#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Global configuration class."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class App:
    """The global configuration class.

    Contains shared variables or variables which control the operation
    of the bot.
    """

    # __conf is a dictionary of configuration parameters
    __conf = {
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
        # cooldown parameters
        "COOLDOWN_RATE": 3,
        "COOLDOWN_STANDARD": 60,
        "COOLDOWN_ONE_HOUR": 3600,
        "HOURS_IN_WEEK": 168,
        # general discord things
        "MAX_CHARS": 1994,
        "LOGGER_NAME": "slashbot",
        "LOGFILE_NAME": Path("log/slashbot.log"),
        # Define users, roles and channels
        "ID_BOT": 815234903251091456,
        "ID_USER_ADAM": 261097001301704704,
        "ID_USER_ZADETH": 737239706214858783,
        "ID_USER_LIME": 121310675132743680,
        "ID_USER_SAULTYEVIL": 151378138612367360,
        "ID_USER_HYPNOTIZED": 176726054256377867,
        "ID_SERVER_ADULT_CHILDREN": 237647756049514498,
        "ID_SERVER_FREEDOM": 815237689775357992,
        "ID_SERVER_BUMPAPER": 710120382144839691,
        "ID_CHANNEL_IDIOTS": 237647756049514498,
        "ID_CHANNEL_SPAM": 627234669791805450,
        # API keys
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "WOLFRAM_API_KEY": os.getenv("WOLFRAM_API_KEY"),
        "OWM_API_KEY": os.getenv("OWM_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        # File locations
        "BAD_WORDS_FILE": Path("data/badwords.txt"),
        "GOD_WORDS_FILE": Path("data/godwords.txt"),
        "DATABASE_LOCATION": Path("data/slashbot.sqlite.db"),
    }

    __conf["SLASH_SERVERS"] = [
        __conf["ID_SERVER_ADULT_CHILDREN"],
        __conf["ID_SERVER_FREEDOM"],
        __conf["ID_SERVER_BUMPAPER"],
    ]

    __conf["NO_COOL_DOWN_USERS"] = [__conf["ID_USER_SAULTYEVIL"]]

    # __setters is a tuple of parameters which can be set
    __setters = ()

    # Special methods ----------------------------------------------------------

    def __getitem__(self, name: str) -> Any:
        """Get an item from __conf using square bracket indexing.

        Parameters
        ---------
        name: str
            The name of the item to get.

        Returns
        -------
        value: Any
            The value of item.
        """
        return App.__conf[name]

    # Public methods -----------------------------------------------------------

    @staticmethod
    def config(name: str) -> Any:
        """Get a configuration parameter.

        Parameters
        ----------
        name: str
            The name of the parameter to get the value for.
        """
        return App.__conf[name]

    @staticmethod
    def set(name: str, value: Any) -> None:
        """Set the value of a configuration parameter.

        Parameters
        ----------
        name: str
            The name of the parameter to set a value for.
        value: Any
            The new value of the parameter.
        """
        if name in App.__setters:
            App.__conf[name] = value
        else:
            raise NameError(f"Name {name} not accepted in set() method")


# Set up logger ----------------------------------------------------------------

logger = logging.getLogger(App.config("LOGGER_NAME"))
formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)8s : %(message)s (%(filename)s:%(lineno)d)", "%Y-%m-%d %H:%M:%S"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    filename=App.config("LOGFILE_NAME"), encoding="utf-8", maxBytes=int(5e5), backupCount=5
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Set up logger for disnake ----------------------------------------------------

disnake_handler = logging.FileHandler(filename="log/disnake.log", encoding="utf-8", mode="w")
disnake_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger_disnake = logging.getLogger("disnake")
logger_disnake.setLevel(logging.DEBUG)
logger_disnake.addHandler(disnake_handler)
