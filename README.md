# slashbot

slashbot is a shitty discord bot written using disnake, based on my previous
bot, badbot. It is designed to work in only a few servers, hence there are some
hardcoded IDs in here.

## Features

Here are some of the main features

* Markov Chain sentence generation (learns from the server)
* Embed a YouTube search
* Set, view and remove reminders
* Generate sentences from God's temple
* Post images from rule34.xxx
* Get the news headlines
* Check the weather and forecast
* Ask Stephen Wolfram a question
* Send a gif of a spitting girl

## Deployment

slashbot can be deployed using docker and docker-compose,

```bash
$ docker-compose up -d --build
```

You will need the environment variables listed in the next section in a file
named `docker-env.env`.

## Requirements

Python 3.10 is required. All other requirements are in requirements.txt, and
can be installed as such,

```bash
$ python -m pip install -r requirements.txt
```

The following environment variables are required,

```
export BOT_TOKEN="XXXXXXXXXXXXXXXXXXXX"       # the discord bot token
export YT_VIDEO_KEY="XXXXXXXXXXXXXXXXXXXX"    # a google api key
export OWM_KEY="XXXXXXXXXXXXXXXXXXXX"         # an open weather map api key
export WOLFRAM_ID="XXXXXXXXXXXXXXXXXXXX"      # a wolfram alpha api key
export NEWS_API="XXXXXXXXXXXXXXXXXXXX"        # an api key for newsapi.org
export TWITTER_BEARER="XXXXXXXXXXXXXXXXXXXX"  # twitter bearer token
```

## Usage

```bash
$ python run.py
```
