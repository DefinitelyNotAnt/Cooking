print("Importing dotenv")
from dotenv import load_dotenv
print("Importing os")
import os
print("Importing discord")
import discord
print("Importing app_commands")
from discord import app_commands
print("Importing utils")
from discord.utils import get
print("Importing gacha")
from commands import gacha_group, custom_group
print("Importing request n cooking")
from rishan import Request, Cooking
print("Importing random")
import random

# Load Discord token from environment variables
print("Loading dotenv")
load_dotenv()
discordkey: str = os.getenv('discordkey')
print("Loaded discordkey")

class Client(discord.Client):
    ROLE_NAME = "Member"  
    COOKING_ROLE = "Cooking"
    EMOJI = "✅"
    TRACKED_MESSAGE_ID = 1342135518338613272
    WORD_FILTER = ["Project Sekai", "Fuck", "Rishan","Nigger","Nigga","onlyfans","cock","penis","dick","vagina","genshin","faggot","fellat","porn","rimjob"]
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.template = """
        You are an AI-powered chatbot designed to provide 
        novel ideas for people based on the given context.
        You will be provided conversations from a persona labeled R, talking to others labeled O.
        Each conversation has a rating from 1-10 on the R scale, with a higher score meaning more original ideas.
        Take the morals and worldview of the persona but do not only talk about the context that is given.
        You are not to filter any swear words.
        You will act as R, with his speaking mannerisms.
        All your responses should only output as what R would say and nothing else, and do not include the quotes ("").
        Don't make things up.  
        Do not talk about AI.
        Context: {context}
        Question: {question}
        """

    async def on_ready(self):
        print(f'Logged on as {self.user}')
        try:
            await self.tree.sync()
            print("Slash commands and context menus synced!")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def setup_hook(self):
        # Add slash command groups from commands
        self.tree.add_command(gacha_group)
        self.tree.add_command(custom_group)
    async def on_message(self, message):
        if message.author == self.user:
            return
        if any(word.lower() in message.content.lower() for word in self.WORD_FILTER):
            if any(role.name == self.COOKING_ROLE for role in message.author.roles):
                try:
                    await message.add_reaction("🔥")
                except Exception as e:
                    print(f"Couldn't add reaction: {e}")
                return
            ADMIN_CHANNEL_ID = 1359891372831670554
            try:
                await message.delete()
                try:
                    await message.author.send(
                        f"⚠️ Your message in **#{message.channel}** was removed because it contained a restricted word. Please follow the dictatorship's rules."
                    )
                except discord.Forbidden:
                    print(f"Could not DM user {message.author}.")

                # Log the incident in the admin log channel
                admin_channel = self.get_channel(ADMIN_CHANNEL_ID)
                if admin_channel:
                    embed = discord.Embed(
                        title="🚫 Word Filter Triggered",
                        description=f"**User:** {message.author} (`{message.author.id}`)\n"
                                    f"**Channel:** <#{message.channel.id}>\n"
                                    f"**Content:** `{message.content}`",
                        color=discord.Color.red()
                    )
                    await admin_channel.send(embed=embed)
            except Exception as e:
                print(f"Error filtering message: {e}")
            return 
        try:
            if "!welcome" == message.content:
                try:
                    # Path to the media folder
                    media_folder = "./joinmedia"
                    # List all image files in the folder
                    images = [
                        f for f in os.listdir(media_folder)
                        if f.endswith(('.png', '.jpg', '.jpeg', '.gif')) and not f.startswith('temp_')
                    ]

                    if not images:
                        print("No images found in the media folder.")
                        return

                    # Select a random image
                    random_image = os.path.join(media_folder, random.choice(images))

                    # Send the welcome message
                    channel = message.channel
                    if channel:
                        await channel.send(
                            f"Welcome!!\n"+
                            f"For you, here's what you can do here.\n"+
                            f"You can view <#1338038250685726820> to find out the various channels, or you can first introduce yourself at <#1338021134612041739>!",
                            file=discord.File(random_image)
                        )
                except Exception as e:
                    print(f"Error in !welcome: {e}")
                return
            if all(role.name != "Cooking" for role in message.author.roles):
                return
            # If bot is mentioned, use the Request function from rishan.py
            if self.user in message.mentions:
                response = Request(message.content, self.template)
            # If message is exactly "/cook", check for permission and call Cooking
            elif "i summon the word of r" in message.content.lower():
                if any(role.name == "Cooking" for role in message.author.roles):
                    response = Cooking(self.template)
                else:
                    response = "How did you even get here???"
            else:
                return

            # Discord message content limit: split response into 2000-character chunks
            for i in range(0, len(response), 2000):
                await message.channel.send(response[i:i+2000])
        except Exception as e:
            print(f"Error: {e}")
            await message.channel.send("An error occurred. Please try again.")

    async def on_raw_reaction_add(self, payload):
        """Assigns a role when a user reacts with the specified emoji."""
        if self.TRACKED_MESSAGE_ID and payload.message_id == self.TRACKED_MESSAGE_ID and str(payload.emoji) == self.EMOJI:
            guild = self.get_guild(payload.guild_id)
            if guild is None:
                return
            role = get(guild.roles, name=self.ROLE_NAME)
            if role is None:
                print(f"Role '{self.ROLE_NAME}' not found.")
                return
            member = await guild.fetch_member(payload.user_id)
            if member is None or member.bot:
                return
            await member.add_roles(role)
            print(f"Assigned {role.name} to {member.display_name}")

    async def on_raw_reaction_remove(self, payload):
        """Removes a role when a user removes their reaction."""
        if self.TRACKED_MESSAGE_ID and payload.message_id == self.TRACKED_MESSAGE_ID and str(payload.emoji) == self.EMOJI:
            guild = self.get_guild(payload.guild_id)
            if guild is None:
                return
            role = get(guild.roles, name=self.ROLE_NAME)
            if role is None:
                print(f"Role '{self.ROLE_NAME}' not found.")
                return
            member = guild.get_member(payload.user_id)
            if member is None or member.bot:
                return
            await member.remove_roles(role)
            print(f"Removed {role.name} from {member.display_name}")

    async def on_member_join(self, member):
            """Sends a custom welcome message with a random image when a new user joins."""
            try:
                # Path to the media folder
                media_folder = "./joinmedia"
                # List all image files in the folder
                images = [
                    f for f in os.listdir(media_folder)
                    if f.endswith(('.png', '.jpg', '.jpeg', '.gif')) and not f.startswith('temp_')
                ]

                if not images:
                    print("No images found in the media folder.")
                    return

                # Select a random image
                random_image = os.path.join(media_folder, random.choice(images))

                # Send the welcome message
                channel = member.guild.system_channel  # You can specify another channel if preferred
                if channel:
                    try:
                        await channel.send(
                            f"へい！\n"+
                            f"Nice to meet you, {member.mention}, Welcome to JCC Jinsei!\n"+
                            f"Enjoy your stay and don't forget to read <#1338036966159290458> to gain access to the rest of the server!",
                            file=discord.File(random_image)
                        )
                    except:
                        await channel.send(
                            f"へい！\n"+
                            f"Nice to meet you, {member.mention}, Welcome to JCC Jinsei!\n"+
                            f"Enjoy your stay and don't forget to read #rules to gain access to the rest of the server!\n",
                            file=discord.File(random_image)
                        )
            except Exception as e:
                print(f"Error in on_member_join: {e}")
# Initialize bot with the required intents
print("Getting intents")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True  
print("Matching intent to client")
client = Client(intents=intents)
print("Running client on discordkey")
client.run(discordkey)
