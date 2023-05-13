#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Cog for AI interactions, from the OpenAI API."""

import logging
import time
from types import coroutine
from typing import Tuple
from collections import defaultdict

import openai
import openai.error
import disnake
from disnake.ext import commands

from slashbot.config import App
from slashbot.custom_cog import CustomCog
from slashbot.custom_bot import ModifiedInteractionBot


openai.api_key = App.config("OPENAI_API_KEY")

logger = logging.getLogger(App.config("LOGGER_NAME"))
COOLDOWN_USER = commands.BucketType.user


DEFAULT_SYSTEM_MESSAGE = " ".join(
    [
        "You are playing a character named Margaret, a helpful assistant.",
        "You should make references to popular culture wherever appropriate.",
    ]
)

TIME_LIMITED_SERVERS = [
    App.config("ID_SERVER_ADULT_CHILDREN"),
    App.config("ID_SERVER_FREEDOM"),
]


class Chat(CustomCog):
    """AI chat features powered by OpenAI."""

    def __init__(self, bot: ModifiedInteractionBot):
        super().__init__()
        self.bot = bot

        self.guild_prompt_history = {}
        self.guild_prompt_token_count = defaultdict(dict)
        self.guild_cooldown = defaultdict(dict)

        self.model_temperature = 0.5
        self.model_max_history_tokens = 1024  # tokens
        self.model_max_history_remove_fraction = 0.5

    # Functions ----------------------------------------------------------------

    def __openai_chat_completion(self, history_id: int) -> str:
        """Get a message from ChatGPT using the ChatCompletion API.

        Parameters
        ----------
        history_id : int
            The ID to store chat history context to. Usually the guild or user
            id.

        Returns
        -------
        str
            The message returned by ChatGPT.
        """
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=self.guild_prompt_history[history_id],
            temperature=self.model_temperature,
            max_tokens=1024,
        )

        usage = response["usage"]
        message = response["choices"][0]["message"]["content"]

        if len(message) > 1920:
            return "I've generated a sentence which is too large for Discord!"

        self.guild_prompt_history[history_id].append({"role": "assistant", "content": message})
        self.guild_prompt_token_count[history_id] = float(usage["total_tokens"])

        return message

    async def __trim_message_history(self, history_id: int) -> None:
        """Remove messages from a chat history.

        Removes a fraction of the messages from the chat history if the number
        of tokens exceeds a threshold controlled by
        `self.model.max_history_tokens`.

        Parameters
        ----------
        history_id : int
            The chat history ID. Usually the guild or user id.
        """
        if self.guild_prompt_token_count[history_id] < self.model_max_history_tokens:
            return

        num_remove = int(self.model_max_history_remove_fraction * len(self.guild_prompt_history[history_id]))
        logger.info("Removing last %d messages from %d prompt history", num_remove, history_id)

        for i in range(num_remove):
            self.guild_prompt_history[history_id].pop(i + 1)  # + 1 to ignore system message

        self.guild_prompt_token_count[history_id] = 0

    def __get_cooldown_length(self, guild_id: int, user: disnake.User | disnake.Member) -> Tuple[int, int]:
        """Returns the cooldown length and interaction amount fo a user in a
        guild.

        What returns depends on the guild and the role of the user.

        Parameters
        ----------
        guild_id : int
            The ID of the guild the message was sent in.
        user : disnake.User | disnake.Member
            The User or Member object of the user who sent the prompt.

        Returns
        -------
        int
            The cooldown time in minutes
        int
            The max number of interactions before a cooldown is applied
        """
        if guild_id == App.config("ID_SERVER_ADULT_CHILDREN"):
            if App.config("ID_ROLE_TOP_GAY") in [role.id for role in user.roles]:
                return (0, 999)
            return (App.config("COOLDOWN_STANDARD"), App.config("COOLDOWN_RATE"))

        return App.config("COOLDOWN_STANDARD"), App.config("COOLDOWN_RATE")

    async def respond_to_prompt(self, history_id: int, prompt: str) -> str:
        """Process a prompt and get a response.

        This function is the main steering function for getting a response from
        OpenAI ChatGPT. The prompt is prepared, the chat history updated, and
        a response is retrieved and returned.

        If something goes wrong due to, e.g. rate limiting from OpenAI, special
        strings are returned which can be sent to chat.

        Parameters
        ----------
        history_id: int
            An ID to store chat history to. Usually the guild or user id.
        prompt : str
            The latest prompt to give to ChatGPT.

        Returns
        -------
        str
            The generated response to the given prompt.
        """
        prompt = prompt.replace("@Margaret", "", 1).strip()  # todo, remove hardcoded reference

        if history_id not in self.guild_prompt_history:
            self.guild_prompt_token_count[history_id] = 0
            self.guild_prompt_history[history_id] = [{"role": "system", "content": DEFAULT_SYSTEM_MESSAGE}]

        await self.__trim_message_history(history_id)
        self.guild_prompt_history[history_id].append({"role": "user", "content": prompt})

        try:
            response = self.__openai_chat_completion(history_id)
        except openai.error.RateLimitError:
            return "Uh oh! I've hit OpenAI's rate limit :-("
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("OpenAI API failed with exception %s", exc)
            return "Uh oh! Something went wrong with that request :-("

        return response

    async def __check_for_cooldown(self, message: disnake.Message) -> bool:
        """Check if a message author is on cooldown.

        Parameters
        ----------
        message : disnake.Message
            The message recently sent to the bot.

        Returns
        -------
        bool
            True if the use is on cooldown, False if not.
        """
        current_time = time.time()
        last_message_time, message_count = self.guild_cooldown[message.guild.id].get(message.author.id, (0, 0))
        elapsed_time = current_time - last_message_time
        cooldown_length, max_message_count = self.__get_cooldown_length(message.guild.id, message.author)

        if elapsed_time <= cooldown_length and message_count >= max_message_count:
            return True

        if message_count >= cooldown_length:
            message_count = 0

        message_count += 1

        self.guild_cooldown[message.guild.id][message.author.id] = (current_time, message_count)

        return False

    # Listeners ----------------------------------------------------------------

    @commands.Cog.listener("on_message")
    async def listen_for_mentions(self, message: disnake.Message) -> None:
        """Listen for mentions which are prompts for the AI.

        Parameters
        ----------
        message : str
            The message to process for mentions.
        """
        # ignore other both messages and itself
        if message.author.bot or message.author == App.config("BOT_USER_OBJECT"):
            return

        # only respond when mentioned or in DMs
        bot_mentioned = App.config("BOT_USER_OBJECT") in message.mentions
        message_in_dm = isinstance(message.channel, disnake.channel.DMChannel)

        if bot_mentioned or message_in_dm:
            if not message_in_dm and message.guild.id in TIME_LIMITED_SERVERS:
                on_cooldown = await self.__check_for_cooldown(message)

            if on_cooldown:
                try:
                    await message.delete(delay=10)
                    return await message.channel.send(f"Stop abusing me {message.author.mention}!", delete_after=10)
                except disnake.Forbidden:
                    logger.error("Bot does not have permission to delete time limited message.")
                    return

            # if everything ok, type and send
            async with message.channel.typing():
                response = await self.respond_to_prompt(
                    message.author.id if message_in_dm else message.guild.id, message.clean_content
                )

            await message.channel.send(f"{message.author.mention} {response}")

    # Commands -----------------------------------------------------------------

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="clear_ai_chat_history", description="reset your AI chat history")
    async def clear_chat_history(self, inter: disnake.ApplicationCommandInteraction) -> coroutine:
        """Clear history context for where the interaction was called from.

        Parameters
        ----------
        inter : disnake.ApplicationCommandInteraction
            The slash command interaction.
        """
        if inter.guild.id not in self.guild_prompt_history:
            return await inter.response.send_message("There is no chat history to clear.", ephemeral=True)

        logger.info("System prompt reset to default for %s", inter.guild.name)
        self.guild_prompt_history[inter.guild.id] = [{"role": "system", "content": DEFAULT_SYSTEM_MESSAGE}]

        return await inter.response.send_message(
            "System prompt reset to default and chat history cleared.", ephemeral=True
        )

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="set_chat_system_prompt", description="change the chat system prompt")
    async def set_system_message(self, inter: disnake.ApplicationCommandInteraction, message: str) -> coroutine:
        """Set a new system message for the location were the interaction came
        from.

        This typically does not override the default system message, and will
        append a new system message.

        Parameters
        ----------
        inter : disnake.ApplicationCommandInteraction
            The slash command interaction.
        message : str
            The new system prompt to set.
        """
        if inter.guild.id in self.guild_prompt_history:
            self.guild_prompt_history[inter.guild.id].append([{"role": "system", "content": message}])
        else:
            self.guild_prompt_history[inter.guild.id] = [{"role": "system", "content": message}]
        logger.info("New system prompt for chat %s: %s", inter.guild.name, message)

        return await inter.response.send_message(
            "System prompt updated and chat history cleared.",
            ephemeral=True,
        )
