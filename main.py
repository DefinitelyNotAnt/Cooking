from dotenv import load_dotenv
import os 
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
import discord
from discord.utils import get
from discord import app_commands
import re
from pymongo import MongoClient
import os

# Load environment variables
load_dotenv()
discordkey: str = os.getenv('discordkey')
api_key: str = os.getenv('apikey')
model: str = "deepseek-r1-distill-llama-70b"
mongo_uri = os.getenv("mongouri")


client = MongoClient(mongo_uri)
db = client["PCRDatabase"]
users_collection = db["users"]
pcrs_collection = db["pcrs"]
audit_logs_collection = db["audit_logs"]
AUDIT_ROLES = "Maincomm"
def user_has_maincomm_role(user) -> bool:
    """Check if the user has Maincomm role."""
    return any(role.name == AUDIT_ROLES for role in user.roles)


def log_audit(user_id, pcr_name, action, details=""):
    """Log PCR changes unless it's private."""
    audit_logs_collection.insert_one({
        "user_id": user_id,
        "pcr_name": pcr_name,
        "action": action,
        "details": details
    })




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
pcr = app_commands.Group(name="pcr", description="Manage PCR tasks")
# # Define Context Menu Command
# @app_commands.command(name="pcr")
# async def pcr_command(interaction: discord.Interaction):
#     await interaction.response.send_message("Hello PCR making!")
@pcr.command(name="create", description="Create a new PCR")
async def pcr_create(interaction: discord.Interaction, name: str, item: str, private: bool = False):
    user_id = str(interaction.user.id)
    if pcrs_collection.find_one({"user_id": user_id, "name": name}):
        await interaction.response.send_message("You already have a PCR with this name.")
        return

    pcrs_collection.insert_one({
        "user_id": user_id,
        "name": name,
        "item": item,
        "sources": [],
        "rationale": "",
        "private": private
    })

    if not private:
        log_audit(user_id, name, "create")

    await interaction.response.send_message(f"PCR '{name}' created!")

@pcr.command(name="add", description="Add data to an existing PCR")
async def pcr_add(interaction: discord.Interaction, name: str, source: str = None, rationale: str = None):
    user_id = str(interaction.user.id)
    pcr = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr:
        await interaction.response.send_message("PCR not found.")
        return

    update_fields = {}
    if source:
        update_fields["sources"] = pcr["sources"] + [source]
    if rationale:
        update_fields["rationale"] = rationale

    pcrs_collection.update_one({"_id": pcr["_id"]}, {"$set": update_fields})

    if not pcr["private"]:
        log_audit(user_id, name, "add", f"Added source/rationale: {source or rationale}")

    await interaction.response.send_message(f"Added to PCR '{name}'.")

@pcr.command(name="edit", description="Edit an existing PCR")
async def pcr_edit(interaction: discord.Interaction, name: str, item: str = None, sources: str = None, rationale: str = None):
    user_id = str(interaction.user.id)
    pcr = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr:
        await interaction.response.send_message("PCR not found.")
        return

    update_fields = {}
    if item:
        update_fields["item"] = item
    if sources:
        update_fields["sources"] = sources.split(",")  # Example input: link1,link2
    if rationale:
        update_fields["rationale"] = rationale

    pcrs_collection.update_one({"_id": pcr["_id"]}, {"$set": update_fields})

    if not pcr["private"]:
        log_audit(user_id, name, "edit", "Edited PCR details")

    await interaction.response.send_message(f"PCR '{name}' edited.")

@pcr.command(name="remove", description="Remove data from an existing PCR")
async def pcr_remove(interaction: discord.Interaction, name: str, source: str = None, remove_rationale: bool = False):
    user_id = str(interaction.user.id)
    pcr = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr:
        await interaction.response.send_message("PCR not found.")
        return

    update_fields = {}
    if source:
        update_fields["sources"] = [s for s in pcr["sources"] if s != source]
    if remove_rationale:
        update_fields["rationale"] = ""

    pcrs_collection.update_one({"_id": pcr["_id"]}, {"$set": update_fields})

    if not pcr["private"]:
        log_audit(user_id, name, "remove", f"Removed source/rationale: {source or 'rationale'}")

    await interaction.response.send_message(f"Removed from PCR '{name}'.")

@pcr.command(name="delete", description="Delete an existing PCR")
async def pcr_delete(interaction: discord.Interaction, name: str):
    user_id = str(interaction.user.id)
    pcr = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr:
        await interaction.response.send_message("PCR not found.")
        return

    pcrs_collection.delete_one({"_id": pcr["_id"]})

    if not pcr["private"]:
        log_audit(user_id, name, "delete", "Deleted PCR")

    await interaction.response.send_message(f"PCR '{name}' deleted.")

@pcr.command(name="pcr_view", description="View your own PCR or all PCRs if Maincomm.")
async def pcr_view(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if user_has_maincomm_role(interaction.user):
        pcrs = pcrs_collection.find()
    else:
        pcrs = pcrs_collection.find({"user_id": user_id})

    response = ""
    for pcr in pcrs:
        response += f"**{pcr['name']}**\nItem: {pcr['item']}\nSources: {', '.join(pcr['sources'])}\nRationale: {pcr['rationale']}\n\n"

    await interaction.response.send_message(response or "No PCRs found.")
@tree.command(name="audit_log", description="View the audit log (Maincomm only).")
async def audit_log(interaction: discord.Interaction):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to view the audit log.")
        return

    logs = audit_logs_collection.find()
    response = ""
    for log in logs:
        response += f"User: {log['user_id']}, PCR: {log['pcr_name']}, Action: {log['action']}, Details: {log['details']}\n"

    await interaction.response.send_message(response or "No audit logs found.")

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
            # self.tree.add_command(pcr_command)  # Register context menu command
            await self.tree.sync()
            print("Slash commands and context menus synced!")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
    async def setup_hook(self):
        self.tree.add_command(pcr)  # Register the group here
        
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
