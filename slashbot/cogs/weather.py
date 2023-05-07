#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Commands for getting the weather."""

import json
import logging
from types import coroutine
from typing import Tuple

import disnake
import requests
from disnake.ext import commands
from sqlalchemy.orm import Session

from slashbot.config import App
from slashbot.custom_cog import CustomCog
from slashbot.error import deferred_error_message
from slashbot.db import get_user
from slashbot.db import connect_to_database_engine
from slashbot.markov import MARKOV_MODEL
from slashbot.markov import generate_sentences_for_seed_words


logger = logging.getLogger(App.config("LOGGER_NAME"))


COOLDOWN_USER = commands.BucketType.user
WEATHER_UNITS = ["metric", "imperial"]
FORECAST_TYPES = ["hourly", "daily"]
API_KEY = App.config("OWM_API_KEY")


class GeocodeException(Exception):
    """Geocoding API failure"""


class OneCallException(Exception):
    """OneCall API failure"""


class LocationNotFoundException(Exception):
    """Location not in OWM failure"""


class WeatherCommands(CustomCog):
    """Query information about the weather."""

    def __init__(
        self,
        bot: commands.InteractionBot,
    ) -> None:
        """Initialize the cog.

        Parameters
        ----------
        bot: commands.InteractionBot
            The bot object.
        """
        super().__init__()
        self.bot = bot

        self.markov_sentences = generate_sentences_for_seed_words(
            MARKOV_MODEL,
            ["weather", "forecast"],
            App.config("PREGEN_MARKOV_SENTENCES_AMOUNT"),
        )

    # Private ------------------------------------------------------------------

    @staticmethod
    def __degrees_to_cardinal_direction(degrees: float) -> str:
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

    @staticmethod
    def __get_user_location(user_id: str, user_name: str) -> str:
        """Return the stored location set by a user.

        Parameters
        ----------
        user_id : str
            _description_
        user_name : str
            _description_

        Returns
        -------
        _type_
            _description_
        """
        with Session(connect_to_database_engine()) as session:
            user = get_user(session, user_id, user_name)
            if not user.city:
                return None
            return f"{user.city}, {user.country_code if user.country_code else ''}"

    @staticmethod
    def __get_weather_response(location: str, units: str, extract_type: str) -> Tuple[str, dict]:
        """_summary_

        Parameters
        ----------
        location : str
            _description_
        units : str
            _description_
        extract_type : str
            _description_

        Returns
        -------
        dict
            _description_

        Raises
        ------
        requests.RequestException
            _description_
        requests.exceptions.Timeout
            _description_
        """
        geocode_request = requests.get(
            f"http://api.openweathermap.org/geo/1.0/direct?q={location}&appid={API_KEY}",
            timeout=5,
        )

        if geocode_request.status_code != 200:
            raise GeocodeException(f"Geocoding API failed for {location}")

        geocode = json.loads(geocode_request.content)

        if len(geocode) == 0:
            raise LocationNotFoundException(f"{location} not found in Geocoding API")

        geocode = geocode[0]
        lat, lon = geocode["lat"], geocode["lon"]
        name, country = geocode["name"], geocode["country"]

        one_call_request = requests.get(
            f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&units={units}&exclude=minutely&appid={API_KEY}",
            timeout=5,
        )

        if one_call_request.status_code != 200:
            if one_call_request.status_code == 400:
                raise LocationNotFoundException(f"{location} could not be found")
            else:
                raise OneCallException(f"OneCall API failed for {location}")

        return f"{name}, {country}", json.loads(one_call_request.content)[extract_type]

    @staticmethod
    def __get_weather_icon_url(icon_code: str) -> str:
        """_summary_

        Parameters
        ----------
        icon_code : str
            _description_

        Returns
        -------
        str
            _description_
        """
        return f"https://openweathermap.org/img/wn/{icon_code}@2x.png"

    # Commands -----------------------------------------------------------------

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="forecast", description="get the weather forecast")
    async def forecast(  # pylint: disable=too-many-locals
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_location: str = commands.Param(
            name="location", description="The city to get weather at, default is your saved location.", default=None
        ),
        forecast_type: str = commands.Param(
            description="The type of forecast to return.", default="daily", choices=FORECAST_TYPES
        ),
        units: str = commands.Param(
            description="The units to return weather readings in.", default="metric", choices=WEATHER_UNITS
        ),
        amount: int = commands.Param(description="The number of results to return.", default=3, gt=0, lt=5),
    ) -> coroutine:
        """Print the weather forecast for a location.

        Parameters
        ----------
        inter: disnake.ApplicationCommandInteraction
            The interaction to possibly remove the cooldown from.
        location: str
            The location to get the weather forecast for.
        days: int
            The number of days to return the forecast for.
        """
        await inter.response.defer()

        if not user_location:
            user_location = self.__get_user_location(inter.author.id, inter.author.name)
            if not user_location:
                return await deferred_error_message(
                    inter, "You need to either specify a city, or set your city and/or country using /set_info."
                )

        try:
            location, forecast = self.__get_weather_response(user_location, units, forecast_type)
        except (LocationNotFoundException, GeocodeException):
            return await deferred_error_message(inter, f"{user_location} is not available in OpenWeatherMap.")
        except OneCallException:
            return await deferred_error_message(inter, "OpenWeatherMap OneCall API has returned an error.")
        except requests.Timeout:
            return await deferred_error_message(inter, "OpenWeatherMap API has timed out.")

        embed = disnake.Embed(
            title=f"{forecast_type.capitalize()} forecast for {location}", color=disnake.Color.default()
        )

        embed.set_footer(text=f"{self.get_generated_sentence('forecast')}")
        embed.set_thumbnail(self.__get_weather_icon_url(forecast["weather"][0]["icon"]))

        return await inter.edit_original_message(embed=embed)

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="weather", description="get the current weather")
    async def weather(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_location: str = commands.Param(
            name="location", description="The city to get weather for, default is your saved location.", default=None
        ),
        units: str = commands.Param(
            description="The units to return weather readings in.", default="metric", choices=WEATHER_UNITS
        ),
    ) -> coroutine:
        """Get the weather for a location.

        Parameters
        ----------
        inter: disnake.ApplicationCommandInteraction
            The interaction to possibly remove the cooldown from.
        where: str
            The location to get the weather for.
        what: str
            What to get, either the whole forecast, temperature, rain or wind.
        units: str
            The units to use, either metric or imperial.
        """
        await inter.response.defer()

        if not user_location:
            user_location = self.__get_user_location(inter.author.id, inter.author.name)
            if not user_location:
                return await deferred_error_message(
                    inter, "You need to specify a city, or set your city and/or country using /set_info."
                )

        try:
            location, weather = self.__get_weather_response(user_location, units, "current")
        except (LocationNotFoundException, GeocodeException):
            return await deferred_error_message(inter, f"{user_location} is not available in OpenWeatherMap.")
        except OneCallException:
            return await deferred_error_message(inter, "OpenWeatherMap OneCall API has returned an error.")
        except requests.Timeout:
            return await deferred_error_message(inter, "OpenWeatherMap API has timed out.")

        if units == "metric":
            temp_unit, wind_unit, wind_factor = "C", "km/h", 3.6
        else:
            temp_unit, wind_unit, wind_factor = "F", "mph", 1

        embed = disnake.Embed(title=f"Current weather conditions for {location}", color=disnake.Color.default())

        embed.add_field(name="Description", value=weather["weather"][0]["description"].capitalize(), inline=False)
        embed.add_field(name="Temperature", value=weather["temp"] + f" °{temp_unit}", inline=False)
        embed.add_field(name="Humidity", value=weather["humidity"] + "%", inline=False)
        embed.add_field(
            name="Wind speed", value=f"{float(weather['wind_speed']) * wind_factor:.1f} {wind_unit}", inline=False
        )
        embed.add_field(
            name="Wind direction",
            value=f"{weather['wind_deg']:.01f}° ({self.__degrees_to_cardinal_direction(weather['wind_deg'])})",
            inline=False,
        )

        embed.set_footer(text=f"{self.get_generated_sentence('weather')}")
        embed.set_thumbnail(self.__get_weather_icon_url(weather["weather"][0]["icon"]))

        return await inter.edit_original_message(embed=embed)
