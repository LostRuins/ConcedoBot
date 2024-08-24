# ConcedoBot
A very simple Discord bot intended for KoboldCpp

To Use:
- Clone repo
- pip install -r requirements.txt
- create a new `.env` file based on `template.env`, fill in your credentials and endpoint. That file MUST be named `.env`
- python3 concedobot.py

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
```

General Commands:
```
/botsleep @YourBotName - Immediately goes to sleep
/botreset @YourBotName - Clears all past context and goes to sleep
/botstatus @YourBotName - Prints current bot status
/botdraw @YourBotName [prompt] - Generates an image with a prompt
```