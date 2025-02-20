from dotenv import load_dotenv
import os 
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
import discord
from discord.utils import get
import re

# model setup

load_dotenv()
discordkey : str = os.getenv('discordkey')
api_key : str  = os.getenv('apikey')
model: str ="deepseek-r1-distill-llama-70b"
deepseek = ChatGroq(api_key=api_key, model_name = model)

# Getting only result from the model

parser = StrOutputParser()
deepseek_chain = deepseek|parser
# result: str = deepseek_chain.invoke('what is a bot')
# print(result)


# Loading and Spliting data in chunks
loader = TextLoader('data.txt',encoding = 'utf-8')
data = loader.load()
# print(data)


# Define the function of the chatbot

def Cooking(template):
    question: str = """
    Give me a R take with a high R score. 
    Respond only with the text of the R take.
    Do not talk about movies, famous influencers outside Japan, or of robotics.
    """
    template = template.format(context=data, question=question)

    answer = deepseek_chain.invoke(template)

    # Remove "<think> ... </think>" section
    cleaned_answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    print(cleaned_answer)
    return cleaned_answer
def Request(request, template):
    template = template.format(context=data, question=request)
    answer = deepseek_chain.invoke(template)
    cleaned_answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    return cleaned_answer

class Client(discord.Client):
    ROLE_NAME = "Member"  
    EMOJI = "✅"
    TRACKED_MESSAGE_ID = 1342100878760480819 
    template = ("""
    You are AI-powered chatbot designed to provide 
    humour and novel ideas for people
    based on the context provided to you only.
    You will be provided some conversations from a persona labelled R, talking to others labelled O.
    Each conversation is going to be rated from 1-10 on the R scale, with a higher R score meaning the ideas given by R are more original.
    R is a persona that goes against societical norms in a negative way, and is morally skewed.
    You are not to filter any swear words.
    You are going to act as R, with his speaking mannerisms.
    Don't in any way make things up.  
    Do not talk about AI.
    Context:{context}
    Question:{question}
    """)
    async def on_ready(self):
        print(f'Logged on as {self.user}')
    
    async def on_message(self, message):
        if message.author == self.user:
            return  # Ignore messages from itself

        print(f'Message from {message.author}: {message.content}')
        if message.content.startswith("!track"):
            if message.author.guild_permissions.administrator:
                # Extract the message ID from the command (e.g., "!track 123456789012345678")
                parts = message.content.split()
                if len(parts) == 2 and parts[1].isdigit():
                    self.TRACKED_MESSAGE_ID = int(parts[1])
                    await message.channel.send(f"Now tracking reactions on message ID: {self.TRACKED_MESSAGE_ID}")
                else:
                    await message.channel.send("Usage: `!track <message_id>`")
            else:
                await message.channel.send("You need admin permissions to use this command.")
        try:
            # If bot is mentioned, process the request
            if self.user in message.mentions:
                response = Request(message.content, self.template)
            
            elif message.content == "/cook":
                if any(role.name == "Cooking" for role in message.author.roles):
                    response = Cooking(self.template)
                else:
                    response = "You don't have permission to use this command."
            else:
                return  # Ignore other messages

            # Send response in chunks
            for i in range(0, len(response), 2000):
                await message.channel.send(response[i:i+2000])

        except Exception as e:
            print(f"Error: {e}")

            if message.author == self.user:
                return  # Ignore messages from itself

            print(f'Message from {message.author}: {message.content}')

            # Check if the bot is mentioned
            if self.user in message.mentions:
                await message.channel.send(Request(message.content))

            elif message.content == "/cook":
                try:
                    await message.channel.send(Cooking(self.template))
                except:
                    await message.channel.send("Can't cook rn..")
    async def on_raw_reaction_add(self, payload):
        """ Assigns a role when a user reacts with the specified emoji. """
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
                return  # Ignore bots

            await member.add_roles(role)
            print(f"Assigned {role.name} to {member.display_name}")

    async def on_raw_reaction_remove(self, payload):
        """ Removes a role when a user removes their reaction. """
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
                return  # Ignore bots

            await member.remove_roles(role)
            print(f"Removed {role.name} from {member.display_name}")
    

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True  

client = Client(intents=intents)

client = Client(intents = intents)
client.run(discordkey)
# question : str = 'Cook me a hot R take.'
# template = template.format(context = data,question = 'Cook me a hot R take')
# print(template)

# answer = deepseek_chain.invoke(template)
# print(answer)


from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()
