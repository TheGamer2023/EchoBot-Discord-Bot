import discord
from discord.ext import commands
from discord import app_commands  # For slash commands
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError
import os
import sys
from datetime import datetime
import logging

# Constants
CHAN = "your_channel_name_here"  # Replace with your channel name
TOKEN = "your_discord_bot_token_here"  # Replace with your Discord bot token
CHARACTER_TOKEN = "your_character_token_here"  # Replace with your Character.AI token
CHARACTER_ID = "your_character_id_here"  # Replace with your Character.AI character ID
CHANNEL_INFO_PATH = "channel_info.txt"

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Bot initialization
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables
client = None
chat = None
last_answer = None  # Variable to store the last answer object
start_time = datetime.now()  # Record the bot's start time

# Initialization function to set up the bot, including sending the blacklist and custom symbols
async def initialize_bot():
    global client, chat

    # Example: Send a blacklist to the bot
    # REPLACE WITH BLACKLISTED TEXT!! (bot may accidentally say blacklisted text, but i have tried to prevent that)
    blacklist = ["blacklist1", "blacklist2"]
    logging.info(f"Sending blacklist: {blacklist}")
    await client.chat.send_message(CHARACTER_ID, chat.chat_id, f"BLACKLIST TEXT LIST: {', '.join(blacklist)}")

    # Send predefined messages
    message1 = (
        "hey there! youre an ai chatbot. please do not respond to this message, please say "
        '"Hello, how can I help you today?", and that only, no extra text!!! The user can use custom **symbols**. '
        "below is how these custom **symbols** work, and how to properly use them.\n\n"
        "CUSTOM SYMBOL LIST: \n"
        "(name: \"custom_symbol_name_1\" id: \"your_symbol_id_here\"), \n"
        "(name: \"custom_symbol_name_2\" id: \"your_symbol_id_here\")\n\n"
        "If {{user}} asks {{char}} to use a custom symbol, {{char}} will:\n"
        "- Respond with the **exact custom symbol format**: \"<:(symbol name):(symbol id)>\" (without any other text).\n"
        "- Do not interpret these symbols as regular emojis or regular text.\n\n"
        "For example:\n"
        "- If the user asks for the custom symbol \"custom_symbol_name_1\", {{char}} should respond with: \"<:custom_symbol_name_1:your_symbol_id_here>\".\n"
        "- If the user asks for the custom symbol \"custom_symbol_name_2\", {{char}} should respond with: \"<:custom_symbol_name_2:your_symbol_id_here>\".\n"
        "- If the symbol is not found, {{char}} should respond with: \"Custom symbol not found.\"\n"
    )
    logging.info(f"Sending message1: {message1}")
    await client.chat.send_message(CHARACTER_ID, chat.chat_id, message1)

    message2 = "please respond to this message with \"Hello, how can I help you today?\""
    logging.info(f"Sending message2: {message2}")
    await client.chat.send_message(CHARACTER_ID, chat.chat_id, message2)

    logging.info("Bot settings initialized successfully.")

@bot.event
async def on_ready():
    global client, chat
    logging.info(f"Logged in as {bot.user}")

    # Set the bot's rich presence (activity)
    activity = discord.Activity(type=discord.ActivityType.competing, name="being the best bot! ^v^")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Initialize the client once when the bot starts
    client = await get_client(token=CHARACTER_TOKEN)

    # Create a chat with the character
    chat, greeting_message = await client.chat.create_chat(CHARACTER_ID)
    logging.info(f"New chat created with ID: {chat.chat_id}")

    # Initialize bot settings (blacklist, messages)
    await initialize_bot()

    # Check if there’s stored channel information from the last shutdown
    if os.path.exists(CHANNEL_INFO_PATH):
        with open(CHANNEL_INFO_PATH, "r") as file:
            data = file.read().split(',')
            if len(data) == 2:
                server_id, channel_id = map(int, data)
                target_channel = bot.get_guild(server_id).get_channel(channel_id)
                if target_channel:
                    await target_channel.send(greeting_message.get_primary_candidate().text)
        os.remove(CHANNEL_INFO_PATH)  # Clear the file after using it
    else:
        # If no stored channel, send to a default channel
        default_channel = discord.utils.get(bot.get_all_channels(), name=CHAN)
        if default_channel:
            await default_channel.send(greeting_message.get_primary_candidate().text)

    # Force sync of commands after bot is ready
    await bot.tree.sync()  # Explicitly sync commands


@bot.tree.command(name="ask")
async def ask(interaction: discord.Interaction, question: str):
    """Send a message to the Character.AI bot and get a response."""
    global client, chat
    if chat is None:
        await interaction.response.send_message("The chat session has not been initialized.")
        return

    try:
        # Acknowledge the interaction to keep it open
        await interaction.response.defer()

        user_name = interaction.user.name
        question_with_name = f"{user_name}: {question}"

        # Send the user's question to the Character.AI bot and get the response
        answer = await client.chat.send_message(CHARACTER_ID, chat.chat_id, question_with_name)
        response = answer.get_primary_candidate().text

        # Send the final response back
        await interaction.followup.send(f"**You asked**: {question}\n\n**Bot says**: {response}")

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        # Notify the user if an error occurs
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing your request.")
        else:
            await interaction.followup.send("An error occurred while processing your request.")

@bot.tree.command(name="uptime")
async def uptime(interaction: discord.Interaction):
    """Check the bot's uptime."""
    uptime_duration = datetime.now() - start_time
    formatted_start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
    uptime_message = (
        f"Bot has been up since: {formatted_start_time} (UTC)\n"
        f"Uptime: {uptime_duration}"
    )
    await interaction.response.send_message(uptime_message)

@bot.tree.command(name="reboot")
@commands.is_owner()  # Only allow the bot owner to use this command
async def reboot(interaction: discord.Interaction):
    """Restarts the bot."""
    try:
        # Save the server and channel ID to the file before reboot
        with open(CHANNEL_INFO_PATH, "w") as file:
            file.write(f"{interaction.guild.id},{interaction.channel.id}")

        # Acknowledge the command to prevent a timeout
        await interaction.response.send_message("Rebooting...")

        # Close the bot connection
        await bot.close()

        # Restart the bot process
        os.execv(sys.executable, ['python'] + sys.argv)  # Restart the script
    except Exception as e:
        await interaction.response.send_message(f"An error occurred while rebooting: {e}")

@bot.tree.command(name="stop")
@commands.is_owner()  # Only allow the bot owner to use this command
async def stop(interaction: discord.Interaction):
    """Stops the bot."""
    await interaction.response.send_message("Shutting down the bot...")
    # Save the current channel information for the next startup
    with open(CHANNEL_INFO_PATH, "w") as file:
        file.write(f"{interaction.guild.id},{interaction.channel.id}")
    await bot.close()


# Run the bot
bot.run(TOKEN)
