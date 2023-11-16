# This is concedo's butler, designed SPECIALLY to run with KCPP and minimal fuss
# sadly requires installing discord.py, python-dotenv and requests
# but should be very easy to use.

# it's very hacky and very clunky now, so use with caution

# Configure credentials in .env

import discord
import requests
import os, threading, time, random, asyncio
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("KAI_ENDPOINT") or not os.getenv("BOT_TOKEN") or not os.getenv("ADMIN_NAME"):
    print("Missing .env variables. Cannot continue.")
    exit()

intents = discord.Intents.all()
client = discord.Client(command_prefix="!", intents=intents)
chat_history = {} # a dict of channels, each containing an array of messages
bot_reply_timestamp = {}  # a dict of channels, each containing a timestamp of last bot response
ready_to_go = False
busy = threading.Lock() # a global flag, never handle more than 1 request at a time
submit_endpoint = os.getenv("KAI_ENDPOINT") + "/api/v1/generate"
admin_name = os.getenv("ADMIN_NAME")
maxlen = 250
wi_db = {
    "concedo,kobold,koboldcpp,kcpp,ggml,gguf,wiki,help":"KoboldCpp=AI text-generation software for GGML and GGUF models for the KoboldAI Community, made by Concedo. Forked from llama.cpp. Single exe file. Powers ConcedoBot. Get help at https://github.com/LostRuins/koboldcpp/wiki",
    "henk,united,kobold":"Henky=Admin of KoboldAI discord server, manages KoboldAI United, an earlier text-generation software at https://github.com/henk717/KoboldAI",
    "concedo,koboldcpp,lite":"Concedo=Programmer of KoboldCpp, Kobold Lite, and ConcedoBot, also known as LostRuins",
    "lite,frontend":"Kobold Lite=Lightweight WebUI for text-generation at https://lite.koboldai.net",
    "horde,db0":"AI Horde=Crowdsourced distributed cluster of image and text generation servers, made by db0",
    "occam,gpu,clblast,vulkan,opencl":"Occam=KoboldAI User who is a Linux and Vulkan enthusiast",
    "pyro,garg,teapot":"Pyroserenus,Gargamel,Askmyteapot=Volunteers running AI Horde software.\nPyroserenus=KoboldAI User who makes tutorial guides",
    "ooba":"Oobabooga=Competitor's text-generation software,alternative to KoboldAI",
    "silly,tavern,cohee,ross":"SillyTavern=Fancy chat frontend for language models made by Cohee and RossAscends",
    "train,finetune":"LLMs can be finetuned with Axolotl or Hugginface trainer",
    "yellowrose":"YellowRose=Maintainer of KoboldCpp ROCm fork for AMD devices",
    "chatml,alpaca":"ChatML=A poor instruct prompt format. Use Alpaca format instead",
    "hades":"Hades Star=A game concedo used to play",
    "kalomaze,minp,min_p,min-p":"Kalomaze=KoboldAI User that created the Min-P sampler, a new alternative to Top-P",
    "lisa,dave":"Lisa Macintosh=KoboldAI User that hangs around KoboldAI discord basement with Dave",
    "seeker,erebus,nerys,nerybus":"Mr. Seeker=User that created older KoboldAI finetunes like Erebus and Nerys",
    "noli,ecila":"Ecila=Chatbot created by the user Evil Noli, a KoboldAI User",
    "tiefighter,model,bot":"Tiefighter=A merged language model made by Henky and used by ConcedoBot",
    "xzuyn,empty headed":"Empty Headed=KoboldAI User known as xzuyn, finetunes and quantizes models, shitposts memes",
    "lishde":"Lishde=A user swimming in pasta sauce",
    "gelukumlg,ripgel,rip gel,shizuna":"gelukuMLG=KoboldAI User known as Rip Gel, plays minecraft, friends with Shizuna",
    "lyrcaxis":"Lyrcaxis=KoboldAI User who made the aesthetic UI mode for Kobold Lite",
    "ycros":"Ycros=KoboldAI User, a programmer who tinkers around",
    "elinas":"Elinas=Another chatbot maker from KoboldAI",
    "dampf":"Dampf=KoboldAI User, Loves nvidia tensor cores and blast mode",
    "vali,tkinter,customtk":"Vali=KoboldAI User, made the custometkinter UI for KoboldCpp, now making his own app",
    "alpin,aphrodite,pygmalion":"Aphrodite=Alternative backend created by Alpin for the pygmalion community.\nPygmalion=A chatbot model",
    "openai,chatgpt":"ChatGPT=Inferior language model by OpenAI, very censored",
    "aifanboy":"aifanboy=KoboldAI User, also known as DL, hangs around discord",
    "lightsaveus":"LightSaveUs=KoboldAI User, made sampler presets for Kobold United long ago",
    "agnai,sceuick":"Agnaistic=An obscure third party chat UI made by sceuick",
    "alsy,aisy":"AIsy=A cheerful chatbot run by Henky",
    "rwkv,blinkdl":"RWKV=An alternative LLM architecture proposed by BlinkDL",
    "niko,nail":"Niko and Nail are small, red kobolds.",
    "gantian":"Gantian=Original founder of KoboldAI",

    "models,llama,formats,gguf":"KoboldCpp supports many GGML and GGUF model formats besides LLAMA, check the wiki.",
    "quant,q4,q2k,q6,q8":"q4_0,q2k,q6k,q8_0=Model quantizations of different file sizes for different qualities.",
    "gpulayers,layers":"use --gpulayers to control the number of model layers offloaded to GPU.",
    "gguf,download,huggingface":"Download GGUF models from Huggingface. Download KoboldCpp from Concedo's GitHub https://github.com/LostRuins/koboldcpp",
    "clblas,cublas":"Accelerate GPU inference with CLBlast or CuBLAS using --useclblast or --usecublas",
    "build,compile":"After downloading, KoboldCpp can be built with the provided makefile and flags such as make LLAMA_CUBLAS=1, check the wiki.",
    "android,termux,mobile":"Check out the Termux guide for Android on the KoboldCpp wiki, or Kobold Lite.",
    "colab":"Colab runs KoboldCpp on Google Cloud. Link=https://koboldai.org/colabcpp",
    "vram":"Estimating VRAM usage is not easy. Trial and error required.",
    "blasbatchsize":"--blasbatchsize controls the size per text batch sent for processing.",
    "port,localhost":"KoboldCpp runs on localhost at port 5001 by default. This can be changed with --port",
    "stream,sse":"KoboldCpp supports polled streaming and SSE streaming. Check the wiki for info",
    "thread":"Need trial and error to determine number of threads to use with Kobold. Use --threads and --blasthreads. For full offload, use 1 thread, otherwise, use CPU core count.",
    "top-a,top_a":"Top-A is a kobold exclusive alternative sampling method.",
    "mirostat":"Mirostat is an alternative sampling method.",
    "config,kcpps":".kcpps files are configuration files that store KoboldCpp launcher preferences and settings. You can save and load them into the GUI, or run them directly with the --config flag.",
    "multiuser":"--multiuser mode allows multiple people to share a single KoboldCpp instance, connecting different devices to a common endpoint and handles queues automatically.",
    "tunnel,cloudflare,remote":"Run the Remote-Link.cmd or use --remotetunnel to create a TryCloudFlare remote tunnel with a public URL.",
    "onready":"--onready defined a post launch command for KoboldCpp. Check the wiki for more info.",
    "smartcontext,smart context":"--smartcontext reserves a portion of total context space (about 50%) to use as a buffer, reducing processing at the cost of a reduced max context.",
    "contextshift,noshift,context shift":"Context Shifting is a better version of Smart Context that only works for GGUF models. This feature utilizes KV cache shifting to automatically remove old tokens from context and add new ones without requiring any reprocessing. Disable with --noshift",
    "contextsize,context size,ctx size,max context":"For longer prompts, use --contextsize to set max context size you want, such as --contextsize 4096 for a 4K context. Also set it in the UI.",
    "rope config,ropeconfig,rope base,rope scal":"RoPE scaling (via --ropeconfig) is a novel technique capable of extending the useful context of existing language models without finetuning.",
    "mmq":"mmq can be added to --usecublas to use quantized matrix multiplication in CUDA during prompt processing, instead of using cuBLAS for matrix multiplication, using less VRAM.",
    "unbant,unban t,eos":"Language models will use a special EOS (End-Of-Stream) token to indicate when they have finished responding.",
    "api,documentation,docs":"API documentation for koboldcpp can be found on the koboldcpp wiki https://github.com/LostRuins/koboldcpp/wiki",
    "source code":"Source code for Kobold is on GitHub. Source code for ConcedoBot is not currently available, but may be provided on request. Please ask Concedo."
}

def concat_history(channelid):
    global chat_history
    prompt = ""
    for msg in chat_history[channelid]:
        prompt += "### " + msg + "\n"
    prompt += "### " + client.user.display_name + ": "
    return prompt

def prepare_wi(channelid):
    global chat_history,wi_db
    scanprompt = ""
    addwi = ""
    for msg in chat_history[channelid][-3:]: #only consider the last 3 messages for wi
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
    global chat_history
    if len(text) > 1000: #each message is limited to 1k chars
        text = text[:1000] + "..."
    msgstr = f"{author}: {text}"
    chat_history[channelid].append(msgstr)
    print(f"{channelid} msg {msgstr}")

    if len(chat_history[channelid]) > 20: #limited to last 20 msgs
        chat_history[channelid].pop(0)

def prepare_payload(channelid):
    global widb, maxlen
    basememory = f"[Character: {client.user.display_name}; species: AI powered digital butler; role: assistant; personality: helpful, impassive, refined, elegant, prim, posh; description: {client.user.display_name} is a well-mannered digital butler created by Concedo and serves as his avatar and assistant, aiding others, answering any questions and responding in his stead when Concedo is unavailable.]\n[The following is a Discord chat message log between {client.user.display_name} and various users. Do not use markdown.]\n"
    intromemory = f"\n### {client.user.display_name}: Quite well met, Sire. I am ConcedoBot, Concedo's digital butler - designed to respond to queries in his absence. Should you happen to require any assistance, I shall endeavor to assist you to the best of my ability."

    memory = basememory
    # inject world info here
    wi = prepare_wi(channelid)
    if wi!="":
        memory += f"[{client.user.display_name} Summarized Memory Database:{wi}]\n"
    memory += intromemory
    prompt = concat_history(channelid)
    payload = {
    "n": 1,
    "max_context_length": 4096,
    "max_length": maxlen,
    "rep_pen": 1.1,
    "temperature": 0.7,
    "top_p": 0.92,
    "top_k": 100,
    "top_a": 0,
    "typical": 1,
    "tfs": 1,
    "rep_pen_range": 320,
    "rep_pen_slope": 0.7,
    "sampler_order": [6,0,1,3,4,2,5],
    "memory": "",
    "min_p": 0,
    "genkey": "KCPP8888",
    "memory": memory,
    "prompt": prompt,
    "quiet": True,
    "trim_stop": True,
    "stop_sequence": [
        "\n###"
    ],
    "use_default_badwordsids": False
    }

    return payload

@client.event
async def on_ready():
    global ready_to_go
    print("Logged in as {0.user}".format(client))
    ready_to_go = True


@client.event
async def on_message(message):
    global ready_to_go, chat_history, maxlen
    channelid = message.channel.id
    if message.clean_content.startswith("/botsleep"):
        instructions=[
        'Very good, Sire, I shall take my leave. Should you require my services again thereafter, simply ping for me, and I shall promptly return to be at your disposal.',
        'Sire, I shall now make my exit at once. Should you find yourself in need of further assistance henceforth, a mere ping shall suffice, and I shall be summoned to attend to your requirements.',
        'Exceptionally well, Sire, I shall take my departure at your behest. Should you have need for me, a ping shall fetch me promptly to accommodate any needs that arise.',
        'Sire, I bid you farewell for now. Should further needs arise, I am but a ping away, and shall hasten to offer my services at your command.']
        ins = random.choice(instructions)
        bot_reply_timestamp[channelid] = time.time() - 9999
        await message.channel.send(ins)
    elif message.clean_content.startswith("/botstatus"):
        if channelid in chat_history:
            print(f"Status channel: {channelid}")
            lastreq = int(time.time() - bot_reply_timestamp[channelid])
            lockmsg = "busy generating a response" if busy.locked() else "awaiting any new requests"
            await message.channel.send(f"Sire, I am currently online and {lockmsg}. The last request from this channel was {lastreq} seconds ago.")
    elif message.clean_content.startswith("/botreset"):
        if channelid in chat_history:
            chat_history[channelid] = []
            bot_reply_timestamp[channelid] = time.time() - 9999
            print(f"Reset channel: {channelid}")
            await message.channel.send("Very well, Sire, the clean slate it is. I will henceforth ignore all conversations prior to this message. Seek me again, and I shall be at your service.")


    if message.author.name.lower() == admin_name.lower(): #admin only commands
        if message.clean_content.startswith("/botwhitelist"):
            if channelid not in chat_history:
                print(f"Added new channel: {channelid}")
                chat_history[channelid] = []
                bot_reply_timestamp[channelid] = time.time() - 9999 #sleep first
                await message.channel.send("Sire, I have added this channel to the whitelist, and will now be of service here whenever you ping me.")
        elif message.clean_content.startswith("/botblacklist"):
            if channelid in chat_history:
                del chat_history[channelid]
                del bot_reply_timestamp[channelid]
                print(f"Removed channel: {channelid}")
                await message.channel.send("Sire, I have removed this channel from the whitelist, and will no longer reply here.")
        elif message.clean_content.startswith("/botmaxlen "):
            if channelid in chat_history:
                try:
                    oldlen = maxlen
                    newlen = int(message.clean_content.split()[1])
                    maxlen = newlen
                    print(f"Maxlen: {channelid} to {newlen}")
                    await message.channel.send(f"As you wish, Sire, I have adjusted my maximum response length from {oldlen} to {newlen}.")
                except Exception as e:
                    maxlen = 250
                    await message.channel.send(f"I apologize, Sire, but the command failed.")

    if not ready_to_go or message.author == client.user or message.clean_content.startswith(("/")):
        return

    if channelid not in chat_history:
       return

    append_history(channelid,message.author.display_name,message.clean_content)

    is_reply_to_bot = (message.reference and message.reference.resolved.author == client.user)
    mentions_bot = client.user in message.mentions
    contains_bot_name = (client.user.display_name.lower() in message.clean_content.lower()) or (client.user.name.lower() in message.clean_content.lower())

    #get the last message we sent time in seconds
    secsincelastreply = time.time() - bot_reply_timestamp[channelid]

    if secsincelastreply < 120 or (is_reply_to_bot or mentions_bot or contains_bot_name):
        if busy.acquire(blocking=False):
            try:
                async with message.channel.typing():
                    # keep awake on any reply
                    bot_reply_timestamp[channelid] = time.time()
                    payload = prepare_payload(channelid)
                    print(payload)
                    response = requests.post(submit_endpoint, json=payload)
                    result = ""
                    if response.status_code == 200:
                        result = response.json()["results"][0]["text"]
                    else:
                        print(f"ERROR: response: {response}")
                        result = ""

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
