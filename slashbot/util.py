#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Various utility functions used through slashbot."""

import base64
import datetime
import json
import logging
import pathlib
import re
from io import BytesIO
from typing import Any, Dict, List
from urllib.parse import urlparse

import disnake
import httpx
from PIL import Image

from slashbot.config import App

logger = logging.getLogger(App.get_config("LOGGER_NAME"))


async def send_cooldown_message(
    channel: disnake.TextChannel | disnake.DMChannel, author: disnake.User | disnake.Member
) -> None:
    """Respond to a user on cooldown.

    Historically, this used to do a lot more.

    Parameters
    ----------
    channel
        The channel to send the message to
    author
        The user to respond to
    """
    await channel.send(f"Stop abusing me {author.mention}!")


def split_text_into_chunks(text: str, chunk_length: int) -> list:
    """
    Split text into smaller chunks of a set length while preserving sentences.

    Parameters
    ----------
    text : str
        The input text to be split into chunks.
    chunk_length : int, optional
        The maximum length of each chunk. Default is 1648.

    Returns
    -------
    list
        A list of strings where each string represents a chunk of the text.
    """
    chunks = []
    current_chunk = ""

    while len(text) > 0:
        # Find the nearest sentence end within the chunk length
        end_index = min(len(text), chunk_length)
        while end_index > 0 and text[end_index - 1] not in (".", "!", "?"):
            end_index -= 1

        # If no sentence end found, break at chunk length
        if end_index == 0:
            end_index = chunk_length

        current_chunk += text[:end_index]
        text = text[end_index:]

        if len(text) == 0 or len(current_chunk) + len(text) > chunk_length:
            chunks.append(current_chunk)
            current_chunk = ""

    return chunks


def join_list_max_chars(words: List[str], max_chars: int) -> str:
    """Join a list of words into a comma-separated list.

    Parameters
    ----------
    words : List[str]
        A list of words to join together
    max_chars : int
        The maximum length the output string can be

    Returns
    -------
    str
        The joined words with "..." at the end if max_chars is hit
    """
    result = ""
    current_length = 0

    for word in words:
        if current_length + len(word) > max_chars - 3:
            if result:
                result += "..."
            break
        result += word + ", "
        current_length += len(word)

    # Remove the trailing ", " if there's anything in the result
    if result.endswith(", "):
        result = result[:-2]

    return result


def convert_string_to_lower(_inter: disnake.ApplicationCommandInteraction, variable: Any) -> Any:
    """Slash command convertor to transform a string into all lower case.

    Parameters
    ----------
    _inter : disnake.ApplicationCommandInteraction
        The slash command interaction. Currently unused.
    variable : Any
        The possible string to convert into lower case.

    Returns
    -------
    Any :
        If a string was passed, the lower version of the string is returned.
        Otherwise the original variable is returned.
    """
    return variable.lower() if isinstance(variable, str) else variable


def convert_yes_no_to_bool(_inter: disnake.ApplicationCommandInteraction, choice: str) -> bool:
    """_summary_

    Parameters
    ----------
    _inter : disnake.ApplicationCommandInteraction
        The slash command interaction. Currently unused.
    choice : str
        The yes/no string to convert into a bool.

    Returns
    -------
    bool
        True or False depending on yes or no.
    """
    return True if choice.lower() == "yes" else False


def remove_emojis_from_string(string: str) -> str:
    """Remove emojis from a string.

    Parameters
    ----------
    string : str
        _description_

    Returns
    -------
    str
        _description_
    """
    emoj = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U00002500-\U00002bef"  # chinese char
        "\U00002702-\U000027b0"
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2b55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        re.UNICODE,
    )
    return re.sub(emoj, "", string)


def convert_radial_to_cardinal_direction(degrees: float) -> str:
    """Convert a degrees value to a cardinal direction.

    Parameters
    ----------
    degrees: float
        The degrees direction.

    Returns
    -------
    The cardinal direction as a string.
    """
    directions = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]

    return directions[round(degrees / (360.0 / len(directions))) % len(directions)]


def read_in_prompt_json(filepath: str | pathlib.Path) -> dict:
    """Read in a prompt and check for keys."""
    required_keys = (
        "name",
        "prompt",
    )

    with open(filepath, "r", encoding="utf-8") as prompt_in:
        prompt = json.load(prompt_in)
        if not all(key in prompt for key in required_keys):
            raise OSError(f"{filepath} is missing either 'name' or 'prompt' key")

    return prompt


def create_prompt_dict() -> dict:
    """Creates a dict of prompt_name: prompt."""
    return {
        prompt_dict["name"]: prompt_dict["prompt"]
        for prompt_dict in [
            read_in_prompt_json(file)
            for file in pathlib.Path("data/prompts").glob("*.json")
            if not file.name.startswith("_")  # prompts which start with _ are hidden prompts
        ]
    }


def add_days_to_datetime(
    now: datetime.datetime, original_date: datetime.datetime, days_to_add: float
) -> datetime.datetime:
    """Add a week to a datetime object.

    Parameters
    ----------
    now: datetime.datetime:
        The current datetime.
    original_date: datetime.datetime
        The datetime to calculate from.
    days_to_add: float
        The number of additional days to sleep for

    Returns
    -------
    A datetime object a week after the given one.
    """
    if days_to_add < 0:
        raise ValueError("Invalid value for days_to_add, cannot be < 0")
    if not isinstance(original_date, datetime.datetime):
        raise ValueError("Need to pass time as a datetime.datetime")

    time_delta = original_date + datetime.timedelta(days=days_to_add)
    next_date = datetime.datetime(
        year=time_delta.year,
        month=time_delta.month,
        day=time_delta.day,
        hour=original_date.hour,
        minute=original_date.minute,
        second=original_date.second,
    )
    sleep_for_seconds = (next_date - now).total_seconds()

    return sleep_for_seconds


def calculate_seconds_until(weekday: int, hour: int, minute: int, frequency: int) -> int:
    """Calculate how long to sleep till a hour:minute time for a given weekday.

    If the requested moment is time is beyond the current time, the number of
    days provided in frequency are added.

    Parameters
    ----------
    weekday : int
        An integer representing the weekday, where Monday is 0.
    hour : int
        The hour for the requested time.
    minute : int
        The minute for the requested time.
    frequency : Frequency
        The frequency at which to repeat this.

    Returns
    -------
    int
        The time to sleep for in seconds.
    """
    if frequency < 0:
        raise ValueError("Invalid value for frequency, cannot be < 0")
    if not isinstance(weekday, int) or weekday > 6:
        raise ValueError("Invalid value for weekday: 0 <= weekday <= 6 and must be int")

    now = datetime.datetime.now()

    if weekday < 0:
        weekday = now.weekday()

    day_delta = now + datetime.timedelta(days=(weekday - now.weekday()) % 7)
    next_date = datetime.datetime(
        year=day_delta.year, month=day_delta.month, day=day_delta.day, hour=hour, minute=minute, second=0
    )
    sleep_for_seconds = (next_date - now).total_seconds()

    if sleep_for_seconds <= 0:
        sleep_for_seconds = add_days_to_datetime(now, next_date, frequency)

    return sleep_for_seconds


async def get_image_from_url(image_urls: str) -> List[Dict[str, str]]:
    """Fetch images from the given URL(s) and return their base64-encoded data.

    Parameters
    ----------
    image_urls : str or List[str]
        A single image URL or a list of image URLs.

    Returns
    -------
    List[Dict[str, str]]
        A list of dictionaries, where each dictionary contains the base64-encoded image data string and the image type (file extension).
    """
    image_data = []
    for url in image_urls:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                parsed_url = urlparse(url)
                image_type = parsed_url.path.split(".")[-1]
                image_type = "jpeg" if image_type == "jpg" else image_type  # Replace "jpg" with "jpeg"
                image_data.append(
                    {"type": "image/" + image_type, "image": base64.b64encode(response.content).decode("utf-8")}
                )
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            logger.error("Error fetching image from %s: %s", url, exc)

    return image_data


def resize_image(image_string: str, image_type: str, target_megapixels: float = 1.15) -> str:
    """
    Resizes an image to a target number of megapixels while maintaining the aspect ratio.

    Parameters
    ----------
    image_string : str
        The base64-encoded string representation of the image.
    image_type : str
        The MIME type of the image (e.g., "image/jpeg", "image/png").
    target_megapixels : float, optional
        The desired number of megapixels for the resized image. Default is 1.12.

    Returns
    -------
    str
        The base64-encoded string representation of the resized image.
    """
    # Decode the base64-encoded string to a bytes object
    image_bytes = base64.b64decode(image_string)

    # Open the image from the bytes object
    image = Image.open(BytesIO(image_bytes))

    # Calculate the target dimensions based on the target megapixels and aspect ratio
    width, height = image.size
    aspect_ratio = width / height
    target_pixels = target_megapixels * 1e6
    if width * height > target_pixels:
        if width > height:
            target_width = int((target_pixels * aspect_ratio) ** 0.5)
            target_height = int(target_width / aspect_ratio)
        else:
            target_height = int((target_pixels / aspect_ratio) ** 0.5)
            target_width = int(target_height * aspect_ratio)
    else:
        target_width = width
        target_height = height

    # Resize the image to the target dimensions
    resized_image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Convert the resized image to a bytes object and encode it as a base64 string
    buffer = BytesIO()
    if "webp" in image_type:  # this is a crutch to stop webp crashing the bot
        resized_image.save(buffer, format="JPEG")
    else:
        resized_image.save(buffer, format=image_type.split("/")[1].upper())
    resized_image_bytes = buffer.getvalue()
    resized_image_string = base64.b64encode(resized_image_bytes).decode("utf-8")

    return resized_image_string
