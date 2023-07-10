#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Custom Cog class."""

import logging

import disnake
from disnake.ext import commands, tasks

from slashbot.config import App
from slashbot.markov import (
    MARKOV_MODEL,
    generate_list_of_sentences_with_seed_word,
    generate_sentence,
)

logger = logging.getLogger(App.config("LOGGER_NAME"))


class SlashbotCog(commands.Cog):
    """A custom cog class which modifies cooldown behavior."""

    def __init__(self):
        super().__init__()
        self.markov_sentences = {}
        self.regenerate_markov_sentences.start()  # pylint: disable=no-member

    # Before command invokes ---------------------------------------------------

    async def cog_before_slash_command_invoke(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> disnake.ApplicationCommandInteraction:
        """Reset the cooldown for some users and servers.

        Parameters
        ----------
        inter: disnake.ApplicationCommandInteraction
            The interaction to possibly remove the cooldown from.
        """
        if inter.guild and inter.guild.id != App.config("ID_SERVER_ADULT_CHILDREN"):
            return inter.application_command.reset_cooldown(inter)

        if inter.author.id in App.config("NO_COOL_DOWN_USERS"):
            return inter.application_command.reset_cooldown(inter)

    # Tasks --------------------------------------------------------------------

    @tasks.loop(seconds=5)
    async def regenerate_markov_sentences(self) -> None:
        """Re-generate the markov sentences with a given seed word."""
        if not self.bot.markov_gen_on:
            return
        if len(self.markov_sentences) == 0:
            return

        for seed_word, sentences in self.markov_sentences.items():
            if len(sentences) < App.config("PREGEN_REGENERATE_LIMIT"):
                logger.debug("Regenerating sentences for seed word %s", seed_word)
                self.markov_sentences[seed_word] = generate_list_of_sentences_with_seed_word(
                    MARKOV_MODEL, seed_word, App.config("PREGEN_MARKOV_SENTENCES_AMOUNT")
                )

    @regenerate_markov_sentences.before_loop
    async def wait_before_start(self) -> None:
        """Wait until the bot is ready for the task."""
        await self.bot.wait_until_ready()

    # Functions ----------------------------------------------------------------

    def get_generated_sentence(self, seed_word: str) -> str:
        """Retrieve a pre-generated sentence from storage.

        If a sentence for a seed word doesn't exist, then a sentence is created
        on-the-fly instead.

        Parameters
        ----------
        seed_word : str
            The seed word for the sentence.

        Returns
        -------
        str
            The generated sentence.
        """
        if seed_word not in self.markov_sentences:
            if self.bot.markov_gen_on:
                logger.error("No pre-generated markov sentences for seed word %s ", seed_word)
            return generate_sentence(MARKOV_MODEL, seed_word)

        try:
            return self.markov_sentences[seed_word].pop()
        except IndexError:
            if self.bot.markov_gen_on:
                logger.debug("Using generate_sentence instead of pre gen sentences for %s", seed_word)
            return generate_sentence(MARKOV_MODEL, seed_word)
