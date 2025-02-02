import discord
import os
from discord.ext import commands
import requests
import random
import asyncio
import json
import time
from openai import OpenAI
from eight_ball_answers import eight_ball_answers

# Files for storage
CACHE_FILE = "ai_cache.json"
POSTCARD_FILE = "postcards.json"

# Set intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# Initialize bot
bot = commands.Bot(command_prefix=';', intents=intents)


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
def update_xp(user_id, xp_earned):
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


# Example usage:
search_term = "excited"  # You can change this to any search term
gif_url = get_random_gif(search_term,
                         apikey="YOUR_API_KEY",
                         ckey="my_test_app")
print(gif_url)  # This will print the URL of the GIF to be sent to Discord


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
    system_prompt = "You are named Milo cannot write more than 2000 carachters You are a discord bot to help boost engagement You are not a dog"

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
async def on_member_join(member):
    for guild in bot.guilds:
        # Try to find the first available text channel in the guild
        channel = next((c for c in guild.text_channels
                        if c.permissions_for(guild.me).send_messages), None)

        if channel:
            await channel.send(
                f"Welcome {member.mention} to {member.guild.name}! We hope you have a great time here! 🎉"
            )  # Sends the message to the first available channel
        else:
            print(
                f"No text channels where the bot can send messages in guild '{guild.name}'!"
            )


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')


@bot.command()
async def modsetup(ctx):
    if ctx.author.guild_permissions.manage_channels:
        # Create a new text channel
        await ctx.send("Setting up the bot...")
        await ctx.guild.create_text_channel('path mod logs')
        await ctx.send(f"✅ Channels have been created.")
        time.sleep(1)
        await ctx.send(f"✅ Commands have been setup.")
        time.sleep(1)
        await ctx.send(
            f"✅ Setup Complete. To view a list of commands, run **;helpcommand**"
        )
    else:
        await ctx.send(
            "❌ I don't have permission to create a channel. Please make sure I have the necessary permissions, and run this command again."
        )


@bot.command()
async def riggedcoinflip(ctx):
    await ctx.send('Heads')


@bot.command()
async def image(ctx, *, query):
    await ctx.send(get_pixabay_image(query))


@bot.command()
async def gif(ctx, *, query):
    tenorapikey = os.getenv('TENOR_API')
    clientkey = "The_Path"
    await ctx.send(get_random_gif(query, tenorapikey, clientkey))


@bot.command()
async def ai(ctx, *, user_input: str):
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
    await ctx.send(response)


@bot.command()
async def magic8ball(ctx):
    await ctx.send(random.choice(eight_ball_answers))


@bot.command()
async def coinflip(ctx):
    chance = random.randint(1, 2)
    if chance == 1:
        await ctx.send("Heads")
    else:
        await ctx.send("Tails")


@bot.command()
async def choice(ctx):
    chance = random.randint(1, 2)
    if chance == 1:
        await ctx.send("Yes")
    else:
        await ctx.send("No")


@bot.command()
async def choice2(ctx):
    chance = random.randint(1, 3)
    if chance == 1:
        await ctx.send("Yes")
    elif chance == 2:
        await ctx.send("No")
    else:
        await ctx.send("Maybe")


@bot.command()
async def magic(ctx):
    await ctx.send("Aberacadabera, You're a Camera!")


@bot.command()
async def cat(ctx):
    await ctx.reply(get_cat())


@bot.command()
async def arebirdsreal(ctx):
    await ctx.send("No.")
    msg = await bot.wait_for("message")
    if msg.content.lower() == "really?":
        await ctx.send("Yes, of course they're real.")


@bot.command()
async def languages(ctx):
    await ctx.send(
        'Supported languages: Afrikaans (af), Albanian (sq), Amharic (am), Arabic (ar), Armenian (hy), Assamese (as), Aymara (ay), Azerbaijani (az), Bambara (bm), Basque (eu), Belarusian (be), Bengali (bn), Bhojpuri (bho), Bosnian (bs), Bulgarian (bg), Catalan (ca), Cebuano (ceb), Chichewa (ny), Chinese (Simplified) (zh), Chinese (Traditional) (zh-TW), Corsican (co), Croatian (hr), Czech (cs), Danish (da), Dhivehi (dv), Dogri (doi), Dutch (nl), English (en), Esperanto (eo), Estonian (et), Ewe (ee), Filipino (fil), Finnish (fi), French (fr), Frisian (fy), Galician (gl), Georgian (ka), German (de), Greek (el), Guarani (gn), Gujarati (gu), Haitian Creole (ht), Hausa (ha), Hawaiian (haw), Hebrew (he), Hindi (hi), Hmong (hmn), Hungarian (hu), Icelandic (is), Igbo (ig), Ilocano (ilo), Indonesian (id), Irish (ga), Italian (it), Japanese (ja), Javanese (jv), Kannada (kn), Kazakh (kk), Khmer (km), Kinyarwanda (rw), Konkani (gom), Korean (ko), Krio (kri), Kurdish (Kurmanji) (ku), Kurdish (Sorani) (ckb), Kyrgyz (ky), Lao (lo), Latin (la), Latvian (lv), Lingala (ln), Lithuanian (lt), Luganda (lg), Luxembourgish (lb), Macedonian (mk), Maithili (mai), Malagasy (mg), Malay (ms), Malayalam (ml), Maltese (mt), Maori (mi), Marathi (mr), Meiteilon (Manipuri) (mni), Mizo (lus), Mongolian (mn), Myanmar (Burmese) (my), Nepali (ne), Norwegian (no), Odia (Oriya) (or), Oromo (om), Pashto (ps), Persian (fa), Polish (pl), Portuguese (pt), Punjabi (pa), Quechua (qu), Romanian (ro), Russian (ru), Samoan (sm), Sanskrit (sa), Scots Gaelic (gd), Sepedi (nso), Serbian (sr), Sesotho (st), Shona (sn), Sindhi (sd), Sinhala (si), Slovak (sk), Slovenian (sl), Somali (so), Spanish (es), Sundanese (su), Swahili (sw), Swedish (sv), Tajik (tg), Tamil (ta), Tatar (tt), Telugu (te), Thai (th), Tigrinya (ti), Tsonga (ts), Turkish (tr), Turkmen (tk), Twi (tw), Ukrainian (uk), Urdu (ur), Uyghur (ug), Uzbek (uz), Vietnamese (vi), Welsh (cy), Xhosa (xh), Yiddish (yi), Yoruba (yo), Zulu (zu)'
    )


@bot.command(name="sendpostcard")
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


@bot.command(name="openpostcard")
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


@bot.command()
async def balance(ctx):
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    money = get_balance(guild_id, user_id)
    await ctx.send(
        f"💰 {ctx.author.name}, you have **{money} miles** in this server.")


# 💸 Command: Give money to another user
@bot.command()
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
            f"✅ {ctx.author.name} gave {amount} miles to {member.name}.")
    else:
        await ctx.send("❌ You don’t have enough miles.")


# 🏆 Command: Currency leaderboard (server-specific)
@bot.command()
async def mileboard(ctx):
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

    leaderboard_message = "🏆 **Most Well Traveled Users in This Server** 🏆\n\n"

    for idx, (user_id,
              user_data) in enumerate(sorted_users[:10]):  # Top 10 users
        user = await bot.fetch_user(int(user_id))
        leaderboard_message += f"**{idx + 1}. {user.name}** - {user_data['miles']} miles\n"

    await ctx.send(leaderboard_message)


@bot.command()
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


# Event when a user sends a message
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Give random XP between 10 and 20
    xp_earned = random.randint(10, 20)

    # Update XP and level for the user
    update_xp(str(message.author.id), xp_earned)

    await bot.process_commands(
        message)  # Allows commands to work even with on_message


@bot.command()
async def flight(ctx):
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
            f"{ctx.author.mention}, you can only take a flight once every 24 hours. Please wait {hours_left} hours and {minutes_left} minutes before your next flight."
        )
        return

    # Give 500 miles and update last flight time
    data[guild_id][user_id]["miles"] += 500
    data[guild_id][user_id]["last_flight"] = current_time

    # Save updated data
    with open("currency.json", "w") as f:
        json.dump(data, f, indent=4)

    await ctx.send(
        f"✈️ {ctx.author.mention}, you took a flight and earned **500 miles**! Come back in 24 hours for another trip."
    )


bot.run(os.getenv('DISCORD_TOKEN'))
