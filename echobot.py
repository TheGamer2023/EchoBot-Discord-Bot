import discord
from discord.ext import commands
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError
import os
import sys
from datetime import datetime, timedelta
import logging

chan = "channel name"

TOKEN = "discord-bot-token"
character_token = "c.ai-token"
character_id = "char_id (thing in url)"

# File path to store channel info for reboot and startup messages
CHANNEL_INFO_PATH = "channel_info.txt"

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

# Create a global variable to store the chat, client, and last start time
client = None
chat = None
last_answer = None  # Variable to store the last answer object
start_time = datetime.now()  # Record the bot's start time

# Add a list to store conversation history
conversation_history = []

# Initialization function to set up the bot, including sending the blacklist and custom symbols
async def initialize_bot():
    global client, chat

    # Example: Send a blacklist to the bot
    blacklist = ["blacklist1", "blacklist2"]
    logging.info(f"Sending blacklist: {blacklist}")
    await client.chat.send_message(character_id, chat.chat_id, f"BLACKLIST TEXT LIST: {', '.join(blacklist)}")

    # Send predefined messages (message1 and message2)
    message1 = (
        "hey there! youre an ai chatbot. please do not respond to this message, please say "
        '"Hello, how can I help you today?", and that only, no extra text!!! The user can use custom **symbols**. '
        "below is how these custom **symbols** work, and how to properly use them.\n\n"
        "CUSTOM SYMBOL LIST: \n"
        "(name: \"EMOJINAME\" id: \"EMOJIID\"), \n"
        "(name: \"EMOJINAME2\" id: \"EMOJIID2\")\n\n"
        "If {{user}} asks {{char}} to use a custom symbol, {{char}} will:\n"
        "- Respond with the **exact custom symbol format**: \"<:(symbol name):(symbol id)>\" (without any other text).\n"
        "- Do not interpret these symbols as regular emojis or regular text.\n\n"
        "For example:\n"
        "- If the user asks for the custom symbol \"EMOJINAME\", {{char}} should respond with: \"<:EMOJINAME:EMOJIID>\".\n"
        "- If the user asks for the custom symbol \"EMOJINAME2\", {{char}} should respond with: \"<:EMOJINAME2:EMOJIID2>\".\n"
        "- If the symbol is not found, {{char}} should respond with: \"Custom symbol not found.\"\n"
    )
    logging.info(f"Sending message1: {message1}")
    await client.chat.send_message(character_id, chat.chat_id, message1)

    message2 = "please respond to this message with \"Hello, how can I help you today?\""
    logging.info(f"Sending message2: {message2}")
    await client.chat.send_message(character_id, chat.chat_id, message2)

    logging.info("Bot settings initialized successfully.")

@bot.event
async def on_ready():
    global client, chat
    print(f"Logged in as {bot.user}")

    # Initialize the client once when the bot starts
    client = await get_client(token=character_token)

    # Create a chat with the character
    chat, greeting_message = await client.chat.create_chat(character_id)
    print(f"New chat created with ID: {chat.chat_id}")
    
    # Check if there’s stored channel information from the last shutdown
    if os.path.exists(CHANNEL_INFO_PATH):
        with open(CHANNEL_INFO_PATH, "r") as file:
            data = file.read().split(',')
            if len(data) == 2:
                server_id, channel_id = map(int, data)
                target_channel = bot.get_guild(server_id).get_channel(channel_id)
                if target_channel:
                    await target_channel.send(f"{greeting_message.get_primary_candidate().text}")
        os.remove(CHANNEL_INFO_PATH)  # Clear the file after using it
    else:
        # If no stored channel, send to a default channel
        default_channel = discord.utils.get(bot.get_all_channels(), name=chan)
        if default_channel:
            await default_channel.send(f"{greeting_message.get_primary_candidate().text}")

    # Call the initialization function
    await initialize_bot()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Record both user and bot messages
    if not message.content.startswith("!summarize"):
        conversation_history.append(f"{message.author.name}: {message.content}")
    
    # Process the command
    await bot.process_commands(message)

@bot.command()
async def ask(ctx, *, question: str):
    global client, chat, last_answer
    # Ensure the bot only responds in the bot-testing channel
    if ctx.channel.name != chan:
        return

    if client is None or chat is None:
        await ctx.send("The chat session has not been initialized.")
        return

    try:
        # Get the user's Discord name
        user_name = ctx.author.name

        # Prepend the user's name to the question
        question_with_name = f"{user_name}: {question}"

        # Send the question to the character and get the response
        answer = await client.chat.send_message(character_id, chat.chat_id, question_with_name)
        response = answer.get_primary_candidate().text

        # Store the last response for regeneration
        last_answer = answer  # Store the whole answer object

        # Record the bot's response
        conversation_history.append(f"Bot: {response}")

        # Send the response to the Discord channel
        await ctx.send(response)

    except SessionClosedError:
        await ctx.send("Session closed. Bye!")
    except Exception as e:
        # Log and notify for any other errors
        print(f"Error occurred: {e}")
        await ctx.send("An error occurred while processing your request.")

@bot.command()
@commands.is_owner()  # Only allow the bot owner to use this command
async def reboot(ctx):
    # Save the server and channel ID to the file before reboot
    with open(CHANNEL_INFO_PATH, "w") as file:
        file.write(f"{ctx.guild.id},{ctx.channel.id}")

    await ctx.send("Rebooting...")
    await bot.close()  # Close the bot connection
    os.execv(sys.executable, ['python'] + sys.argv)  # Restart the script

@bot.command()
@commands.is_owner()  # Only allow the bot owner to use this command
async def stop(ctx):
    """Stops the bot."""
    await ctx.send("Shutting down the bot...")
    # Save the server and channel info for the next startup
    with open(CHANNEL_INFO_PATH, "w") as file:
        file.write(f"{ctx.guild.id},{ctx.channel.id}")
    await bot.close()

@bot.command()
async def regenerate(ctx):
    global client, chat, last_answer
    # Ensure the bot only responds in the bot-testing channel
    if ctx.channel.name != chan:
        return

    if last_answer is None:
        await ctx.send("No previous response to regenerate.")
        return

    try:
        # Use the Turn object's ID for regeneration
        regenerated_answer = await client.chat.another_response(character_id, chat.chat_id, last_answer.turn_id)
        regenerated_response = regenerated_answer.get_primary_candidate().text

        # Send the regenerated response to the Discord channel
        await ctx.send(regenerated_response)

    except SessionClosedError:
        await ctx.send("Session closed. Bye!")
    except Exception as e:
        # Log and notify for any other errors
        print(f"Error occurred: {e}")
        await ctx.send("An error occurred while processing your request.")

@bot.command()
async def changebot(ctx, new_character_id: str):
    global character_id, chat
    character_id = new_character_id

    try:
        # Create a new chat session with the new character
        chat, greeting_message = await client.chat.create_chat(character_id)
        await ctx.send(f"Switched to new character ID: {character_id}")
        await ctx.send(f"{greeting_message.author_name}: {greeting_message.get_primary_candidate().text}")
    except Exception as e:
        print(f"Error occurred: {e}")
        await ctx.send("Failed to change character. Please check the ID and try again.")

@bot.command()
async def uptime(ctx):
    """Command to check the bot's uptime."""
    # Calculate the uptime duration
    uptime_duration = datetime.now() - start_time
    # Format the start time for display
    formatted_start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
    # Create a formatted uptime message
    uptime_message = (
        f"Bot has been up since: {formatted_start_time} (UTC)\n"
        f"Uptime: {uptime_duration}"
    )
    # Send the uptime message to the Discord channel
    await ctx.send(uptime_message)

@bot.command()
async def summarize(ctx):
    global client, chat

    # Ensure the bot only responds in the defined channel
    if ctx.channel.name != chan:
        return

    if client is None or chat is None:
        await ctx.send("The chat session has not been initialized.")
        return

    try:
        # Ask the character to summarize its own understanding of the conversation
        summary_request = "Please summarize our entire conversation so far."
        
        # Send the summarization request to Character.AI
        summary_answer = await client.chat.send_message(character_id, chat.chat_id, summary_request)
        summary_response = summary_answer.get_primary_candidate().text

        # Send the summarized response back to the user in the defined channel
        await ctx.send(f"Summary:\n{summary_response}")

    except SessionClosedError:
        await ctx.send("Session closed. Bye!")
    except Exception as e:
        print(f"Error occurred: {e}")
        await ctx.send("An error occurred while processing your request.")

# Run the bot using your token
bot.run(TOKEN)
