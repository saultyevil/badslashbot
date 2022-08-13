#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import json
import re

import disnake
from dateutil import parser
from disnake.ext import commands, tasks
from prettytable import PrettyTable

import config

cd_user = commands.BucketType.user
time_units = {
    "time": 1,
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
}
whofor = ["here", "dm", "both"]


class Reminder(commands.Cog):
    """Commands to set up reminders."""

    def __init__(self, bot, generate_sentence):
        self.bot = bot
        self.generate_sentence = generate_sentence
        self.reminders = {}
        self.load_reminders()
        self.check_reminders.start()  # pylint: disable=no-member

    # Before command invoke ----------------------------------------------------

    async def cog_before_slash_command_invoke(self, inter):
        """Reset the cooldown for some users and servers."""
        if inter.guild and inter.guild.id != config.ID_SERVER_ADULT_CHILDREN:
            return inter.application_command.reset_cooldown(inter)

        if inter.author.id in config.NO_COOLDOWN_USERS:
            return inter.application_command.reset_cooldown(inter)

    # Commands -----------------------------------------------------------------

    @commands.cooldown(1, config.COOLDOWN_STANDARD, cd_user)
    @commands.slash_command(name="remind", description="set a reminder")
    async def add(
        self,
        inter,
        when: str = commands.Param(),
        time_unit=commands.Param(choices=list(time_units.keys())),
        reminder=commands.Param(),
        where=commands.Param(default="here", choices=whofor),
    ):
        """Set a reminder.

        Parameters
        ----------
        when: float
            The amount of time to wait before the reminder.
        time_unit: str
            The unit of time to wait before the reminder.
        reminder: str
            The reminder to set.
        where: str
            Where to be reminded, either "here", "dm" or "both".
        """
        if len(reminder) > 1024:
            return await inter.response.send_message(
                "That is too long of a reminder. 1024 characters is the max.",
                ephemeral=True,
            )

        tagged_users, reminder = self.replace_mentions(reminder)
        user_id = inter.author.id
        channel_id = inter.channel.id

        if time_unit != "time":
            try:
                when = float(when)
            except ValueError:
                return await inter.response.send_message("That is not a valid number.", ephemeral=True)
            if when <= 0:
                return await inter.response.send_message(
                    f"You can't set a reminder for 0 {time_unit} or less.",
                    ephemeral=True,
                )

        now = datetime.datetime.now()

        if time_unit == "time":
            try:
                future = parser.parse(when)
            except parser.ParserError:
                return await inter.response.send_message("That is not a valid timestamp.", ephemeral=True)
        else:
            seconds = when * time_units[time_unit]
            future = now + datetime.timedelta(seconds=seconds)

        future = future.isoformat()

        if future < now.isoformat():
            return await inter.response.send_message("You can't set a reminder in the past.", ephemeral=True)

        key = len(reminder) + 1
        while str(key) in self.reminders:
            key += 1

        self.reminders[str(key)] = {
            "user": user_id,
            "whofor": where,
            "channel": channel_id,
            "tag": tagged_users,
            "when": future,
            "what": reminder,
        }
        self.save_reminders()

        if time_unit == "time":
            await inter.response.send_message(f"Reminder set for {when}.", ephemeral=True)
        else:
            await inter.response.send_message(f"Reminder set for {when} {time_unit}.", ephemeral=True)

    @commands.cooldown(config.COOLDOWN_RATE, config.COOLDOWN_STANDARD, cd_user)
    @commands.slash_command(name="forget", description="clear your reminders")
    async def remove(self, inter, m_id):
        """Clear a reminder or all of a user's reminders.

        Parameters
        ----------
        m_id: str
            The id of the reminder to remove.
        """
        if m_id not in self.reminders:
            return await inter.response.send_message("That reminder doesn't exist.", ephemeral=True)

        if self.reminders[m_id]["user"] != inter.author.id:
            return await inter.response.send_message("You can't remove someone else's reminder.", ephemeral=True)

        removed = self.reminders.pop(m_id, None)
        self.save_reminders()

        await inter.response.send_message(f"Reminder for {removed['what']} removed.", ephemeral=True)

    @commands.cooldown(config.COOLDOWN_RATE, config.COOLDOWN_STANDARD, cd_user)
    @commands.slash_command(name="planned", description="view your reminders")
    async def show(self, inter):
        """Show the reminders set for a user."""
        reminders = [
            [m_id, datetime.datetime.fromisoformat(item["when"]), item["what"]]
            for m_id, item in self.reminders.items()
            if item["user"] == inter.author.id
        ]
        if not reminders:
            return await inter.response.send_message("You don't have any reminders set.", ephemeral=True)

        message = f"You have {len(reminders)} reminders set.\n```"
        table = PrettyTable()
        table.align = "r"
        table.field_names = ["ID", "When", "What"]
        table._max_width = {"ID": 10, "When": 10, "What": 50}  # pylint: disable=protected-access
        table.add_rows(reminders)
        message += table.get_string(sortby="ID") + "```"

        await inter.response.send_message(message, ephemeral=True)

    @commands.cooldown(config.COOLDOWN_RATE, config.COOLDOWN_STANDARD, cd_user)
    @commands.slash_command(name="allplanned", description="view all the reminders, if you're allowed to")
    async def show_all(self, inter):
        """Show all the reminders."""
        if inter.author.id not in config.NO_COOLDOWN_USERS:
            return await inter.response.send_message(
                "You do not have permission to view all the reminders.", ephemeral=True
            )

        reminders = [
            [m_id, datetime.datetime.fromisoformat(item["when"]), item["what"]] for m_id, item in self.reminders.items()
        ]
        if not reminders:
            return await inter.response.send_message("There are no reminders.", ephemeral=True)

        message = f"There are {len(reminders)} reminders set.\n```"
        table = PrettyTable()
        table.align = "r"
        table.field_names = ["ID", "When", "What"]
        table._max_width = {"ID": 10, "When": 10, "What": 50}  # pylint: disable=protected-access
        table.add_rows(reminders)
        message += table.get_string(sortby="ID") + "```"

        await inter.response.send_message(message[:2000], ephemeral=True)

    # Tasks --------------------------------------------------------------------

    @tasks.loop(seconds=5.0)
    async def check_reminders(self):
        """Check if any reminders need to be sent."""
        for m_id, reminder in list(self.reminders.items()):
            when = datetime.datetime.fromisoformat(reminder["when"])

            if when <= datetime.datetime.now():
                user = self.bot.get_user(reminder["user"])
                if user.id == config.ID_USER_ADAM:
                    continue
                embed = disnake.Embed(title=reminder["what"], color=disnake.Color.default())
                embed.set_footer(text=f"{self.generate_sentence('reminder')}")
                embed.set_thumbnail(url=user.avatar.url)

                if reminder["whofor"] == "dm" or reminder["whofor"] == "both":
                    await user.send(embed=embed)

                if reminder["whofor"] == "here" or reminder["whofor"] == "both":
                    channel = self.bot.get_channel(reminder["channel"])
                    message = f"{user.mention}"

                    if user.id != config.ID_USER_ADAM:
                        for user_id in reminder["tag"]:
                            user = self.bot.get_user(int(user_id))
                            if user:
                                message += f" {user.mention}"

                    await channel.send(message, embed=embed)

                self.reminders.pop(m_id, None)
                self.save_reminders()

    # Functions ----------------------------------------------------------------

    def load_reminders(self):
        """Load the reminders from a file."""
        with open(config.REMINDERS_FILE, "r", encoding="utf-8") as fp:
            self.reminders = json.load(fp)

    def replace_mentions(self, sentence):
        """Replace mentions from a post with the user name."""
        user_ids = re.findall(r"\<@!(.*?)\>", sentence)

        for u_id in user_ids:
            user = self.bot.get_user(int(u_id))
            sentence = sentence.replace(f"<@!{u_id}>", user.name)

        return user_ids, sentence

    def save_reminders(self):
        """Dump the reminders to a file."""
        with open(config.REMINDERS_FILE, "w", encoding="utf-8") as fp:
            json.dump(self.reminders, fp)
