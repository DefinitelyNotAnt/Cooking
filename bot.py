from dotenv import load_dotenv
import os
import discord
from discord import app_commands
from discord.utils import get
from rishan import Request, Cooking
from pcr import pcr, source_group

# Load Discord token from environment variables
load_dotenv()
discordkey: str = os.getenv('discordkey')

class Client(discord.Client):
    ROLE_NAME = "Member"  
    EMOJI = "✅"
    TRACKED_MESSAGE_ID = 1342135518338613272

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
        # Add slash command groups from pcr.py
        self.tree.add_command(pcr)
        self.tree.add_command(source_group)

    async def on_message(self, message):
        if message.author == self.user:
            return
        try:
            # If bot is mentioned, use the Request function from rishan.py
            if self.user in message.mentions:
                response = Request(message.content, self.template)
            # If message is exactly "/cook", check for permission and call Cooking
            elif message.content == "/cook":
                if any(role.name == "Cooking" for role in message.author.roles):
                    response = Cooking(self.template)
                else:
                    response = "You don't have permission to use this command."
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

# Initialize bot with the required intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True  

client = Client(intents=intents)
client.run(discordkey)
