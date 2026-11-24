# ConcedoBot
A very simple Discord bot intended for KoboldCpp

To Use:
- Clone repo
- pip install -r requirements.txt
- create a new `.env` file based on `template.env`, fill in your credentials and endpoint. That file MUST be named `.env`
- In the Discord Developer Portal, open your application’s **Bot** settings and enable **Message Content Intent** under **Privileged Gateway Intents**. ConcedoBot uses this privileged intent to read messages in whitelisted channels and use them as context for chat replies. [Discord’s guide to enabling privileged intents](https://support-dev.discord.com/hc/en-us/articles/6205754771351-How-do-I-get-Privileged-Intents-for-my-bot)
- python3 concedobot.py [args]

Available optional args:
- --env: Specifies a different environment file to load (defaults to .env).
- --char: Specifies the character details file, otherwise uses the default assistant.
- --maxlen: Specifies the maximum response length (defaults to 360).
- --bot_idletime: Specifies the bot idle time in seconds (defaults to 120).

Then invite the bot into your discord server with the `bot` and `applications.commands` scopes, and enable it on all desired channels with `/botwhitelist` in each channel.

If slash commands are unavailable in a server, the old message-content fallback still works by mentioning the bot, for example `/botwhitelist @YourBotName`.

Admin Commands:
```
/botwhitelist - Whitelist the bot for this channel
/botblacklist - Blacklist the bot from this channel
/botmaxlen [length] - Set output max length
/botidletime [seconds] - Set number of seconds before bot enters idle mode
/botfilteron - Enables the image prompt filter
/botfilteroff - Disables the image prompt filter
/botmemory [prompt] - Overrides the bot memory for this channel. Leave blank to clear.
/botbackend [url] [text_url] [vision_url] [image_url] - Overrides backends used by the bot in this channel. A bare url is a legacy text/vision override; named values can split text, vision, and image generation. Leave blank to clear.
/botsavesettings - Saves whitelisted channels and bot memories to disk. Does not save chat history.
```

General Commands:
```
/botsleep - Immediately goes to sleep
/botreset - Clears all past context and goes to sleep
/botstatus - Prints current bot status
/botdescribe [image] [roleplay] - Describes an uploaded image
/botdraw [prompt] - Generates an image with a prompt
```
