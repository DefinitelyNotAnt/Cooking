from dotenv import load_dotenv
import os 
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
import discord
from discord.utils import get
from discord import app_commands
import re

# Load environment variables
load_dotenv()
discordkey: str = os.getenv('discordkey')
api_key: str = os.getenv('apikey')
model: str = "deepseek-r1-distill-llama-70b"

# Initialize model
deepseek = ChatGroq(api_key=api_key, model_name=model)
parser = StrOutputParser()
deepseek_chain = deepseek | parser

# Load and split data
loader = TextLoader('data.txt', encoding='utf-8')
data = loader.load()

# Define chatbot functions
def Cooking(template):
    question = """
    Give me a R take with a high R score. 
    Respond only with the text of the R take.
    Do not talk about movies, famous influencers outside Japan, or robotics.
    """
    template = template.format(context=data, question=question)
    answer = deepseek_chain.invoke(template)
    cleaned_answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    return cleaned_answer

def Request(request, template):
    template = template.format(context=data, question=request)
    answer = deepseek_chain.invoke(template)
    cleaned_answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    return cleaned_answer

# Define Context Menu Command
@app_commands.command(name="pcr")
async def pcr_command(interaction: discord.Interaction):
    await interaction.response.send_message("Hello PCR making!")

# Discord Bot Client
class Client(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.template = """
        You are an AI-powered chatbot designed to provide 
        humor and novel ideas for people based on the given context.
        You will be provided conversations from a persona labeled R, talking to others labeled O.
        Each conversation has a rating from 1-10 on the R scale, with a higher score meaning more original ideas.
        R is a persona that goes against societal norms in a negative way and is morally skewed.
        You are not to filter any swear words.
        You will act as R, with his speaking mannerisms.
        Don't make things up.  
        Do not talk about AI.
        Context: {context}
        Question: {question}
        """

    async def on_ready(self):
        print(f'Logged on as {self.user}')
        try:
            self.tree.add_command(pcr_command)  # Register context menu command
            await self.tree.sync()
            print("Slash commands and context menus synced!")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return  # Ignore bot's own messages

        print(f'Message from {message.author}: {message.content}')

        try:
            if self.user in message.mentions:
                response = Request(message.content, self.template)
            elif message.content == "/cook":
                if any(role.name == "Cooking" for role in message.author.roles):
                    response = Cooking(self.template)
                else:
                    response = "You don't have permission to use this command."
            else:
                return  # Ignore other messages

            # Send response in chunks (to fit Discord's character limit)
            for i in range(0, len(response), 2000):
                await message.channel.send(response[i:i+2000])

        except Exception as e:
            print(f"Error: {e}")
            await message.channel.send("An error occurred. Please try again.")

# Initialize bot with intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = Client(intents=intents)
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
