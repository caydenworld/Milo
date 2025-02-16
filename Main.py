import discord
import os
from discord.ext import commands
import requests
import random
import json
import time
from openai import OpenAI
from eight_ball_answers import eight_ball_answers
from dotenv import load_dotenv
import re
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from discord.ui import InputText, Select, View, Modal, Button
from discord.utils import get
import youtube_dl
import asyncio

load_dotenv()

# Files for storage
CACHE_FILE = "ai_cache.json"
POSTCARD_FILE = "postcards.json"

# Set intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True


# Initialize bot
bot = commands.Bot(command_prefix=';', intents=intents, help_command=None)

SETTINGS_FILE = "Settings.json"

async def send_dm_to_staff(guild, message):
    log_channel = discord.utils.get(guild.text_channels, name="milo-mod-logs")

    if not log_channel:
        print("Log channel 'milo-mod-logs' not found!")
        await message.send("Please use *;modsetup* to correctly setup your server.")
        return

    await log_channel.send(message)

def load_settings():
    """Loads settings from Settings.json or returns an empty dictionary if the file doesn't exist."""
    if not os.path.exists(SETTINGS_FILE):
        return {}

    with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}  # Return an empty dictionary if the JSON is malformed

def save_settings(settings):
    """Saves the given settings dictionary to Settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(settings, file, indent=4)

def update_setting(guild_id: str, setting_key: str, setting_value):
    """Updates a specific setting for a guild while preserving existing settings."""
    settings = load_settings()

    # Ensure the guild has an entry
    if guild_id not in settings:
        settings[guild_id] = {}

    # Update the specific setting
    settings[guild_id][setting_key] = setting_value

    # Save the updated settings
    save_settings(settings)



def load_currency():
    try:
        with open("currency.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# Save currency data
def save_currency(data):
    with open("currency.json", "w") as f:
        json.dump(data, f, indent=4)


# Get user balance (per server)
def get_balance(guild_id, user_id):
    data = load_currency()
    return data.get(str(guild_id), {}).get(str(user_id), 0)


# Add money to a user (per server)
def add_money(guild_id, user_id, amount):
    data = load_currency()
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data:
        data[guild_id] = {}
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = 0

    data[guild_id][user_id] += amount
    save_currency(data)


# Remove money from a user (per server)
def remove_money(guild_id, user_id, amount):
    data = load_currency()
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data or user_id not in data[guild_id] or data[guild_id][
            user_id] < amount:
        return False  # Not enough money

    data[guild_id][user_id] -= amount
    save_currency(data)
    return True


def load_cache():
    """Load AI response cache from a JSON file"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            return json.load(file)
    return {}


def save_cache(cache):
    """Save AI response cache to a JSON file"""
    with open(CACHE_FILE, "w") as file:
        json.dump(cache, file)


def load_postcards():
    """Load postcards data from a JSON file"""
    if os.path.exists(POSTCARD_FILE):
        with open(POSTCARD_FILE, "r") as file:
            return json.load(file)
    return {}


def save_postcards(postcards):
    """Save postcards data to a JSON file"""
    with open(POSTCARD_FILE, "w") as file:
        json.dump(postcards, file)


def read_user_data():
    try:
        with open('user_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# Function to save user data to the JSON file
def save_user_data(data):
    with open('user_data.json', 'w') as f:
        json.dump(data, f, indent=4)


# Function to update XP and level for a user
async def update_xp(message, user_id, xp_earned):
    data = read_user_data()

    if user_id not in data:
        data[user_id] = {"xp": 0, "level": 1}

    data[user_id]["xp"] += xp_earned

    # Check if the user leveled up
    xp_to_next_level = data[user_id][
        "level"] * 100  # Level up at 100 XP per level
    if data[user_id]["xp"] >= xp_to_next_level:
        data[user_id]["level"] += 1
        data[user_id]["xp"] = 0  # Reset XP after leveling up
        await message.reply(f"🥳 Congrats! You leveled up to level {data[user_id]["level"]}")

    save_user_data(data)


# Load the cache when the bot starts
response_cache = load_cache()

# Load postcard storage from JSON
postcard_storage = load_postcards()


def get_random_gif(search_term: str, apikey: str, ckey: str, limit: int = 8):
    """
    Returns a random GIF URL based on a search term using the Tenor API.

    Args:
        search_term (str): The search term to find GIFs (e.g., "excited").
        apikey (str): Your Tenor API key.
        ckey (str): Your client key for Tenor.
        limit (int): The number of results to fetch (default is 8).

    Returns:
        str: URL of a random GIF or None if the request failed.
    """
    # Make the request to the Tenor API
    r = requests.get(
        f"https://tenor.googleapis.com/v2/search?q={search_term}&key={apikey}&client_key={ckey}&limit={limit}"
    )

    if r.status_code == 200:
        # Load the GIFs using the urls for the smaller GIF sizes
        top_gifs = json.loads(r.content)

        # Debugging: Print out the top_gifs to inspect the structure
        print(json.dumps(
            top_gifs,
            indent=4))  # This will print the response in a readable format

        # Check if there are results and the 'media_formats' key is in each result
        if 'results' in top_gifs:
            gifs = top_gifs['results']

            # Filter out results that don't have 'media_formats' or 'gif' format
            valid_gifs = [
                gif for gif in gifs
                if 'media_formats' in gif and 'gif' in gif['media_formats']
            ]

            if valid_gifs:
                # Randomly select a valid GIF and return its GIF URL
                random_gif = random.choice(valid_gifs)
                gif_url = random_gif['media_formats']['gif']['url']

                # Ensure the URL is not too long
                if len(gif_url
                       ) <= 2000:  # Discord allows up to 2000 characters
                    return gif_url
                else:
                    return "Error: The GIF URL is too long."
    return "No GIFs found or error occurred."


def get_pixabay_image(query):
    PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')
    PIXABAY_URL = "https://pixabay.com/api/"
    params = {
        'key': PIXABAY_API_KEY,
        'q': query,
        'image_type': 'photo',
        'orientation': 'horizontal',
        'per_page': 5  # You can adjust the number of results to return
    }

    try:
        response = requests.get(PIXABAY_URL, params=params)
        data = response.json()

        # If we got results from Pixabay
        if data['totalHits'] > 0:
            # Randomly pick an image from the results
            image = random.choice(data['hits'])
            return image['webformatURL']
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching image: {e}")
        return None


def get_ai(user_input: str):
    base_url = "https://api.aimlapi.com/v1"
    api_key = os.getenv('AI_API_KEY')
    system_prompt = "You are named Milo cannot write more than 2000 carachters You are a discord bot to help boost engagement."

    api = OpenAI(api_key=api_key, base_url=base_url)
    MAX_MESSAGE_LENGTH = 232

    # Truncate user input if it's too long
    if len(user_input) > MAX_MESSAGE_LENGTH:
        user_input = user_input[:MAX_MESSAGE_LENGTH]

    completion = api.chat.completions.create(
        model="google/gemma-2b-it",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_input
            },
        ],
        temperature=0.7,
        max_tokens=255,
    )

    response = completion.choices[0].message.content
    return response  # Ensure this returns a string


def get_cat():
    url = "https://api.thecatapi.com/v1/images/search"
    cat_api_key = os.environ['CATAPIKEY']
    headers = {'x-api-key': cat_api_key}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()[0]['url']


@bot.event
async def on_guild_join(guild):
    """Triggered when the bot joins a new guild."""

    # Get the default text channel in the guild
    channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)

    if channel:
        # Create an embed object
        embed = discord.Embed(
            title=f"Hello {guild.name}!",
            description="Thank you for inviting me to your server! I'm **Milo**, your new assistant bot. I'm here to help with moderation, custom commands, and much more! 🎉\n\n"
            "Here's a few things you can do to get started:\n\n"
            "- **Set up custom commands** – Need a unique command? I can help with that!\n"
            "- **Auto Roles** – I can assign roles to new members automatically.\n"
            "- **Moderation tools** – Let me help you keep the server clean and friendly.\n\n"
            "I'm excited to be part of your community, and I’m always here to assist! If you need help, just type `!help`, and I'll show you all the awesome things I can do! 🚀",)

        # Add an image to the embed (can be a URL to an image)
        embed.set_image(url="https://example.com/your-image-url.jpg")  # Replace with your own image URL

        # Send the embed with the image to the channel
        await channel.send(embed=embed)

    else:
        print(f"No available channels to send a welcome message in '{guild.name}'!")
@bot.event
async def on_member_join(member):
    """Handles new member joins, sends a welcome message in the correct channel, and assigns an auto role."""
    settings = load_settings()
    guild_id = str(member.guild.id)
    guild_settings = settings.get(guild_id, {})

    # Get the welcome message (with member ping and name)
    welcome_message = guild_settings.get("Welcome message", f"Welcome {member.mention} to {member.guild.name}! 🎉")

    # Replace placeholders with actual values
    welcome_message = welcome_message.replace("{user.mention}", member.mention).replace("{user.name}", member.name)

    # Get the stored welcome channel ID
    welcome_channel_id = guild_settings.get("Welcome Channel")
    channel = None

    if welcome_channel_id:
        channel = bot.get_channel(welcome_channel_id)  # Ensure the bot retrieves the channel properly
        if not channel or not channel.permissions_for(member.guild.me).send_messages:
            print(f"❌ Cannot send message in configured welcome channel ({welcome_channel_id}) for '{member.guild.name}'!")
            channel = None  # Reset if the bot can't send messages there

    # Only fallback if necessary
    if not channel:
        channel = next((c for c in member.guild.text_channels if c.permissions_for(member.guild.me).send_messages), None)

    if channel:
        await channel.send(welcome_message)
        print(f"✅ Sent welcome message in {channel.name} ({member.guild.name})")
    else:
        print(f"❌ No available channels to send a welcome message in '{member.guild.name}'!")

    # Auto Role Assignment
    auto_role_name = guild_settings.get("Auto Role")
    if auto_role_name:
        role = discord.utils.get(member.guild.roles, name=auto_role_name)

        if role:
            if member.guild.me.guild_permissions.manage_roles and role.position < member.guild.me.top_role.position:
                await member.add_roles(role)
                print(f"✅ Assigned Auto Role '{role.name}' to {member.name}")
            else:
                print(f"❌ Cannot assign '{role.name}' - Role is higher than the bot's role or lacks permission!")
        else:
            print(f"❌ Auto Role '{auto_role_name}' not found in '{member.guild.name}'!")

activity = discord.Game(name=";ai")
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    print(bot.commands)
    await bot.change_presence(activity=activity)

@bot.event
async def on_raw_reaction_remove(payload):
    """Handles role removal when a user removes a reaction from a message."""
    guild_id = str(payload.guild_id)
    member = await bot.guilds[0].fetch_member(payload.user_id)
    settings = load_settings()

    # Check if the guild has reaction roles
    guild_settings = settings.get(guild_id, {})
    if "reaction_roles" not in guild_settings:
        return

    emoji = str(payload.emoji)
    role_id = guild_settings["reaction_roles"].get(emoji)

    if not role_id:
        return

    # Get the role object
    role = discord.utils.get(member.guild.roles, id=role_id)

    if role:
        try:
            await member.remove_roles(role)
            print(f"✅ Removed role '{role.name}' from {member.name} for emoji '{emoji}'")
        except discord.DiscordException as e:
            print(f"❌ Error removing role: {str(e)}")
    else:
        print(f"❌ Role with ID '{role_id}' not found!")

@bot.event
async def on_raw_reaction_add(payload):
    """Handles role assignment when a user reacts to a message."""
    guild_id = str(payload.guild_id)
    member = await bot.guilds[0].fetch_member(payload.user_id)
    settings = load_settings()

    # Check if the guild has reaction roles
    guild_settings = settings.get(guild_id, {})
    if "reaction_roles" not in guild_settings:
        return

    emoji = str(payload.emoji)  # Convert emoji to string
    role_id = guild_settings["reaction_roles"].get(emoji)

    if not role_id:
        return

    # Get the role object
    role = discord.utils.get(member.guild.roles, id=role_id)

    if role:
        try:
            await member.add_roles(role)
            print(f"✅ Assigned role '{role.name}' to {member.name} for emoji '{emoji}'")
        except discord.DiscordException as e:
            print(f"❌ Error assigning role: {str(e)}")
    else:
        print(f"❌ Role with ID '{role_id}' not found!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You need the 'Staff' role to use this command.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Please check the available commands.")
    else:
        await ctx.send(f"An error occurred while processing your request. Error code: {error}. If the issue persists, please contact the server admin to make sure that I have the necessary permissions.")
        await send_dm_to_staff(ctx.guild, f"⚠️ An error occured with the bot in {ctx.channel}. \n User: {ctx.author.mention} \n Error: {error} \n Please make sure that Milo has the necessary permissions. If it does, please let us know about the error by posting the error code in our [github](https://github.com/caydenworld/Milo/).")
        print(f"An error occured in a server {error}")

@bot.command(name="addstaff", description="Adds a member to the staff role.", category="Moderation")
@commands.has_role("Staff")  # Ensure the person has administrator permissions
async def addstaff(ctx, member: discord.Member):
    """Adds a user to the staff role (only accessible to the server owner or staff)."""

    # Check if the user is the server owner or has the 'Staff' role
    if ctx.author == ctx.guild.owner or "Staff" in [role.name for role in ctx.author.roles]:
        staff_role = discord.utils.get(ctx.guild.roles, name="Staff")

        # If the 'Staff' role doesn't exist, create one
        if not staff_role:
            staff_role = await ctx.guild.create_role(name="Staff")

        # Add the 'Staff' role to the member
        await member.add_roles(staff_role)
        await ctx.send(f"{member.mention} has been added to the staff role.")
    else:
        await ctx.send("You need to be the server owner or have the 'Staff' role to use this command.")


@bot.command(name="closeticket", description="Closes a support ticket.", category="Utilities")
@commands.has_role("Staff")  # Only staff can close tickets
async def closeticket(ctx):
    """Closes the ticket by deleting the ticket channel."""

    # Check if the command is being used in a ticket channel
    if ctx.channel.name.startswith("ticket-"):
        # Send a confirmation message before deletion
        await ctx.send("Closing this ticket...")

        # Optionally, you could archive the content of the ticket before deletion, e.g., by logging it in another channel

        # Delete the ticket channel
        await ctx.channel.delete()
    else:
        await ctx.send("This command can only be used in a ticket channel.")

@bot.command(name="ticket", description="Opens a support ticket.", category="Utilities")
async def ticket(ctx):
    """Creates a private ticket channel for the user."""

    # Get the guild and author (the user)
    guild = ctx.guild

    # Create a unique name for the ticket channel based on the user's name
    ticket_name = f"ticket-{ctx.author.name}"

    # Check if a ticket already exists for the user
    existing_channel = discord.utils.get(guild.text_channels, name=ticket_name)
    if existing_channel:
        await ctx.send(f"You already have a ticket open: {existing_channel.mention}")
        return

    # Set up channel permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),  # Prevent everyone from seeing the ticket
        ctx.author: discord.PermissionOverwrite(read_messages=True),  # Allow the user to see their own ticket
        bot.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)  # Allow bot to see and send messages

    }

    # Create the ticket channel
    ticket_channel = await guild.create_text_channel(ticket_name, overwrites=overwrites)

    # Notify staff about the new ticket
    staff_role = discord.utils.get(guild.roles, name="Staff")
    if staff_role:
        await ticket_channel.send(f"Hello {ctx.author.mention}, this is your ticket! A staff member will assist you shortly.")
        await ticket_channel.send(f"Hey {staff_role.mention}, a new ticket has been created by {ctx.author.mention}.")

    # Send a message in the original channel notifying the user
    await ctx.send(f"Your ticket has been created! {ticket_channel.mention}")


@bot.command(name="rr", description="Create a reaction role.", category="Utilities")
@commands.has_role("Staff")
async def rr(ctx, message_id: int, emoji: str, *, role: discord.Role):
    """
    Sets up a reaction role for a specific message.
    - `message_id`: The ID of the message to add reactions to.
    - `emoji`: The emoji to react with.
    - `role`: The role to assign when the emoji is reacted with.
    """
    # Get the message to add the reaction
    try:
        message = await ctx.fetch_message(message_id)
    except discord.NotFound:
        await ctx.send(f"❌ Could not find message with ID {message_id}.")
        return

    # Add the reaction to the message
    try:
        await message.add_reaction(emoji)
        await ctx.send(f"✅ Reaction role set! React with {emoji} to get the {role.name} role.")
    except discord.DiscordException as e:
        await ctx.send(f"❌ Error adding reaction: {str(e)}")
        return

    # Store the emoji-role mapping in settings or a dictionary
    settings = load_settings()
    guild_id = str(ctx.guild.id)
    if guild_id not in settings:
        settings[guild_id] = {}

    # Store reaction-role mapping
    if "reaction_roles" not in settings[guild_id]:
        settings[guild_id]["reaction_roles"] = {}

    settings[guild_id]["reaction_roles"][emoji] = role.id

    # Save settings
    save_settings(settings)

# Command: Set Auto Role
@bot.command(name="setautorole", description="Sets the auto role for the server.", category="Moderation")
@commands.has_role("Staff")
async def setautorole(ctx, role: discord.Role):
    """Sets the Auto Role for new members."""
    update_setting(ctx.guild.id, "Auto Role", role.name)
    await ctx.send(f"✅ Auto Role set to: **{role.name}**")

# Command: Set Welcome Message
@bot.command(name="setwelcome", description="Sets the server´s welcome message.", category="Moderation")
@commands.has_role("Staff")
async def setwelcome(ctx, channel: discord.TextChannel = None, *, message: str):
    """Sets a custom welcome message and optionally a specific welcome channel."""
    guild_id = str(ctx.guild.id)
    settings = load_settings()

    # Ensure the guild has an entry
    if guild_id not in settings:
        settings[guild_id] = {}

    # Store welcome message
    settings[guild_id]["Welcome message"] = message

    # Store the selected channel (if provided)
    if channel:
        settings[guild_id]["Welcome Channel"] = channel.id
        await ctx.send(f"✅ Welcome message set! It will be sent in {channel.mention}.")
    else:
        await ctx.send("✅ Welcome message updated! It will be sent in the first available channel.")

    # Save settings to file
    save_settings(settings)


# Command: Set Custom AI Prompt
@bot.command(name="setaiprompt", description="Insert a custom ai prompt.", category="Moderation")
@commands.has_role("Staff")
async def setaiprompt(ctx, *, prompt: str):
    """Sets the system prompt for AI interactions."""
    update_setting(ctx.guild.id, "AI Prompt", prompt)
    await ctx.send("✅ AI system prompt updated!")

# Command: View Current Settings
@bot.command(name="viewsettings", description="View the settings for this server.", category="Moderation")
@commands.has_role("Staff")
async def viewsettings(ctx):
    """Displays the current server settings."""
    settings = load_settings()
    guild_id = str(ctx.guild.id)
    guild_settings = settings.get(guild_id, {})

    if not guild_settings:
        await ctx.send("⚠ No settings configured for this server.")
        return

    formatted_settings = "\n".join([f"**{key}:** {value}" for key, value in guild_settings.items()])
    await ctx.send(f"🔧 **Current Settings:**\n{formatted_settings}")


@bot.command(name="modsetup", description="Sets up the server for Milo.", category="Moderation")
async def modsetup(ctx):
    guild = ctx.guild
    staff_role = discord.utils.get(guild.roles, name="Staff")

    if staff_role in ctx.author.roles or ctx.author == guild.owner or ctx.author == bot.user:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),  # Hide for everyone
            staff_role: discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True),
            # Allow staff
            guild.me: discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True)
            # Allow Milo bot
        }

        existing_channel = discord.utils.get(guild.text_channels, name="milo-mod-logs")
        if existing_channel:
            await ctx.send("⚠️ 'milo-mod-logs' channel already exists!")
        else:
            await guild.create_text_channel('milo-mod-logs', overwrites=overwrites)
            await ctx.send("✅ Created 'milo-mod-logs' channel with restricted access!")
    else:
        await ctx.send("❌ You do not have permission to create this channel. To add staff, use the add staff command.")


@bot.command(name="riggedcoinflip", description="Win every bet.", category="Utilities")
async def riggedcoinflip(ctx):
    await ctx.send('Heads')


@bot.command(name="image", description="Gets an image of choice.", category="Image")
async def image(ctx, *, query):
    await ctx.send(get_pixabay_image(query))


@bot.command(name="gif", description="Gets a gif of choice. ", category="Image")
async def gif(ctx, *, query):
    async with ctx.typing():
        tenorapikey = os.getenv('TENOR_API')
        clientkey = "The_Path"
        await ctx.send(get_random_gif(query, tenorapikey, clientkey))


@bot.command(name="ai", description="Talk to Milo!", category="Fun")
async def ai(ctx, *, user_input: str):
    async with ctx.typing():
        # Check if the response is already cached
        if user_input in response_cache:
            response = response_cache[user_input]
        else:
            try:
                # Get AI response from the get_ai function
                response = get_ai(user_input)

                # Cache the response for future use
                response_cache[user_input] = response

                # Save the updated cache to the file
                save_cache(response_cache)

            except Exception as e:
                # Check if it's a rate limit error (Error code: 429)
                website = os.getenv('Website')
                if "429" in str(e):
                    await ctx.send(
                        f"Sorry, we've hit the rate limit for the AI API. To help increase this limit, [Buy us a Coffee!]({website})"
                    )
                    # Log the error for debugging
                    print(f"Rate limit error: {e}")
                else:
                    # For other errors, simply send an error message
                    await ctx.send(f"An error occurred: {e}")
                    return

    # Send the AI response in the original channel
    await ctx.send(f"{response}\n -# Milo ai can make mistakes. Check important info.")


@bot.command(name="magic8ball", description="What will it answer?", category="Fun")
async def magic8ball(ctx):
    await ctx.send(random.choice(eight_ball_answers))


@bot.command(name="coinflip", description="Chooses between heads and tails.", category="Utilities")
async def coinflip(ctx):
    chance = random.randint(1, 2)
    if chance == 1:
        await ctx.send("Heads")
    else:
        await ctx.send("Tails")


@bot.command(name="choice", description="Chooses between yes and no.", category="Utilities")
async def choice(ctx):
    chance = random.randint(1, 2)
    if chance == 1:
        await ctx.send("Yes")
    else:
        await ctx.send("No")


@bot.command(name="choice2", description="Chooses between yes, no and maybe.", category="Utilities")
async def choice2(ctx):
    chance = random.randint(1, 3)
    if chance == 1:
        await ctx.send("Yes")
    elif chance == 2:
        await ctx.send("No")
    else:
        await ctx.send("Maybe")


@bot.command(name="magic", description="Summons magical powers.", category="Fun")
async def magic(ctx):
    await ctx.send("Aberacadabera, You're a Camera!")


@bot.command(name="cat", description="Gets a random cat.", category="Fun")
async def cat(ctx):
    await ctx.reply(get_cat())


@bot.command(name="arebirdsreal", description="Are they?", category="Fun")
async def arebirdsreal(ctx):
    await ctx.send("No.")
    msg = await bot.wait_for("message")
    if msg.content.lower() == "really?":
        await ctx.send("Yes, of course they're real.")


@bot.command(name="languages", description="View languages and their language codes for the translate command.", category="Fun")
async def languages(ctx):
    await ctx.send(
        'Supported languages: Afrikaans (af), Albanian (sq), Amharic (am), Arabic (ar), Armenian (hy), Assamese (as), Aymara (ay), Azerbaijani (az), Bambara (bm), Basque (eu), Belarusian (be), Bengali (bn), Bhojpuri (bho), Bosnian (bs), Bulgarian (bg), Catalan (ca), Cebuano (ceb), Chichewa (ny), Chinese (Simplified) (zh), Chinese (Traditional) (zh-TW), Corsican (co), Croatian (hr), Czech (cs), Danish (da), Dhivehi (dv), Dogri (doi), Dutch (nl), English (en), Esperanto (eo), Estonian (et), Ewe (ee), Filipino (fil), Finnish (fi), French (fr), Frisian (fy), Galician (gl), Georgian (ka), German (de), Greek (el), Guarani (gn), Gujarati (gu), Haitian Creole (ht), Hausa (ha), Hawaiian (haw), Hebrew (he), Hindi (hi), Hmong (hmn), Hungarian (hu), Icelandic (is), Igbo (ig), Ilocano (ilo), Indonesian (id), Irish (ga), Italian (it), Japanese (ja), Javanese (jv), Kannada (kn), Kazakh (kk), Khmer (km), Kinyarwanda (rw), Konkani (gom), Korean (ko), Krio (kri), Kurdish (Kurmanji) (ku), Kurdish (Sorani) (ckb), Kyrgyz (ky), Lao (lo), Latin (la), Latvian (lv), Lingala (ln), Lithuanian (lt), Luganda (lg), Luxembourgish (lb), Macedonian (mk), Maithili (mai), Malagasy (mg), Malay (ms), Malayalam (ml), Maltese (mt), Maori (mi), Marathi (mr), Meiteilon (Manipuri) (mni), Mizo (lus), Mongolian (mn), Myanmar (Burmese) (my), Nepali (ne), Norwegian (no), Odia (Oriya) (or), Oromo (om), Pashto (ps), Persian (fa), Polish (pl), Portuguese (pt), Punjabi (pa), Quechua (qu), Romanian (ro), Russian (ru), Samoan (sm), Sanskrit (sa), Scots Gaelic (gd), Sepedi (nso), Serbian (sr), Sesotho (st), Shona (sn), Sindhi (sd), Sinhala (si), Slovak (sk), Slovenian (sl), Somali (so), Spanish (es), Sundanese (su), Swahili (sw), Swedish (sv), Tajik (tg), Tamil (ta), Tatar (tt), Telugu (te), Thai (th), Tigrinya (ti), Tsonga (ts), Turkish (tr), Turkmen (tk), Twi (tw), Ukrainian (uk), Urdu (ur), Uyghur (ug), Uzbek (uz), Vietnamese (vi), Welsh (cy), Xhosa (xh), Yiddish (yi), Yoruba (yo), Zulu (zu)'
    )


@bot.command(name="sendpostcard", description="Send a postcard to a user.", category="Fun")
async def sendpostcard(ctx, recipient: discord.User, *, message=None):
    """
    Sends a postcard to a recipient with a custom message or randomly generated one.
    """
    # List of random postcard messages if no custom message is provided
    random_postcards = [
        "Greetings from Paris! 🗼✨ Hope you enjoy the Eiffel Tower and the local croissants!",
        "A sunny day in Bali! 🌴🌊 Don't forget to visit the temples and beaches!",
        "Exploring Tokyo! 🏙️🍣 Amazing food and an awesome blend of tradition and technology!",
        "Cheers from London! 🎡🌧️ Be sure to visit the Tower of London and Big Ben!",
        "Wanderlust in New York City! 🗽🌆 Enjoy the skyline and the amazing parks!"
    ]

    # If no message is provided, choose a random postcard
    if not message:
        message = random.choice(random_postcards)

    # Append the "from" message at the end of the postcard
    from_message = f"\n\nFrom: {ctx.author.name} ({ctx.author.mention})"

    # Final postcard message
    final_message = message + from_message

    # If the recipient already has postcards, append to the list, otherwise create a new list
    if recipient.id not in postcard_storage:
        postcard_storage[recipient.id] = []

    # Append the new postcard message to the recipient's list
    postcard_storage[recipient.id].append(final_message)

    # Save the updated postcards to the JSON file
    save_postcards(postcard_storage)

    # Notify the recipient via DM
    try:
        await recipient.send(
            f"📬 You've received a new postcard from {ctx.author.name} ({ctx.author.mention})! Use `;openpostcard` to view your postcards. 🎉"
        )
        await ctx.send(f"✅ Postcard sent to {recipient.mention}!")
    except discord.Forbidden:
        await ctx.send(
            f"❌ Could not send a DM to {recipient.mention}. Please make sure their DMs are open."
        )


@bot.command(name="openpostcard", description="Open your postcards.", category="Fun")
async def openpostcard(ctx):
    """
    Allows a recipient to view their postcards.
    """
    # Check if the user has any postcards stored
    if ctx.author.id in postcard_storage and postcard_storage[ctx.author.id]:
        # Retrieve the list of postcards
        messages = postcard_storage[ctx.author.id]

        # Construct the message to send all postcards
        response = "🌍 Here are your postcards:\n"
        for index, message in enumerate(messages, start=1):
            response += f"**Postcard {index}:** {message}\n"

        # Send the postcards
        await ctx.message.reply(response)

        del postcard_storage[ctx.author.id]

        # Save the updated postcards to the JSON file after deletion
        save_postcards(postcard_storage)
    else:
        await ctx.send("❌ You don’t have any postcards to open!")


@bot.command(name="balance", description="Check your balance.", category="Currency")
async def balance(ctx):
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    money = get_balance(guild_id, user_id)
    await ctx.send(
        f"💰 {ctx.author.name}, you have **{money} miles** in this server.")


# 💸 Command: Give money to another user
@bot.command(name="give", description="Give another person gems.", category="Currency")
async def give(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("Please enter a valid amount.")
        return

    guild_id = ctx.guild.id
    user_id = ctx.author.id
    target_id = member.id

    if remove_money(guild_id, user_id, amount):
        add_money(guild_id, target_id, amount)
        await ctx.send(
            f"✅ {ctx.author.name} gave {amount} gems to {member.name}.")
    else:
        await ctx.send("❌ You don’t have enough miles.")


# 🏆 Command: Currency leaderboard (server-specific)
@bot.command(name="gemboard", description="View the leaderboard.", category="Currency")
async def gemboard(ctx):
    guild_id = str(ctx.guild.id)
    data = load_currency()

    # If no currency data for the server, create an entry for it
    if guild_id not in data:
        data[guild_id] = {}
        # Save the updated data with the server entry
        save_currency(data)

        await ctx.send(
            "No currency data for this server yet. Creating a new entry.")

    # Sort users by mileage (just miles)
    sorted_users = sorted(data[guild_id].items(),
                          key=lambda x: x[1]['miles'],
                          reverse=True)

    leaderboard_message = "🏆 **Richest in This Server** 🏆\n\n"

    for idx, (user_id,
              user_data) in enumerate(sorted_users[:10]):  # Top 10 users
        user = await bot.fetch_user(int(user_id))
        leaderboard_message += f"**{idx + 1}. {user.name}** - {user_data['miles']} gems\n"

    await ctx.send(leaderboard_message)


@bot.command(name="level", description="View your level.", category="Leveling")
async def level(ctx):
    data = read_user_data()
    user_id = str(ctx.author.id)
    if user_id not in data:
        await ctx.send(f"{ctx.author.name}, you haven't earned any XP yet!")
        return

    user_data = data[user_id]
    await ctx.send(
        f"{ctx.author.name}, you are level {user_data['level']} with {user_data['xp']} XP."
    )


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.author.bot or not message.guild:
        return  # Ignore bots & DMs

    guild_id = str(message.guild.id)
    settings = load_settings()
    bad_words = settings.get(guild_id, {}).get("bad_words", [])

    for word in bad_words:
        if word.lower() in message.content.lower():
            await message.delete()
            await message.channel.send(f"🚩 {message.author.mention}, this message has been flagged by Milo Automod. Think this is a mistake? Contact the server Admin to review their filter.")
            return


    xp_earned = random.randint(10, 20)

    await update_xp(message, str(message.author.id), xp_earned)

    # Get the guild settings
    settings = load_settings()
    guild_id = str(message.guild.id)

    # Check if custom commands are defined for this guild
    if guild_id in settings and "custom_commands" in settings[guild_id]:
        custom_commands = settings[guild_id]["custom_commands"]

        # Check if the message content matches any custom command
        if message.content in custom_commands:
            response = custom_commands[message.content]

            # Replace {user.mention} and {user.name} with actual user details
            response = response.replace("{user.mention}", message.author.mention)
            response = response.replace("{user.name}", message.author.name)

            await message.channel.send(response)
            return  # Stop here, don't process other commands after this

    # Process regular commands (this is necessary to allow normal commands to work)
    await bot.process_commands(message)


@bot.command(name="daily", description="Get 500 gems every day.", category="Currency")
async def daily(ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    # Load currency data
    try:
        with open("currency.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    # Ensure user exists in the system
    if guild_id not in data:
        data[guild_id] = {}
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {"miles": 0, "last_flight": 0}

    # Check if 24 hours have passed since the last flight
    current_time = time.time()
    if current_time - data[guild_id][user_id]["last_flight"] < 86400:
        time_left = 86400 - (current_time -
                             data[guild_id][user_id]["last_flight"])
        hours_left = int(time_left // 3600)
        minutes_left = int((time_left % 3600) // 60)
        await ctx.send(
            f"{ctx.author.mention}, you can only claim a daily once every 24 hours. Please wait {hours_left} hours and {minutes_left} minutes before your next daily."
        )
        return

    # Give 500 miles and update last flight time
    data[guild_id][user_id]["miles"] += 500
    data[guild_id][user_id]["last_flight"] = current_time

    # Save updated data
    with open("currency.json", "w") as f:
        json.dump(data, f, indent=4)

    await ctx.send(
        f"✈️ {ctx.author.mention}, You earned **500 gems** 💎! Come back in 24 hours for another 500."
    )

@bot.command(name="addcommand", description="Allows staff to add a custom command.", category="Moderation")
@commands.has_role("Staff")
async def addcommand(ctx, command_name: str, *, response: str):
    """Adds a custom command to the server."""
    settings = load_settings()
    guild_id = str(ctx.guild.id)

    # Ensure the guild has an entry in the settings file
    if guild_id not in settings:
        settings[guild_id] = {}

    # Create a "custom_commands" section for this server
    if "custom_commands" not in settings[guild_id]:
        settings[guild_id]["custom_commands"] = {}

    # Add the new custom command to the guild's settings
    settings[guild_id]["custom_commands"][f";{command_name}"] = response

    # Save the settings back to the file
    save_settings(settings)

    await ctx.send(f"✅ Custom command `{command_name}` added successfully!")

# Command to remove a custom command
@bot.command(name="removecommand", description="Allows staff to remove a custom command.", category="Moderation")
@commands.has_role("Staff")
async def removecommand(ctx, command_name: str):
    """Removes a custom command from the server."""
    settings = load_settings()
    guild_id = str(ctx.guild.id)

    if guild_id not in settings or "custom_commands" not in settings[guild_id]:
        await ctx.send("❌ No custom commands have been set yet.")
        return

    if command_name in settings[guild_id]["custom_commands"]:
        del settings[guild_id]["custom_commands"][command_name]
        save_settings(settings)
        await ctx.send(f"✅ Custom command `{command_name}` removed successfully!")
    else:
        await ctx.send(f"❌ Command `{command_name}` not found.")




def load_data():
    try:
        with open("mod_data.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save data function
def save_data(data):
    with open("mod_data.json", "w") as f:
        json.dump(data, f, indent=4)





# Load data from files





# **Moderation Commands**
async def send_dm(user: discord.Member, message: str):
    try:
        await user.send(message)
    except discord.Forbidden:
        print(f"❌ Could not DM {user.name} (DMs disabled)")



@bot.command(name="kick", description="Allows staff to kick a user.", category="Moderation")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"✅ {member.mention} has been kicked for: **{reason}**")

        # Log to mod channel
        log_channel = discord.utils.get(ctx.guild.text_channels, name="milo-mod-logs")
        if log_channel:
            await log_channel.send(f"👢 **{member}** was kicked by {ctx.author.mention} for: **{reason}**")

    except discord.Forbidden:
        await ctx.send("❌ I don’t have permission to kick this user.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


# 🔨 **Ban Command**
@bot.command(name="ban", description="Allows staff to ban a user.", category="Moderation")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ {member.mention} has been banned for: **{reason}**")

        # Log to mod channel
        log_channel = discord.utils.get(ctx.guild.text_channels, name="milo-mod-logs")
        if log_channel:
            await log_channel.send(f"⛔ **{member}** was banned by {ctx.author.mention} for: **{reason}**")
    except discord.Forbidden:
        await ctx.send("❌ I don’t have permission to ban this user.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


# 🔨 **Report Command**
@bot.command(name="report", description="Reports a user to the staff.", category="Moderation")
async def report(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        data = load_data()
        if "reports" not in data:
            data["reports"] = []

        # Store report in JSON
        report_entry = {
            "reporter": ctx.author.name,
            "reported": member.name,
            "reason": reason
        }
        data["reports"].append(report_entry)
        save_data(data)

        await ctx.send(f"✅ {ctx.author.mention}, your report on {member.mention} has been recorded.")

        # Log to mod channel
        log_channel = discord.utils.get(ctx.guild.text_channels, name="milo-mod-logs")
        if log_channel:
            await log_channel.send(
                f"🚨 **Report Alert!** 🚨\n<:purple_arrow:1340691455152361653>**Reporter:** {ctx.author.mention}\n<:purple_arrow:1340691455152361653>**Accused:** {member.mention}\n<:purple_arrow:1340691455152361653>**Reason:** {reason}")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

warnings={}
# Warn Command
@bot.command(name="Warn", description="Allows staff to warn a user.", category="Moderation")
@commands.has_role("Staff")
async def warn(ctx, member: discord.Member, *, reason):
    if member.id not in warnings:
        warnings[member.id] = []
    warnings[member.id].append(reason)
    save_data("warnings_file", warnings)
    await ctx.send(f'{member} has been warned for: {reason}')

    # Send DM to staff
    dm_message = f"{ctx.author.name} has warned {member} for: {reason} in {ctx.guild.name}"
    await send_dm_to_staff(ctx.guild, dm_message)
# **Poll Command**

@bot.command(name="poll", description="Creates a Poll.", category="Moderation")
@commands.has_role("Staff")
async def poll(ctx, question, *options):
    if len(options) < 2:
        await ctx.send("Please provide at least two options for the poll.")
        return
    if len(options) > 10:
        await ctx.send("Please provide no more than 10 options for the poll.")
        return
    embed = discord.Embed(title=question,
                          description="\n".join([f"{index + 1}. {option}" for index, option in enumerate(options)]),
                          color=discord.Color.blue())
    poll_message = await ctx.send(embed=embed)

    for i in range(len(options)):
        await poll_message.add_reaction(f"{chr(127462 + i)}")  # Adds reactions A, B, C...


@bot.command(name="butter", description="Summons the power of butter.", category="Fun")
async def butter(ctx):
    await ctx.reply("Oh No! The Butter Flies!")
    await ctx.reply("<:butterbutterfly:1338905847425663077>")

help_commands = {
    "Moderation": {
        "ban": {"emoji": "🔨", "description": "Bans a user from the server.", "usage": "`;ban @user [reason]`"},
        "kick": {"emoji": "👢", "description": "Kicks a user from the server.", "usage": "`;kick @user [reason]`"},
        "warn": {"emoji": "⚠️", "description": "Warns a user and logs it.", "usage": "`;warn @user [reason]`"},
        "report": {"emoji": "📩", "description": "Reports a user to staff.", "usage": "`;report @user [reason]`"},
        "addcommand": {"emoji": "🛠️", "description": "Allows staff to add a custom command.", "usage": "`;addcommand [command_name] [response]`"},
        "removecommand": {"emoji": "❌", "description": "Allows staff to remove a custom command.", "usage": "`;removecommand [command_name]`"},
    },
    "Utility": {
        "help": {"emoji": "❓", "description": "Shows this help menu.", "usage": "`;help [command]`"},
        "openpostcard": {"emoji": "🌍", "description": "Opens your postcards.", "usage": "`;openpostcard`"},
        "poll": {"emoji": "📊", "description": "Creates a poll with reactions.", "usage": "`;poll <question> option1` Surrond the question and options in""."},
        "sendpostcard": {"emoji": "💌", "description": "Send a postcard to another user.", "usage": "`;sendpostcard @user <message>`"},
        "coinflip": {"emoji": "🪙", "description": "Heads or Tails?", "usage": "`;coinflip`"},
        "riggedcoinflip": {"emoji": "🤞", "description": "Heads or Heads? Win every bet!", "usage": "`;riggedcoinflip`"},
        "choice": {"emoji": "🤔", "description": "Chooses between yes and no.", "usage": "`;choice`"},
        "choice2": {"emoji": "🤔", "description": "Chooses between yes, no and maybe.", "usage": "`;choice2`"},
    },
    "Currency": {
        "give": {"emoji": "💸", "description": "Give gems to another user.", "usage": "`;give @user [amount]`"},
        "gemboard": {"emoji": "🏆", "description": "View the currency leaderboard.", "usage": "`;gemboard`"},
        "balance": {"emoji": "💰", "description": "Check your balance.", "usage": "`;balance`"},
        "daily": {"emoji": "✈️", "description": "Get 500 gems every day.", "usage": "`;daily`"}
    },
    "Leveling": {
        "level": {"emoji": "📈", "description": "View your current level and XP.", "usage": "`;level`"}
    },
    "Fun": {
        "butter": {"emoji": "🧈", "description": "Summons the power of butter.", "usage": "`;butter`"},
        "8ball": {"emoji": "🎱", "description": "Ask the magic 8-ball a question.", "usage": "`;8ball <question>`"},
        "ai": {"emoji": "🤖", "description": "Talk to Milo.", "usage": "`;ai <prompt>`"},
    },
    "Image": {
        "image": {"emoji": "📷", "description": "Gets an image.", "usage": "`;image <prompt>`"},
        "gif": {"emoji": "🤣", "description": "Gets a gif.", "usage": "`;gif <prompt>`"},
    }
}


@bot.command()
async def help(ctx, command=None):
    embed = discord.Embed(title="Help Command", color=discord.Color(0xBE38F3))

    # If a specific command is requested
    if command:
        command_info = None
        for category, commands in help_commands.items():
            if command in commands:
                command_info = commands[command]
                break

        # If the command is found, show its details
        if command_info:
            embed.add_field(
                name=f"{command_info['emoji']} {command}",
                value=f"**Description:** {command_info['description']}\n**Usage:** {command_info['usage']}",
                inline=False
            )
        else:
            embed.add_field(name="Error", value="Command not found.", inline=False)

    # If no command is requested, show all commands
    else:
        for category, commands in help_commands.items():
            category_field = ""
            for cmd, info in commands.items():
                category_field += f"{info['emoji']} **{cmd}**: {info['description']}\n"

            embed.add_field(
                name=f"{category} Commands",
                value=category_field,
                inline=False
            )

    await ctx.send(embed=embed)


def is_url(string):
    url_pattern = re.compile(r'https?://(?:www\.)?\S+\.(?:jpg|jpeg|png|gif|webp)')
    return re.match(url_pattern, string)


# Dummy Pixabay function (Replace with actual API call)
def get_pixabay_image(query):
    return "https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_1280.jpg"  # Example image


# Function to get the Impact font
def get_impact_font(size):
    try:
        return ImageFont.truetype("impact.ttf", size)  # Ensure impact.ttf exists
    except:
        return ImageFont.load_default()  # Fallback


# Meme command
@bot.command(name="meme", description="Generates a meme with a given image and text.")
async def meme(ctx, image_input: str, *, text: str):
    async with ctx.typing():
        try:
            # Use the URL directly if it's valid; otherwise, get an image from Pixabay
            image_url = image_input if is_url(image_input) else get_pixabay_image(image_input)

            if not image_url:
                await ctx.send("Couldn't find a valid image. Try another keyword.")
                return

            # Download the image
            response = requests.get(image_url)
            if response.status_code != 200:
                await ctx.send("Failed to download image.")
                return

            # Open image with PIL
            image = Image.open(BytesIO(response.content))

            # Add text (Meme Style)
            draw = ImageDraw.Draw(image)
            font_size = int(image.width * 0.1)
            font = get_impact_font(font_size)

            # Text positioning
            text_x = image.width // 2
            text_y = int(image.height * 0.05)

            # Outline effect
            outline_range = 3
            for x_offset in range(-outline_range, outline_range + 1):
                for y_offset in range(-outline_range, outline_range + 1):
                    draw.text((text_x + x_offset, text_y + y_offset), text, font=font, fill="black", anchor="mm")

            # Main text
            draw.text((text_x, text_y), text, font=font, fill="white", anchor="mm")

            # Save and send the meme
            with BytesIO() as image_binary:
                image.save(image_binary, "PNG")
                image_binary.seek(0)
                await ctx.send(file=discord.File(image_binary, "meme.png"))

        except Exception as e:
            await ctx.send(f"Error: {e}")



# ✅ Command: Add a bad word
@bot.command(name="addbadword", description="Add a word to the filter (Admins only)")
@commands.has_role("Staff")
async def addbadword(ctx, *, word):
    guild_id = str(ctx.guild.id)
    settings = load_settings()
    bad_words = settings.get(guild_id, {}).get("bad_words", [])

    if word.lower() in bad_words:
        await ctx.send("That word is already in the filter!")
        return

    bad_words.append(word.lower())
    update_setting(guild_id, "bad_words", bad_words)
    await ctx.send(f"Added `{word}` to the bad word filter.")

# ❌ Command: Remove a bad word
@bot.command(name="removebadword", description="Remove a word from the filter (Admins only)")
@commands.has_role("Staff")
async def removebadword(ctx, *, word):
    guild_id = str(ctx.guild.id)
    settings = load_settings()
    bad_words = settings.get(guild_id, {}).get("bad_words", [])

    if word.lower() not in bad_words:
        await ctx.send("That word is not in the filter!")
        return

    bad_words.remove(word.lower())
    update_setting(guild_id, "bad_words", bad_words)
    await ctx.send(f"Removed `{word}` from the bad word filter.")

# 📜 Command: List all filtered words
@bot.command(name="listbadwords", description="List all filtered words for this server")
@commands.has_role("Staff")
async def listbadwords(ctx):
    guild_id = str(ctx.guild.id)
    settings = load_settings()
    bad_words = settings.get(guild_id, {}).get("bad_words", [])

    if not bad_words:
        await ctx.send("No bad words are currently filtered.")
    else:
        await ctx.send("Filtered words: " + ", ".join(bad_words))


SERVER_LIST_FILE = "server_list.json"
BAD_WORDS = ["milo", "official", "scam", "scamming"]


def load_servers():
    """Loads the servers from the JSON file."""
    if not os.path.exists(SERVER_LIST_FILE):
        return {}
    with open(SERVER_LIST_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_servers(servers):
    """Saves the servers data to the JSON file."""
    with open(SERVER_LIST_FILE, "w", encoding="utf-8") as file:
        json.dump(servers, file, indent=4)


def is_valid_server_name(server_name):
    """Checks if the server name contains any bad words."""
    for bad_word in BAD_WORDS:
        if bad_word.lower() in server_name.lower():
            return False
    return True


class ServerDropdown(Select):
    """Dropdown for selecting a server."""
    def __init__(self, servers, bot):
        options = []
        for name, data in servers.items():
            # Add the verified emoji to the dropdown if the server is verified
            verified_emoji = None
            if data.get("verified"):
                # Ensure correct emoji formatting for the bot's custom emoji
                verified_emoji = discord.PartialEmoji(name="Verified", id="1340697696960380978")

            options.append(discord.SelectOption(
                label=data['server_name'],
                value=name,
                emoji=verified_emoji  # Add the emoji here
            ))

        super().__init__(placeholder="Select a server to join", options=options)
        self.servers = servers
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        server_name = self.values[0]
        server_data = self.servers.get(server_name, {})

        invite = server_data.get("invite", "")
        if invite:
            button = Button(label="Click to Join", url=invite)

            # Create a view with the button
            view = View()
            view.add_item(button)

            # Send the message with the button inside a view
            await interaction.response.send_message(
                f"🌍 Click to join `{server_name}`:",
                ephemeral=True,
                view=view
            )
        else:
            await interaction.response.send_message(
                "❌ There was an issue with the server's invite link.",
                ephemeral=True)

class VerifyDropdown(Select):
    """Dropdown for selecting servers to verify."""

    def __init__(self, servers):
        options = [
            discord.SelectOption(label=servers[name]["server_name"], value=name)
            for name, data in servers.items() if not data.get("verified")
        ]
        super().__init__(placeholder="Select a server to verify", options=options)
        self.servers = servers

    async def callback(self, interaction: discord.Interaction):
        server_name = self.values[0]
        server_data = self.servers.get(server_name, {})

        # Mark the server as verified
        server_data["verified"] = True
        save_servers(self.servers)

        await interaction.response.send_message(
            f"<:Verified:1340697696960380978> Server `{server_name}` has been verified!", ephemeral=True
        )


@bot.command(name="register", description="Registers your server on the server list")
@commands.has_permissions(administrator=True)
async def register(ctx, server_name):
    """Registers a server with a name and invite link, and checks for bad words."""
    if not is_valid_server_name(server_name):
        await ctx.send(
            "❌ The server name contains restricted words (e.g., Milo, official, scam). Please choose another name. Think this is a mistake? File a patch in our [github](https://github.com/caydenworld/Milo/)")
        return

    servers = load_servers()

    # Check if the guild already has a registered server
    if str(ctx.guild.id) in servers:
        await ctx.send("❌ This server already has a registered listing.")
        return

    # Generate an invite link
    invite = await ctx.channel.create_invite(max_uses=0, unique=True)

    # Save the server data along with the guild ID
    servers[str(ctx.guild.id)] = {
        "server_name": server_name,
        "invite": str(invite),
        "verified": False,  # By default, the server is not verified
        "guild_id": ctx.guild.id  # Store guild ID
    }

    save_servers(servers)

    await ctx.send(f"✅ `{server_name}` has been added to the Milo server list!")


@bot.command(name="servers", description="Shows available servers to join")
async def servers(ctx):
    servers = load_servers()

    if not servers:
        await ctx.send("❌ No servers have been registered yet.")
        return

    view = View()
    dropdown = ServerDropdown(servers, ctx.bot)
    view.add_item(dropdown)

    # Send the message with the dropdown and view
    await ctx.send("📜 **Milo Server List:**", view=view)


@bot.command(name="verify", description="Verifies a server as trusted (Admin only)")
@commands.is_owner()  # Ensure only the bot owner can use this command
async def verify(ctx):
    """Shows a dropdown for selecting servers that can be verified."""
    servers = load_servers()

    if not any(not data.get("verified") for data in servers.values()):
        await ctx.send("❌ No unverified servers available.")
        return

    view = View()
    dropdown = VerifyDropdown(servers)
    view.add_item(dropdown)

    # Send the message with the dropdown to verify
    await ctx.send("🔒 **Select a server to verify:**", view=view)
bot.run(os.getenv('DISCORD_TOKEN'))
