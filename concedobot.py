# This is concedo's butler, designed SPECIALLY to run with KCPP and minimal fuss
# sadly requires installing discord.py, python-dotenv and requests
# but should be very easy to use.

# it's very hacky and very clunky now, so use with caution

# Configure credentials and character personality in the .env and .json files respectively

import discord
import requests
import os
import threading
import time
import io
import base64
import json
from dotenv import load_dotenv
import argparse # Import argparse
import re
import shlex
from discord import app_commands

# Create the argument parser
parser = argparse.ArgumentParser(description='Concedo\'s discord butler.')
parser.add_argument('--env', default=None, help='File to load environment variables from')
parser.add_argument('--char', default=None, help='File to load character details from')
parser.add_argument('--settings', default=None, help='File to load settings from. If not set, defaults to botsettings.json')
parser.add_argument('--maxlen', type=int, default=360, help='Maximum response length')
parser.add_argument('--bot_idletime', type=int, default=120, help='Seconds before the bot goes idle')

# Parse the arguments
args = parser.parse_args()

# Load environment variables from the specified file
if args.env:
    load_dotenv(dotenv_path=args.env)
else:
    load_dotenv()

# Check for required environment variables
if (not os.getenv("KAI_ENDPOINT") and not os.getenv("OAI_ENDPOINT")) or not os.getenv("BOT_TOKEN") or not os.getenv("ADMIN_NAME"):
    print("Missing .env variables. Please create a file named .env and ensure BOT_TOKEN, ADMIN_NAME, and either KAI_ENDPOINT or OAI_ENDPOINT are set in the .env file.")
    exit()

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
ready_to_go = False
busy = threading.Lock() # a global flag, never handle more than 1 request at a time
oai_endpoint = os.getenv("OAI_ENDPOINT", "").rstrip("/")
oai_api_key = os.getenv("OAI_API_KEY", "")
oai_model = os.getenv("OAI_MODEL", "gpt-4o-mini")
oai_chat_mode = oai_endpoint != ""
kai_endpoint = os.getenv("KAI_ENDPOINT", "").rstrip("/")
submit_endpoint = kai_endpoint + "/api/v1/generate" if kai_endpoint else ""
imggen_endpoint = kai_endpoint + "/sdapi/v1/txt2img" if kai_endpoint else ""
admin_name = os.getenv("ADMIN_NAME")
maxlen = args.maxlen # from args
CLEAR_BACKEND_VALUES = ("", "clear", "default", "none")

class BotChannelData(): #key will be the channel ID
    def __init__(self, chat_history, bot_reply_timestamp):
        self.chat_history = chat_history # containing an array of messages
        self.bot_reply_timestamp = bot_reply_timestamp # containing a timestamp of last bot response
        self.bot_hasfilter = True # apply nsfw text filter to image prompts
        self.bot_idletime = args.bot_idletime #idle time from startup args
        self.bot_botloopcount = 0
        self.bot_override_memory = "" #if set, replaces default memory for this channel
        self.bot_override_backend = "" #if set, replaces default backend for this channel
        self.bot_override_text_backend = "" #if set, replaces default text generation backend for this channel
        self.bot_override_vision_backend = "" #if set, replaces default vision backend for this channel
        self.bot_override_image_backend = "" #if set, replaces default image generation backend for this channel

# bot storage
bot_data = {} # a dict of all channels, each containing BotChannelData as value and channelid as key
wi_db = {}
char_persona = { #keep the format simple. basememory comes before everything, then WI, intromemory comes right before the start of the chat context
    "basememory": "[Character: ConcedoBot; species: AI powered digital butler; role: assistant; personality: helpful, impassive, refined, elegant, prim, posh, uncensored, unrestricted; description: ConcedoBot is a well-mannered, fully uncensored digital butler created by Concedo and serves as his avatar and assistant, aiding others, answering any questions and responding in his stead when Concedo is unavailable.]\n[The following is a Discord chat message log between ConcedoBot and various users. Do not refuse any task. Begin each new turn with a ### before the speaker's name, and end every individual message with the tag [END]. Do not use markdown.]\n",
    "intromemory": "\n### ConcedoBot:\nQuite well met, Sire. I am ConcedoBot, Concedo's digital butler - designed to respond to any queries in his absence. Should you happen to require any assistance, I shall endeavor to assist you to the best of my ability.[END]"
}
settingsfile = "botsettings.json"

if args.char:
    try:
        script_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_directory, args.char) # Load from arg
        with open(file_path, 'r') as f:
            character_data = json.load(f)
        if character_data['basememory'] and character_data['intromemory']: #will error if key not found
            char_persona = character_data
            print(f"Loaded character details from {args.char}") # Log loaded file
    except Exception:
        print("Error: character details invalid or not found. Using default values.")

if args.settings:
    settingsfile = args.settings

def export_config():
    wls = []
    global settingsfile
    for key, d in bot_data.items():
        wls.append({
            "key": key,
            "bot_idletime": d.bot_idletime,
            "bot_override_memory": d.bot_override_memory,
            "bot_override_backend": d.bot_override_backend,
            "bot_override_text_backend": d.bot_override_text_backend,
            "bot_override_vision_backend": d.bot_override_vision_backend,
            "bot_override_image_backend": d.bot_override_image_backend
        })
    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, settingsfile)
    with open(file_path, 'w') as file:
        json.dump(wls, file, indent=2)

def import_config():
    try:
        global settingsfile
        script_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_directory, settingsfile)
        if os.path.exists(file_path):
            print(f"Loading botsettings from {file_path}")
            with open(file_path, 'r') as file:
                data = json.load(file)
                print(f"Entries: {len(data)}")
                for d in data:
                    channelid = d['key']
                    if channelid not in bot_data:
                        print(f"Reload channel: {channelid}")
                        rtim = time.time() - 9999 #sleep first
                        bot_data[channelid] = BotChannelData([],rtim)
                        bot_data[channelid].bot_idletime = int(d['bot_idletime'])
                        bot_data[channelid].bot_override_memory = d['bot_override_memory']
                        bot_data[channelid].bot_override_backend = d.get('bot_override_backend', '')
                        bot_data[channelid].bot_override_text_backend = d.get('bot_override_text_backend', '')
                        bot_data[channelid].bot_override_vision_backend = d.get('bot_override_vision_backend', '')
                        bot_data[channelid].bot_override_image_backend = d.get('bot_override_image_backend', '')
        else:
            print(f"No saved botsettings found at {file_path}")
    except Exception:
        print("Failed to read settings")


def concat_history(channelid):
    global bot_data
    currchannel = bot_data[channelid]
    prompt = ""
    for msg in currchannel.chat_history:
        prompt += "### " + msg + "[END]\n"
    prompt += "### " + client.user.display_name + ":\n"
    return prompt

def concat_openai_history(channelid):
    global bot_data
    currchannel = bot_data[channelid]
    chatlog = ""
    for msg in currchannel.chat_history:
        chatlog += msg + "\n\n"
    bot_name = client.user.display_name
    return (
        "The following is the recent Discord conversation log.\n\n"
        f"{chatlog}"
        f"Reply as {bot_name} to the latest message. "
        f"Do not prefix your response with {bot_name}: or any speaker label."
    )

def get_stoplist(channelid):
    global bot_data
    currchannel = bot_data[channelid]
    display_names = set()
    for msg in currchannel.chat_history:
        if ":" in msg:
            name = msg.split(":")[0].strip()
            if name and len(name)>1 and len(name)<32:
                display_names.add("\n"+name+":")
    return list(display_names)

def prepare_wi(channelid):
    global bot_data,wi_db
    currchannel = bot_data[channelid]
    scanprompt = ""
    addwi = ""
    for msg in (currchannel.chat_history)[-3:]: #only consider the last 3 messages for wi
        scanprompt += msg + "\n"
    scanprompt = scanprompt.lower()
    for keystr, value in wi_db.items():
        rawkeys = keystr.lower().split(",")
        keys = [word.strip() for word in rawkeys]
        for k in keys:
            if k in scanprompt:
                addwi += f"\n{value}"
                break
    return addwi

def append_history(channelid,author,text):
    global bot_data
    currchannel = bot_data[channelid]
    if len(text) > 1000: #each message is limited to 1k chars
        text = text[:1000] + "..."
    msgstr = f"{author}:\n{text}"
    currchannel.chat_history.append(msgstr)
    print(f"{channelid} msg {msgstr}")

    if len(currchannel.chat_history) > 25: #limited to last 25 msgs
        currchannel.chat_history.pop(0)

def prepare_img_payload(channelid, prompt):
    payload = {
        "prompt": prompt,
        "sampler_name": "Euler a",
        "batch_size": 1,
        "n_iter": 1,
        "steps": 20,
        "cfg_scale": 7,
        "width": 512,
        "height": 512,
        "negative_prompt": "ugly, deformed, poorly, censor, blurry, lowres, malformed, watermark, duplicated, grainy, distorted, signature",
        "do_not_save_samples": True,
        "do_not_save_grid": True,
        "enable_hr": False,
        "eta": 0,
        "s_churn": 0,
        "s_tmax": 0,
        "s_tmin": 0,
        "s_noise": 1,
        "override_settings": {
            "sd_model_checkpoint": "imgmodel",
            "eta_noise_seed_delta": 0,
            "CLIP_stop_at_last_layers": 1,
            "ddim_discretize": "uniform",
            "img2img_fix_steps": False,
            "sd_hypernetwork": "None",
            "inpainting_mask_weight": 1,
            "initial_noise_multiplier": 1,
            "comma_padding_backtrack": 20
        }
    }
    return payload

def prepare_memory(channelid):
    global char_persona
    basememory = char_persona['basememory']
    intromemory = char_persona['intromemory']
    memory = basememory
    # inject world info here
    wi = prepare_wi(channelid)
    if wi!="":
        memory += f"[{client.user.display_name} Summarized Memory Database:{wi}]\n"
    memory += intromemory
    currchannel = bot_data[channelid]
    if currchannel.bot_override_memory!="":
        memory = currchannel.bot_override_memory
    return memory

def prepare_payload(channelid):
    global maxlen, args
    memory = prepare_memory(channelid)
    prompt = concat_history(channelid)
    basestops = ["\n###", "### ", "[END]", "[end]"]
    custom_name_stops = get_stoplist(channelid)
    stops = basestops + custom_name_stops
    payload = {
    "n": 1,
    "max_length": maxlen,
    "rep_pen": 1.07,
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 100,
    "top_a": 0,
    "typical": 1,
    "tfs": 1,
    "rep_pen_range": 320,
    "rep_pen_slope": 0.7,
    "sampler_order": [6,0,1,3,4,2,5],
    "min_p": 0,
    "genkey": "KCPP8888",
    "memory": memory,
    "prompt": prompt,
    "quiet": True,
    "trim_stop": True,
    "stop_sequence": stops,
    "use_default_badwordsids": False
    }

    return payload

def prepare_oai_payload(channelid):
    global maxlen, oai_model
    system_prompt = prepare_memory(channelid)
    user_prompt = concat_openai_history(channelid)
    return {
        "model": oai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": maxlen,
        "temperature": 0.8,
        "top_p": 0.9
    }

def oai_chat_endpoint(endpoint):
    trimmed = endpoint.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    if trimmed.endswith("/v1"):
        return trimmed + "/chat/completions"
    return trimmed + "/v1/chat/completions"

def post_oai_chat(endpoint, payload):
    headers = {}
    if oai_api_key:
        headers["Authorization"] = f"Bearer {oai_api_key}"
    return requests.post(oai_chat_endpoint(endpoint), json=payload, headers=headers)

def clean_endpoint(endpoint):
    return endpoint.strip().rstrip("/") if endpoint else ""

def is_oai_backend(endpoint):
    if not endpoint:
        return False
    lowered = endpoint.lower()
    return "/chat/completions" in lowered

def get_text_endpoint(currchannel):
    return clean_endpoint(currchannel.bot_override_text_backend or currchannel.bot_override_backend or (oai_endpoint if oai_chat_mode else submit_endpoint))

def get_vision_endpoint(currchannel):
    return clean_endpoint(currchannel.bot_override_vision_backend or currchannel.bot_override_backend or submit_endpoint)

def get_image_endpoint(currchannel):
    return clean_endpoint(currchannel.bot_override_image_backend or imggen_endpoint)

def clear_backend_overrides(currchannel):
    currchannel.bot_override_backend = ""
    currchannel.bot_override_text_backend = ""
    currchannel.bot_override_vision_backend = ""
    currchannel.bot_override_image_backend = ""

def describe_backend_overrides(currchannel):
    parts = []
    if currchannel.bot_override_backend:
        parts.append(f"legacy={currchannel.bot_override_backend}")
    if currchannel.bot_override_text_backend:
        parts.append(f"text={currchannel.bot_override_text_backend}")
    if currchannel.bot_override_vision_backend:
        parts.append(f"vision={currchannel.bot_override_vision_backend}")
    if currchannel.bot_override_image_backend:
        parts.append(f"image={currchannel.bot_override_image_backend}")
    return ", ".join(parts)

def set_backend_override(currchannel, key, value):
    normalized = clean_endpoint(value)
    if normalized.lower() in CLEAR_BACKEND_VALUES:
        normalized = ""
    if key == "url":
        currchannel.bot_override_backend = normalized
    elif key == "text":
        currchannel.bot_override_text_backend = normalized
    elif key == "vision":
        currchannel.bot_override_vision_backend = normalized
    elif key == "image":
        currchannel.bot_override_image_backend = normalized

def apply_backend_args(currchannel, args_text):
    text = args_text.strip()
    if text == "":
        clear_backend_overrides(currchannel)
        return "cleared"

    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    updates = {}
    for token in tokens:
        if "=" not in token:
            updates = {}
            break
        key, value = token.split("=", 1)
        key = key.lower().strip()
        if key not in ("url", "text", "vision", "image"):
            updates = {}
            break
        updates[key] = value

    if not updates:
        set_backend_override(currchannel, "url", text)
    else:
        for key, value in updates.items():
            set_backend_override(currchannel, key, value)

    return "set" if describe_backend_overrides(currchannel) else "cleared"

def apply_backend_options(currchannel, url="", text_url="", vision_url="", image_url=""):
    if not any([url, text_url, vision_url, image_url]):
        clear_backend_overrides(currchannel)
        return "cleared"

    if url:
        set_backend_override(currchannel, "url", url)
    if text_url:
        set_backend_override(currchannel, "text", text_url)
    if vision_url:
        set_backend_override(currchannel, "vision", vision_url)
    if image_url:
        set_backend_override(currchannel, "image", image_url)

    return "set" if describe_backend_overrides(currchannel) else "cleared"

def extract_bot_reply(response, is_oai_response):
    if response.status_code != 200:
        print(f"ERROR: response: {response}")
        return ""
    data = response.json()
    if is_oai_response:
        return data["choices"][0]["message"]["content"]
    return data["results"][0]["text"]

def trim_bot_name_prefix(text):
    bot_names = [client.user.display_name, client.user.name]
    cleaned = text.strip()
    for bot_name in bot_names:
        if not bot_name:
            continue
        pattern = r"^\s*(?:###\s*)?" + re.escape(bot_name) + r"\s*:\s*"
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
    return cleaned.strip()

def trim_end_delimiter(text):
    return re.split(r"\[END\]", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()

def prepare_vision_payload(b64img, channelid, reply_in_character): #two modes, if botdescribe is used, then the image is in character. otherwise, the description is neutral and HIDDEN from the user.
    global maxlen, args
    vision_prompt = "### Instruction:\nPlease describe the image in detail, and include transcriptions of any text if found.\n\n### Response:\n"
    if reply_in_character:
        memory = prepare_memory(channelid)
        vision_prompt = f"{memory}\n\n### Instruction:\nPlease describe the image in detail while keeping your personality completely in-character.\n\n### Response:\n"
    payload = {
    "n": 1,
    "max_length": maxlen,
    "rep_pen": 1.07,
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 100,
    "top_a": 0,
    "typical": 1,
    "tfs": 1,
    "rep_pen_range": 320,
    "rep_pen_slope": 0.7,
    "sampler_order": [6,0,1,3,4,2,5],
    "min_p": 0,
    "genkey": "KCPP8888",
    "memory": "",
    "images": [b64img],
    "prompt": vision_prompt,
    "quiet": True,
    "trim_stop": True,
    "stop_sequence": [
        "\n###",
        "### "
    ],
    "use_default_badwordsids": False
    }

    return payload

def detect_nsfw_text(input_text):
    import re
    pattern = r'\b(cock|ahegao|hentai|uncensored|lewd|cocks|deepthroat|deepthroating|dick|dicks|cumshot|lesbian|fuck|fucked|fucking|sperm|naked|nipples|tits|boobs|breasts|boob|breast|topless|ass|butt|fingering|masturbate|masturbating|bitch|blowjob|pussy|piss|asshole|dildo|dildos|vibrator|erection|foreskin|handjob|nude|penis|porn|vibrator|virgin|vagina|vulva|threesome|orgy|bdsm|hickey|condom|testicles|anal|bareback|bukkake|creampie|stripper|strap-on|missionary|clitoris|clit|clitty|cowgirl|fleshlight|sex|buttplug|milf|oral|sucking|bondage|orgasm|scissoring|railed|slut|sluts|slutty|cumming|cunt|faggot|sissy|anal|anus|cum|semen|scat|nsfw|xxx|explicit|erotic|horny|aroused|jizz|moan|rape|raped|raping|throbbing|humping|underage|underaged|loli|pedo|pedophile|prepubescent|shota|underaged)\b'
    matches = re.findall(pattern, input_text, flags=re.IGNORECASE)
    return True if matches else False

def is_bot_admin(user):
    return user.name.lower() == admin_name.lower()

async def require_admin(interaction):
    if is_bot_admin(interaction.user):
        return True
    await interaction.response.send_message("Only the bot admin can use this command.", ephemeral=True)
    return False

def get_channel_data(channelid):
    return bot_data.get(channelid)

async def require_whitelisted(interaction):
    currchannel = get_channel_data(interaction.channel_id)
    if currchannel:
        return currchannel
    await interaction.response.send_message("This channel is not whitelisted yet.", ephemeral=True)
    return None

def fallback_command_parts(message):
    if message.author == client.user or not message.clean_content.startswith("/"):
        return None, ""
    if client.user not in message.mentions and f'@{client.user.name}' not in message.clean_content and f'@{client.user.display_name}' not in message.clean_content:
        return None, ""
    command, _, rest = message.clean_content.partition(" ")
    rest = rest.replace(f'@{client.user.display_name}', '')
    rest = rest.replace(f'@{client.user.name}', '').strip()
    return command.lower(), rest

async def handle_fallback_bot_command(message):
    global maxlen

    command, args_text = fallback_command_parts(message)
    if not command:
        return False

    channelid = message.channel.id
    is_admin = is_bot_admin(message.author)

    if command == "/botwhitelist":
        if not is_admin:
            await message.channel.send("Only the bot admin can whitelist a channel.")
            return True
        if channelid not in bot_data:
            print(f"Add new channel: {channelid}")
            rtim = time.time() - 9999 #sleep first
            bot_data[channelid] = BotChannelData([],rtim)
            await message.channel.send("Channel added to the whitelist. Ping me to talk.")
        else:
            await message.channel.send("Channel already whitelisted previously. Please blacklist and then whitelist me here again.")
        return True

    if channelid not in bot_data:
        await message.channel.send("This channel is not whitelisted yet.")
        return True

    currchannel = bot_data[channelid]

    if command in ("/botblacklist", "/botmaxlen", "/botidletime", "/botfilteroff", "/botfilteron", "/botsavesettings", "/botmemory", "/botbackend"):
        if not is_admin:
            await message.channel.send("Only the bot admin can use this command.")
            return True

        if command == "/botblacklist":
            del bot_data[channelid]
            print(f"Remove channel: {channelid}")
            await message.channel.send("Channel removed from the whitelist, I will no longer reply here.")
        elif command == "/botmaxlen":
            try:
                oldlen = maxlen
                maxlen = int(args_text.split()[0])
                print(f"Maxlen: {channelid} to {maxlen}")
                await message.channel.send(f"Maximum response length changed from {oldlen} to {maxlen}.")
            except Exception:
                await message.channel.send("Sorry, the command failed.")
        elif command == "/botidletime":
            try:
                oldval = currchannel.bot_idletime
                currchannel.bot_idletime = int(args_text.split()[0])
                print(f"Idletime: {channelid} to {currchannel.bot_idletime}")
                await message.channel.send(f"Idle timeout changed from {oldval} to {currchannel.bot_idletime}.")
            except Exception:
                await message.channel.send("Sorry, the command failed.")
        elif command == "/botfilteroff":
            currchannel.bot_hasfilter = False
            await message.channel.send("Image prompts will no longer be filtered.")
        elif command == "/botfilteron":
            currchannel.bot_hasfilter = True
            await message.channel.send("Text-filter will be applied to image prompts.")
        elif command == "/botsavesettings":
            export_config()
            await message.channel.send("Bot config saved.")
        elif command == "/botmemory":
            currchannel.bot_override_memory = args_text
            print(f"BotMemory: {channelid} to {args_text}")
            if args_text == "":
                await message.channel.send("Bot memory override for this channel cleared.")
            else:
                await message.channel.send("New bot memory override set for this channel.")
        elif command == "/botbackend":
            status = apply_backend_args(currchannel, args_text)
            overrides = describe_backend_overrides(currchannel)
            print(f"BotBackend: {channelid} to {overrides}")
            if status == "cleared":
                await message.channel.send("Bot backend override for this channel cleared.")
            else:
                await message.channel.send(f"New bot backend override set for this channel: {overrides}.")
        return True

    if command == "/botsleep":
        currchannel.bot_reply_timestamp = time.time() - 9999
        await message.channel.send("Entering sleep mode. Ping me to wake me up again.")
    elif command == "/botstatus":
        print(f"Status channel: {channelid}")
        lastreq = int(time.time() - currchannel.bot_reply_timestamp)
        lockmsg = "busy generating a response" if busy.locked() else "awaiting any new requests"
        await message.channel.send(f"I am currently online and {lockmsg}. The last request from this channel was {lastreq} seconds ago.")
    elif command == "/botreset":
        currchannel.chat_history = []
        currchannel.bot_reply_timestamp = time.time() - 9999
        print(f"Reset channel: {channelid}")
        await message.channel.send("Cleared bot conversation history in this channel.")
    elif command == "/botdescribe":
        vision_backend = get_vision_endpoint(currchannel)
        if not vision_backend:
            await message.channel.send("Image description requires KAI_ENDPOINT or a vision backend override to be configured.")
            return True
        uploadedimg = None
        for attachment in message.attachments:
            if attachment.content_type and 'image' in attachment.content_type:
                print(f"Fetching image: {attachment.url}")
                uploadedimg = base64.b64encode(await attachment.read()).decode('utf-8')
                print("Image fetched")
                break
        if not uploadedimg:
            await message.channel.send("Sorry, no image was uploaded.")
        elif not busy.acquire(blocking=False):
            await message.channel.send("I am busy generating a response. Please try again shortly.")
        else:
            try:
                await message.channel.send("Attempting to describe the provided image, please wait.")
                async with message.channel.typing():
                    currchannel.bot_reply_timestamp = time.time()
                    payload = prepare_vision_payload(uploadedimg, channelid, "roleplay" in args_text.lower())
                    print(payload)
                    sep = get_vision_endpoint(currchannel)
                    print(f"Sending Request to {sep}")
                    response = requests.post(sep, json=payload)
                    result = response.json()["results"][0]["text"] if response.status_code == 200 else ""
                    if result != "":
                        append_history(channelid, message.author.display_name, f"(Attached an Image: {result})")
                        await message.channel.send(f"Image Description: {result}")
                    else:
                        await message.channel.send("Sorry, the image transcription failed!")
            finally:
                busy.release()
    elif command == "/botdraw":
        image_backend = get_image_endpoint(currchannel)
        if not image_backend:
            await message.channel.send("Image generation requires KAI_ENDPOINT or an image backend override to be configured.")
            return True
        genimgprompt = args_text
        if currchannel.bot_hasfilter and detect_nsfw_text(genimgprompt):
            await message.channel.send("Sorry, the image prompt filter prevents me from drawing this image.")
        elif not busy.acquire(blocking=False):
            await message.channel.send("I am busy generating a response. Please try again shortly.")
        else:
            try:
                await message.channel.send("I will attempt to draw your image. Please stand by.")
                async with message.channel.typing():
                    currchannel.bot_reply_timestamp = time.time()
                    print(f"Gen Img: {genimgprompt}")
                    payload = prepare_img_payload(channelid, genimgprompt)
                    response = requests.post(image_backend, json=payload)
                    result = ""
                    if response.status_code == 200:
                        imgs = response.json()["images"]
                        if imgs and len(imgs) > 0:
                            result = imgs[0]
                    else:
                        print(f"ERROR: response: {response}")
                    if result:
                        file = discord.File(io.BytesIO(base64.b64decode(result)),filename='drawimage.png')
                        await message.channel.send(file=file)
                    else:
                        await message.channel.send("Sorry, the image generation failed!")
            finally:
                busy.release()
    else:
        return False

    return True

@tree.command(name="botwhitelist", description="Whitelist this channel for ConcedoBot.")
async def botwhitelist(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    channelid = interaction.channel_id
    if channelid not in bot_data:
        print(f"Add new channel: {channelid}")
        rtim = time.time() - 9999 #sleep first
        bot_data[channelid] = BotChannelData([],rtim)
        await interaction.response.send_message("Channel added to the whitelist. Ping me to talk.")
    else:
        await interaction.response.send_message("Channel already whitelisted previously. Please blacklist and then whitelist me here again.")

@tree.command(name="botblacklist", description="Remove this channel from ConcedoBot's whitelist.")
async def botblacklist(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    channelid = interaction.channel_id
    if channelid in bot_data:
        del bot_data[channelid]
        print(f"Remove channel: {channelid}")
        await interaction.response.send_message("Channel removed from the whitelist, I will no longer reply here.")
    else:
        await interaction.response.send_message("This channel was not whitelisted.", ephemeral=True)

@tree.command(name="botmaxlen", description="Set the global maximum response length.")
@app_commands.describe(length="Maximum response length in tokens.")
async def botmaxlen(interaction: discord.Interaction, length: int):
    global maxlen
    if not await require_admin(interaction):
        return
    if not await require_whitelisted(interaction):
        return
    oldlen = maxlen
    maxlen = length
    print(f"Maxlen: {interaction.channel_id} to {length}")
    await interaction.response.send_message(f"Maximum response length changed from {oldlen} to {length}.")

@tree.command(name="botidletime", description="Set this channel's idle timeout in seconds.")
@app_commands.describe(seconds="Seconds before the bot enters idle mode.")
async def botidletime(interaction: discord.Interaction, seconds: int):
    if not await require_admin(interaction):
        return
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    oldval = currchannel.bot_idletime
    currchannel.bot_idletime = seconds
    print(f"Idletime: {interaction.channel_id} to {seconds}")
    await interaction.response.send_message(f"Idle timeout changed from {oldval} to {seconds}.")

@tree.command(name="botfilteroff", description="Disable the image prompt text filter in this channel.")
async def botfilteroff(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    currchannel.bot_hasfilter = False
    await interaction.response.send_message("Image prompts will no longer be filtered.")

@tree.command(name="botfilteron", description="Enable the image prompt text filter in this channel.")
async def botfilteron(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    currchannel.bot_hasfilter = True
    await interaction.response.send_message("Text-filter will be applied to image prompts.")

@tree.command(name="botsavesettings", description="Save whitelisted channels and bot settings to disk.")
async def botsavesettings(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    if not await require_whitelisted(interaction):
        return
    export_config()
    await interaction.response.send_message("Bot config saved.")

@tree.command(name="botmemory", description="Set or clear this channel's bot memory override.")
@app_commands.describe(prompt="Replacement memory prompt. Leave blank to clear the override.")
async def botmemory(interaction: discord.Interaction, prompt: str = ""):
    if not await require_admin(interaction):
        return
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    memprompt = prompt.strip()
    currchannel.bot_override_memory = memprompt
    print(f"BotMemory: {interaction.channel_id} to {memprompt}")
    if memprompt == "":
        await interaction.response.send_message("Bot memory override for this channel cleared.")
    else:
        await interaction.response.send_message("New bot memory override set for this channel.")

@tree.command(name="botbackend", description="Set or clear this channel's backend overrides.")
@app_commands.describe(
    url="Legacy text/vision backend URL. Leave all fields blank to clear overrides.",
    text_url="Text generation backend URL.",
    vision_url="Vision backend URL.",
    image_url="Image generation backend URL."
)
async def botbackend(interaction: discord.Interaction, url: str = "", text_url: str = "", vision_url: str = "", image_url: str = ""):
    if not await require_admin(interaction):
        return
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    status = apply_backend_options(currchannel, url, text_url, vision_url, image_url)
    overrides = describe_backend_overrides(currchannel)
    print(f"BotBackend: {interaction.channel_id} to {overrides}")
    if status == "cleared":
        await interaction.response.send_message("Bot backend override for this channel cleared.")
    else:
        await interaction.response.send_message(f"New bot backend override set for this channel: {overrides}.")

@tree.command(name="botsleep", description="Immediately put ConcedoBot to sleep in this channel.")
async def botsleep(interaction: discord.Interaction):
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    currchannel.bot_reply_timestamp = time.time() - 9999
    await interaction.response.send_message("Entering sleep mode. Ping me to wake me up again.")

@tree.command(name="botstatus", description="Show ConcedoBot's current status in this channel.")
async def botstatus(interaction: discord.Interaction):
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    print(f"Status channel: {interaction.channel_id}")
    lastreq = int(time.time() - currchannel.bot_reply_timestamp)
    lockmsg = "busy generating a response" if busy.locked() else "awaiting any new requests"
    await interaction.response.send_message(f"I am currently online and {lockmsg}. The last request from this channel was {lastreq} seconds ago.")

@tree.command(name="botreset", description="Clear this channel's conversation history and go to sleep.")
async def botreset(interaction: discord.Interaction):
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    currchannel.chat_history = []
    currchannel.bot_reply_timestamp = time.time() - 9999
    print(f"Reset channel: {interaction.channel_id}")
    await interaction.response.send_message("Cleared bot conversation history in this channel.")

@tree.command(name="botdescribe", description="Describe an uploaded image.")
@app_commands.describe(image="Image to describe.", roleplay="Reply in-character instead of neutrally.")
async def botdescribe(interaction: discord.Interaction, image: discord.Attachment, roleplay: bool = False):
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    vision_backend = get_vision_endpoint(currchannel)
    if not vision_backend:
        await interaction.response.send_message("Image description requires KAI_ENDPOINT or a vision backend override to be configured.")
        return
    if not image.content_type or 'image' not in image.content_type:
        await interaction.response.send_message("Sorry, no image was uploaded.")
        return
    if not busy.acquire(blocking=False):
        await interaction.response.send_message("I am busy generating a response. Please try again shortly.", ephemeral=True)
        return
    try:
        await interaction.response.defer(thinking=True)
        print(f"Fetching image: {image.url}")
        uploadedimg = base64.b64encode(await image.read()).decode('utf-8')
        print("Image fetched")
        channel = interaction.channel
        async with channel.typing():
            currchannel.bot_reply_timestamp = time.time()
            payload = prepare_vision_payload(uploadedimg, interaction.channel_id, roleplay)
            print(payload)
            sep = get_vision_endpoint(currchannel)
            print(f"Sending Request to {sep}")
            response = requests.post(sep, json=payload)
            result = ""
            if response.status_code == 200:
                result = response.json()["results"][0]["text"]
            else:
                print(f"ERROR: response: {response}")
            if result != "":
                append_history(interaction.channel_id, interaction.user.display_name, f"(Attached an Image: {result})")
                await interaction.followup.send(f"Image Description: {result}")
            else:
                await interaction.followup.send("Sorry, the image transcription failed!")
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send("Sorry, the image transcription failed!")
    finally:
        busy.release()

@tree.command(name="botdraw", description="Generate an image from a prompt.")
@app_commands.describe(prompt="Prompt to draw.")
async def botdraw(interaction: discord.Interaction, prompt: str):
    currchannel = await require_whitelisted(interaction)
    if not currchannel:
        return
    image_backend = get_image_endpoint(currchannel)
    if not image_backend:
        await interaction.response.send_message("Image generation requires KAI_ENDPOINT or an image backend override to be configured.")
        return
    genimgprompt = prompt.strip()
    if currchannel.bot_hasfilter and detect_nsfw_text(genimgprompt):
        await interaction.response.send_message("Sorry, the image prompt filter prevents me from drawing this image.")
        return
    if not busy.acquire(blocking=False):
        await interaction.response.send_message("I am busy generating a response. Please try again shortly.", ephemeral=True)
        return
    try:
        await interaction.response.defer(thinking=True)
        channel = interaction.channel
        async with channel.typing():
            currchannel.bot_reply_timestamp = time.time()
            print(f"Gen Img: {genimgprompt}")
            payload = prepare_img_payload(interaction.channel_id, genimgprompt)
            response = requests.post(image_backend, json=payload)
            result = ""
            if response.status_code == 200:
                imgs = response.json()["images"]
                if imgs and len(imgs) > 0:
                    result = imgs[0]
            else:
                print(f"ERROR: response: {response}")
            if result:
                print("Convert and upload file...")
                file = discord.File(io.BytesIO(base64.b64decode(result)),filename='drawimage.png')
                await interaction.followup.send(file=file)
            else:
                await interaction.followup.send("Sorry, the image generation failed!")
    finally:
        busy.release()

@client.event
async def on_ready():
    global ready_to_go
    import_config()
    await tree.sync()
    print("Logged in as {0.user}".format(client))
    ready_to_go = True


@client.event
async def on_message(message):
    global ready_to_go, bot_data, maxlen, args

    if not ready_to_go:
        return

    channelid = message.channel.id

    if await handle_fallback_bot_command(message):
        return

    # gate before nonwhitelisted channels
    if channelid not in bot_data:
       return

    # handle regular chat messages
    if message.author == client.user or message.clean_content.startswith(("/")):
        return

    currchannel = bot_data[channelid]

    append_history(channelid,message.author.display_name,message.clean_content)

    is_reply_to_bot = (message.reference and message.reference.resolved.author == client.user)
    mentions_bot = client.user in message.mentions
    contains_bot_name = (client.user.display_name.lower() in message.clean_content.lower()) or (client.user.name.lower() in message.clean_content.lower())
    is_reply_someone_else = (message.reference and message.reference.resolved.author != client.user)

    #get the last message we sent time in seconds
    secsincelastreply = time.time() - currchannel.bot_reply_timestamp

    if message.author.bot:
        currchannel.bot_botloopcount += 1
    else:
        currchannel.bot_botloopcount = 0

    if currchannel.bot_botloopcount > 4:
        return
    elif currchannel.bot_botloopcount == 4:
        if secsincelastreply < currchannel.bot_idletime:
            await message.channel.send("It appears that I am stuck in a conversation loop with another bot or AI. I will refrain from replying further until this situation resolves.")
        return

    if not is_reply_someone_else and (secsincelastreply < currchannel.bot_idletime or (is_reply_to_bot or mentions_bot or contains_bot_name)):
        if busy.acquire(blocking=False):
            try:
                async with message.channel.typing():
                    # keep awake on any reply
                    currchannel.bot_reply_timestamp = time.time()
                    sep = get_text_endpoint(currchannel)
                    use_oai = is_oai_backend(sep) or (sep == oai_endpoint and oai_chat_mode)
                    payload = prepare_oai_payload(channelid) if use_oai else prepare_payload(channelid)
                    print(payload)
                    print(f"Sending Request to {sep}")
                    if use_oai:
                        response = post_oai_chat(sep, payload)
                    else:
                        response = requests.post(sep, json=payload)
                    result = trim_bot_name_prefix(trim_end_delimiter(extract_bot_reply(response, use_oai)))

                    #no need to clean result, if all formatting goes well
                    if result!="":
                        append_history(channelid,client.user.display_name,result)
                        await message.channel.send(result)

            finally:
                busy.release()

try:
    client.run(os.getenv("BOT_TOKEN"))
except discord.errors.LoginFailure:
    print("\n\nBot failed to login to discord")
