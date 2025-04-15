# ConcedoBot
A very simple Discord bot intended for KoboldCpp

To Use:
- Clone repo
- pip install -r requirements.txt
- Modify or copy `.env` file, fill in your credentials and endpoint.
- python3 concedobot.py [args]

Available args:
- --env: Specifies the environment file (defaults to .env).
- --char: Specifies the character details file (defaults to character_details.json).
- --maxlen: Specifies the maximum response length (defaults to 360).
- --bot_idletime: Specifies the bot idle time in seconds (defaults to 120).

Then invite the bot into your discord server, and enable it on all desired channels with `/botwhitelist @YourBotName` in each channel.

Admin Commands:
```
/botwhitelist @YourBotName - Whitelist the bot from a channel
/botblacklist @YourBotName - Blacklist the bot from a channel
/botmaxlen [integer] @YourBotName - Set output max length
/botidletime [integer] @YourBotName - Set number of seconds before bot enters idle mode
/botfilteron @YourBotName - Enables the image prompt filter
/botfilteroff @YourBotName - Disables the image prompt filter
/botmemory @YourBotName [prompt] - Overrides the bot memory for this channel
/botbackend @YourBotName [kcpp_base_url] - Overrides the kcpp backend used by the bot in a channel
/botsavesettings @YourBotName - Saves whitelisted channels and bot memories to disk. Does not save chat history.
/botdescribe @YourBotName - Describes an image uploaded by a user.
```

General Commands:
```
/botsleep @YourBotName - Immediately goes to sleep
/botreset @YourBotName - Clears all past context and goes to sleep
/botstatus @YourBotName - Prints current bot status
/botdraw @YourBotName [prompt] - Generates an image with a prompt
```