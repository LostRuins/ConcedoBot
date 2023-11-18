# ConcedoBot
A very simple Discord bot intended for KoboldCpp

To Use:
- Clone repo
- pip install -r requirements.txt
- create .env file based on template.env, fill in your credentials and endpoint
- python3 concedobot.py

Then invite the bot into your discord server, and enable it on all desired channels with `/botwhitelist @YourBotName` in each channel.

Admin Commands:
```
/botwhitelist @YourBotName - Whitelist the bot from a channel
/botwhitelisttemp [integer] @YourBotName - Temporary whitelist the bot from a channel for X seconds
/botblacklist @YourBotName - Blacklist the bot from a channel
/botmaxlen [integer] @YourBotName - Set output max length
/botidletime [integer] @YourBotName - Set number of seconds before bot enters idle mode
/botcoffeemode @YourBotName - Sets the bot to coffee mode, where it wont go idle for the next message
```

General Commands:
```
/botsleep @YourBotName - Immediately goes to sleep
/botreset @YourBotName - Clears all past context and goes to sleep
/botstatus @YourBotName - Prints current bot status
```