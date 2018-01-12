import sys
import os
import asyncio
import json

from io import StringIO
from datetime import datetime
from discord import Game, InvalidArgument, HTTPException
from discord.ext import commands as c
from accounts import level
from helpers import is_owner, get_logger

VERSION = "2.1.1"

# Set up config variables
with open("config/config.json") as cfg:
    config = json.load(cfg)

token        = config["token"]
bot_name     = config["bot_name"]
bot_avatar   = config["bot_avatar"]
prefix       = config["command_prefix"]
log_file     = config["log_file"]
log_messages = config["log_messages"]
log_commands = config["log_commands"]
cmd_on_edit  = config["commands_on_edit"]

# Grab the blacklist
with open("db/blacklist.json") as bl:
    blacklist = json.load(bl)["users"]

log = get_logger(log_file)

# Set the bot and basic variables up
description="""
General purpose chat and administration bot.
"""
bot = c.Bot(c.when_mentioned_or(prefix), pm_help=True, description=description)
plugins = []
first_launch = True

# Helper function to load plugins
def load_plugins():
    for p in os.listdir("plugins"):
        if p.endswith(".py"):
            p = p.rstrip(".py")
            try:
                bot.load_extension(f'plugins.{p}')
                plugins.append(p)
            except Exception as error:
                exc = "{0}: {1}".format(type(error).__name__, error)
                log.warning(f"Failed to load plugin {p}:\n    {exc}")
    first_launch = False

# Helper function to change avatar and username
async def update_profile(name, picture):
    picture = f"config/{picture}"
    if os.path.isfile(picture):
        with open(picture, "rb") as avatar:
            await bot.edit_profile(avatar=avatar.read())
            log.info("Bot avatar set.")
        await bot.edit_profile(username=name)
        log.info("Bot name set.")

# Events
@bot.event
async def on_ready():
    date = datetime.now()
    # Set the bot's name and avatar
    if first_launch:
        load_plugins()
        try:
            await update_profile(bot_name, bot_avatar)
        except Exception as err:
            await log.warning("Unable to update the bot's profile: {err}.")

    # Load the account commands
    bot.load_extension("accounts")

    # Status header
    log.info("------------------------STATUS------------------------")
    log.info(f"{date}")
    log.info(f"Ispyra v{VERSION}")
    log.info(f"Logged in as {bot.user} ({bot.user.id})")
    log.info("Plugins: {0}".format(", ".join(plugins)))
    log.info("------------------------STATUS------------------------")

@bot.event
async def on_message(msg):
    # Log it
    if log_messages:
        log.info(f"[{msg.server} - #{msg.channel}] <{msg.author}>: {msg.content}")
    # Handle the commands
    await bot.process_commands(msg)

@bot.event
async def on_message_edit(old, new):
    if cmd_on_edit:
        await bot.process_commands(new)

@bot.event
async def on_command(cmd, ctx):
    # Log it home skittle
    if log_commands:
        command = f"{ctx.message.content}"
        user = f"{ctx.message.author}"
        location = f"[{ctx.message.server}] - #{ctx.message.channel}"
        log.info(f'[COMMAND] `{command}` by `{user}` in `{location}`')

@bot.event
async def on_command_error(err, ctx):
    channel = ctx.message.channel
    if isinstance(err, c.NoPrivateMessage):
        await bot.send_message(channel,
            "\U000026A0 This command is not available in DMs.")
    elif isinstance(err, c.CheckFailure):
        await bot.send_message(channel,
            "\U0001F6AB I'm sorry, I'm afraid I can't do that.")
    elif isinstance(err, c.MissingRequiredArgument):
        await bot.send_message(channel,
            "\U00002754 Missing argument(s).")
    elif isinstance(err, c.DisabledCommand):
        pass

@bot.event
async def on_server_join(srv):
    log.info(f"[JOIN] {srv.name}")

@bot.event
async def on_server_remove(srv):
    log.info(f"[LEAVE] {srv.name}")

# Global check for all commands
# This applies to EVERY command, even those in extensions
@bot.check
def allowed(ctx):
    return ctx.message.author.id not in blacklist

# Built-in commands
# Step the bot
@bot.command(name="quit")
@is_owner()
async def bot_quit():
    """Shut the bot down."""
    await bot.say("Shutting down...\n\U0001f44b")
    await bot.logout()

@bot.command(name="info")
async def bot_info():
    """Display information about the bot."""
    await bot.say("Ispyra {VERSION} (https://github.com/Ispira/Ispyra)")

@bot.command(name="status", aliases=["playing"])
async def bot_status(*, status: str):
    """Change the bot's 'playing' status.
    If the status is set to '!none' it will be disabled.
    """
    if status.lower() == "!none":
        game = None
    else:
        game = Game(name=status)
    await bot.change_status(game=game)
    await bot.say("\U00002705")

@bot.command()
async def ping():
    await bot.say("Pong!")

@bot.group(aliases=["plugins", "pl"], pass_context=True)
async def plugin(ctx):
    """Plugin handling.
    Running the command without arguments will list loaded plugins.
    """
    if ctx.invoked_subcommand is None:
        await bot.say(", ".join(plugins))

@plugin.command(name="load")
@is_owner()
async def plugin_load(name: str):
    """Load a plugin."""
    if name in plugins:
        await bot.say(f"\U000026A0 Plugin {name} is already loaded.")
        return

    if not os.path.isfile(f"plugins/{name}.py"):
        await bot.say(f"\U00002754 No plugin {name} exists.")
        return

    try:
        bot.load_extension(f"plugins.{name}")
        plugins.append(name)
        await bot.say(f"\U00002705 Plugin {name} loaded.")
    except Exception as error:
        exc = "{0}: {1}".format(type(error).__name__, error)
        await bot.say(f"\U00002757 Error loading {name}.\n```py\n{exc}\n```")

@plugin.command(name="unload")
@is_owner()
async def plugin_unload(name: str):
    """Unload a plugin."""
    if name not in plugins:
        await bot.say(f"\U000026A0 Plugin {name} is not loaded.")
        return

    try:
        bot.unload_extension(f"plugins.{name}")
        plugins.remove(name)
        await bot.say(f"\U00002705 Plugin {name} unloaded.")
    except:
        await bot.say(f"\U00002757 Error unloading {name}.")

@bot.command(name="eval", hidden=True, pass_context=True, enabled=False)
@is_owner()
async def evaluate(ctx, *, code: str):
    """Extremely unsafe eval command."""
    code = code.strip("` ")
    result = None
    try:
        result = eval(code)
        if asyncio.iscoroutine(result):
            result = await result
    except Exception as err:
        await bot.say(python.format(type(err).__name__ + ": " + str(error)))
        return

    await bot.say(f"```py\n{result}\n```")

@bot.command(name="exec", hidden=True, pass_context=True, enabled=False)
@is_owner()
async def execute(ctx, *, code: str):
    """If you thought eval was dangerous, wait'll you see exec!"""
    code = code.strip("```").lstrip("py")
    result = None
    env = {}
    env.update(locals())
    stdout = sys.stdout
    redirect = sys.stdout = StringIO()

    try:
        exec(code, globals(), env)
    except Exception as err:
        await bot.say(python.format(type(err).__name__ + ": " + str(error)))
    finally:
        sys.stdout = stdout

    await bot.say(f"```\n{redirect.getvalue()}\n```")

bot.run(token)
