#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Global configuration class."""

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

SLASH_CONFIG = None


def load_config():
    global SLASH_CONFIG
    with open(os.getenv("SLASHBOT_CONFIG"), "r", encoding="utf-8") as file_in:
        SLASH_CONFIG = json.load(file_in)


load_config()


def setup_logging():
    """Setup up the logger and log file."""

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger = logging.getLogger(App.config("LOGGER_NAME"))
    logger.addHandler(console_handler)

    if Path(App.config("LOGFILE_NAME")).parent.exists():
        file_handler = RotatingFileHandler(
            filename=App.config("LOGFILE_NAME"), encoding="utf-8", maxBytes=int(5e5), backupCount=5
        )
        file_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)8s : %(message)s (%(filename)s:%(lineno)d)", "%Y-%m-%d %H:%M:%S"
            )
        )
        logger.addHandler(file_handler)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.info("Loaded config file %s", os.getenv("SLASHBOT_CONFIG"))


class FileWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.event_type == "modified" and event.src_path == os.getenv("SLASHBOT_CONFIG"):
            # TODO: this triggers twice on file modify...
            App._set_config_values()


class App:
    """The global configuration class.

    Contains shared variables or variables which control the operation
    of the bot.
    """

    # __conf is a dictionary of configuration parameters
    _config = {}

    # Private methods ----------------------------------------------------------

    @classmethod
    def _set_config_values(cls):
        """Set the values of the config from the config file.

        The purpose of this script is to populate the __conf class attribute.
        """
        load_config()
        _config = {
            # cooldown parameters
            "COOLDOWN_RATE": int(SLASH_CONFIG["COOLDOWN"]["RATE"]),
            "COOLDOWN_STANDARD": int(SLASH_CONFIG["COOLDOWN"]["STANDARD"]),
            "COOLDOWN_EXTENDED": int(SLASH_CONFIG["COOLDOWN"]["EXTENDED"]),
            "NO_COOLDOWN_USERS": SLASH_CONFIG["COOLDOWN"]["NO_COOLDOWN_USERS"],
            "NO_COOLDOWN_SERVERS": SLASH_CONFIG["COOLDOWN"]["NO_COOLDOWN_SERVERS"],
            # general things
            "MAX_CHARS": SLASH_CONFIG["DISCORD"]["MAX_CHARS"],
            "LOGGER_NAME": SLASH_CONFIG["LOGFILE"]["LOG_NAME"],
            "LOGFILE_NAME": SLASH_CONFIG["LOGFILE"]["LOG_LOCATION"],
            "DEVELOPMENT_SERVERS": [],
            # Define users, roles and channels
            "ID_USER_SAULTYEVIL": 151378138612367360,
            # API keys
            "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
            "WOLFRAM_API_KEY": os.getenv("WOLFRAM_API_KEY"),
            "OWM_API_KEY": os.getenv("OWM_API_KEY"),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "MONSTER_API_KEY": os.getenv("MONSTER_API_KEY"),
            # File locations
            "DATABASE_LOCATION": Path(SLASH_CONFIG["FILES"]["DATABASE"]),
            "BAD_WORDS_FILE": Path(SLASH_CONFIG["FILES"]["BAD_WORDS"]),
            "GOD_WORDS_FILE": Path(SLASH_CONFIG["FILES"]["GOD_WORDS"]),
            "SCHEDULED_POST_FILE": Path(SLASH_CONFIG["FILES"]["SCHEDULED_POSTS"]),
            "RANDOM_MEDIA_DIRECTORY": Path(SLASH_CONFIG["FILES"]["RANDOM_MEDIA_DIRECTORY"]),
            # Markov Chain configuration
            "ENABLE_MARKOV_TRAINING": bool(SLASH_CONFIG["MARKOV"]["ENABLE_MARKOV_TRAINING"]),
            "ENABLE_PREGEN_SENTENCES": bool(SLASH_CONFIG["MARKOV"]["ENABLE_PREGEN_SENTENCES"]),
            "PREGEN_MARKOV_SENTENCES_AMOUNT": int(SLASH_CONFIG["MARKOV"]["NUM_PREGEN_SENTENCES"]),
            "PREGEN_REGENERATE_LIMIT": int(SLASH_CONFIG["MARKOV"]["PREGEN_REGENERATE_LIMIT"]),
            # Cog settings
            "SPELLCHECK_SERVERS": [],
        }
        cls._config = _config

    # Public methods -----------------------------------------------------------

    @staticmethod
    def config(name: str) -> Any:
        """Get a configuration parameter.

        Parameters
        ----------
        name: str
            The name of the parameter to get the value for.
        """
        return App._config[name]


App._set_config_values()
setup_logging()

observer = Observer()
observer.schedule(FileWatcher(), path=Path(os.getenv("SLASHBOT_CONFIG")).parent)
observer.start()
