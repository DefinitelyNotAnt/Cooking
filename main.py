from dotenv import load_dotenv
import os
import re
import asyncio
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
import discord
from discord.utils import get
from discord import app_commands
from pymongo import MongoClient
import aiohttp

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
PCR_ROLES = "Subcomm 25/26"

def user_has_maincomm_role(user) -> bool:
    """Check if the user has Maincomm role."""
    return any(role.name == AUDIT_ROLES for role in user.roles)

def log_audit(user_id, user_name, pcr_name, action, details=""):
    """Log PCR changes with the user's name."""
    audit_logs_collection.insert_one({
        "user_id": user_id,
        "user_name": user_name,
        "pcr_name": pcr_name,
        "action": action,
        "details": details
    })

def user_can_access_pcr(user, pcr_name):
    """Check if the user is the owner or has shared access to the PCR."""
    user_id = str(user.id)
    pcr = pcrs_collection.find_one({"name": pcr_name, "$or": [{"user_id": user_id}, {"shared_with": user_id}]})
    return pcr is not None

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

#############################################
# Existing PCR Command Group (unchanged)    #
#############################################

pcr = app_commands.Group(name="pcr", description="Manage PCR tasks")

@pcr.command(name="create", description="Create a new PCR")
async def pcr_create(interaction: discord.Interaction, name: str, item: str, private: bool = False):
    user_id = str(interaction.user.id)
    user_name = interaction.user.name

    if pcrs_collection.find_one({"user_id": user_id, "name": name}):
        await interaction.response.send_message("You already have a PCR with this name.")
        return

    # Insert the new PCR document into the collection
    pcrs_collection.insert_one({
        "user_id": user_id,
        "name": name,
        "item": item,
        "sources": [],
        "rationale": "",
        "private": private,
        "shared_with": [],
        "status": "Draft"
    })

    # Retrieve the PCR document to access its fields
    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr_doc:
        await interaction.response.send_message("An error occurred while creating the PCR.")
        return
    if not private:
        log_audit(user_id, user_name, name, "create")

    # Send the response with the correct data
    await interaction.response.send_message(f"**PCR '{name}' Created!**\nItem: {item}\n"
                                            f"**Sources:** {', '.join(pcr_doc['sources']) if pcr_doc['sources'] else 'None'}\n"
                                            f"**Rationale:** {pcr_doc['rationale'] or 'None'}\n"
                                            f"**Status:** {pcr_doc['status'] or 'Draft?'}")

@pcr.command(name="view", description="View your own PCRs, shared PCRs, or a specific PCR.")
async def pcr_view(interaction: discord.Interaction, name: str = None):
    user_id = str(interaction.user.id)

    if name:
        pcr_doc = pcrs_collection.find_one({
            "name": name,
            "$or": [
                {"user_id": user_id},
                {"shared_with": user_id}
            ]
        })
        if not pcr_doc:
            await interaction.response.send_message("PCR not found or you don't have access.")
            return
        response = (
            f"**PCR Name:** {pcr_doc['name']}\n"
            f"**Item:** {pcr_doc['item']}\n"
            f"**Sources:** {', '.join(pcr_doc['sources']) if pcr_doc['sources'] else 'None'}\n"
            f"**Rationale:** {pcr_doc['rationale'] or 'None'}\n"
            f"**Status:** {pcr_doc['status'] or 'Draft?'}"
        )
    else:
        query = {} if user_has_maincomm_role(interaction.user) else {
            "$or": [{"user_id": user_id}, {"shared_with": user_id}]
        }
        pcr_list = list(pcrs_collection.find(query))

        if not pcr_list:
            response = "No PCRs found."
        else:
            response = "\n\n".join(
                f"**PCR Name:** {p['name']}\n"
                f"**Item:** {p['item']}\n"
                f"**Sources:** {', '.join(p['sources']) if p['sources'] else 'None'}\n"
                f"**Rationale:** {p['rationale'] or 'None'}\n"
                f"**Status:** {p['status'] or 'Draft?'}"
                for p in pcr_list
            )

    await interaction.response.send_message(response)

@pcr.command(name="add", description="Add data to an existing PCR")
async def pcr_add(interaction: discord.Interaction, name: str, source: str = None, rationale: str = None):
    user_id = str(interaction.user.id)
    user_name = interaction.user.name

    if not user_can_access_pcr(interaction.user, name):
        await interaction.response.send_message("You don't have permission to edit this PCR.")
        return

    pcr_doc = pcrs_collection.find_one({"name": name})

    update_fields = {}
    if source:
        update_fields["sources"] = pcr_doc["sources"] + [source]
    if rationale:
        update_fields["rationale"] = rationale

    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    log_audit(user_id, user_name, name, "add", f"Added source/rationale: {source or rationale}")
    
    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})  # Fetch updated PCR
    await interaction.response.send_message(f"**PCR '{name}' Updated!**\nItem: {pcr_doc['item']}\n"
                                              f"**Sources:** {', '.join(pcr_doc['sources']) if pcr_doc['sources'] else 'None'}\n"
                                              f"**Rationale:** {pcr_doc['rationale'] or 'None'}\n"
                                              f"**Status:** {pcr_doc['status'] or 'Draft?'}")

@pcr.command(name="edit", description="Edit an existing PCR")
async def pcr_edit(interaction: discord.Interaction, name: str, item: str = None, sources: str = None, rationale: str = None):
    if not user_can_access_pcr(interaction.user, name):
        await interaction.response.send_message("You don't have permission to edit this PCR.")
        return

    user_id = str(interaction.user.id)
    user_name = interaction.user.name
    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return

    update_fields = {}
    if item:
        update_fields["item"] = item
    if sources:
        update_fields["sources"] = sources.split(",")  # Example input: link1,link2
    if rationale:
        update_fields["rationale"] = rationale

    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    if not pcr_doc["private"]:
        log_audit(user_id, user_name, name, "edit", "Edited PCR details")

    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})  # Fetch updated PCR
    response = (f"**Updated PCR '{name}'**\n"
                f"Item: {pcr_doc['item']}\n"
                f"Sources: {', '.join(pcr_doc['sources'])}\n"
                f"Rationale: {pcr_doc['rationale']}\n"
                f"**Status:** {pcr_doc['status'] or 'Draft?'}")
    await interaction.response.send_message(response)

@pcr.command(name="remove", description="Remove data from an existing PCR")
async def pcr_remove(interaction: discord.Interaction, name: str, source: str = None, remove_rationale: bool = False):
    user_id = str(interaction.user.id)
    user_name = interaction.user.name
    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return
    if not user_can_access_pcr(interaction.user, name):
        await interaction.response.send_message("You don't have permission to edit this PCR.")
        return

    update_fields = {}
    if source:
        update_fields["sources"] = [s for s in pcr_doc["sources"] if s != source]
    if remove_rationale:
        update_fields["rationale"] = ""

    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    if not pcr_doc["private"]:
        log_audit(user_id, user_name, name, "remove", f"Removed source/rationale: {source or 'rationale'}")

    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})  # Fetch updated PCR
    response = (f"**Updated PCR '{name}'**\n"
                f"Item: {pcr_doc['item']}\n"
                f"Sources: {', '.join(pcr_doc['sources'])}\n"
                f"Rationale: {pcr_doc['rationale']}\n"
                f"**Status:** {pcr_doc['status'] or 'Draft?'}")
    await interaction.response.send_message(response)
    
@pcr.command(name="share", description="Share a PCR with another user")
async def pcr_share(interaction: discord.Interaction, name: str, user: discord.Member):
    user_id = str(interaction.user.id)
    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return

    if pcr_doc["user_id"] != user_id:
        await interaction.response.send_message("Only the owner can share this PCR.")
        return

    shared_user_id = str(user.id)
    shared_with = pcr_doc.get("shared_with", [])
    if shared_user_id in shared_with:
        await interaction.response.send_message(f"{user.name} already has access to this PCR.")
        return

    shared_with.append(shared_user_id)
    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": {"shared_with": shared_with}})

    log_audit(user_id, interaction.user.name, name, "share", f"Shared with {user.name}")

    await interaction.response.send_message(f"PCR '{name}' shared with {user.name}.")

@pcr.command(name="delete", description="Delete an existing PCR")
async def pcr_delete(interaction: discord.Interaction, name: str):
    user_id = str(interaction.user.id)
    user_name = interaction.user.name

    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})

    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return

    pcrs_collection.delete_one({"_id": pcr_doc["_id"]})

    log_audit(user_id, user_name, name, "delete", "Deleted PCR")

    await interaction.response.send_message(f"PCR '{name}' deleted.")

@pcr.command(name="submit", description="Submit your PCR for review")
async def pcr_submit(interaction: discord.Interaction, name: str):
    user_id = str(interaction.user.id)
    user_name = interaction.user.name
    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})
    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return
    update_fields = {"status": "Pending"}
    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    if not pcr_doc["private"]:
        log_audit(user_id, user_name, name, "submit", "Submit PCR for review")

    pcr_doc = pcrs_collection.find_one({"user_id": user_id, "name": name})  # Fetch updated PCR
    response = (f"**PCR '{name}' Submitted for review**\n"
                f"Item: {pcr_doc['item']}\n"
                f"Sources: {', '.join(pcr_doc['sources'])}\n"
                f"Rationale: {pcr_doc['rationale']}\n"
                f"**Status:** {pcr_doc['status'] or 'Draft?'}")
    await interaction.response.send_message(response)

@pcr.command(name="audit_log", description="View the audit log (Maincomm only).")
async def audit_log(interaction: discord.Interaction):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to view the audit log.")
        return

    logs = audit_logs_collection.find()
    response = "\n".join(
        f"User: {log['user_name']} (ID: {log['user_id']}), PCR: {log['pcr_name']}, Action: {log['action']}, Details: {log['details']}"
        for log in logs
    )

    await interaction.response.send_message(response or "No audit logs found.")

@pcr.command(name="view_pending", description="View pending PCR forms (Maincomm only).")
async def view_pending(interaction: discord.Interaction):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to view pending PCRs.")
        return
    query = {"status": "Pending"}
    pcr_list = list(pcrs_collection.find(query))

    if not pcr_list:
        response = "No PCRs found."
    else:
        response = "\n\n".join(
            f"**PCR Name:** {p['name']}\n"
            f"**Item:** {p['item']}\n"
            f"**Sources:** {', '.join(p['sources']) if p['sources'] else 'None'}\n"
            f"**Rationale:** {p['rationale'] or 'None'}\n"
            f"**Status:** {p['status'] or 'Draft?'}"
            for p in pcr_list
        )

    await interaction.response.send_message(response)

@pcr.command(name="view_approved", description="View approved PCR forms (Maincomm only).")
async def view_approved(interaction: discord.Interaction):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to view approved PCRs.")
        return
    query = {"status": "Approved"}
    pcr_list = list(pcrs_collection.find(query))

    if not pcr_list:
        response = "No PCRs found."
    else:
        response = "\n\n".join(
            f"**PCR Name:** {p['name']}\n"
            f"**Item:** {p['item']}\n"
            f"**Sources:** {', '.join(p['sources']) if p['sources'] else 'None'}\n"
            f"**Rationale:** {p['rationale'] or 'None'}\n"
            f"**Status:** {p['status'] or 'Draft?'}"
            for p in pcr_list
        )

    await interaction.response.send_message(response)

@pcr.command(name="approve", description="Approve pending PCR forms (Maincomm only).")
async def approve(interaction: discord.Interaction, name: str):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to approve pending PCRs.")
        return
    user_id = str(interaction.user.id)
    user_name = interaction.user.name
    pcr_doc = pcrs_collection.find_one({"name": name})
    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return
    update_fields = {"status": "Approved"}
    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    if not pcr_doc["private"]:
        log_audit(user_id, user_name, name, "approve", "Approved PCR")

    pcr_doc = pcrs_collection.find_one({"name": name})  # Fetch updated PCR
    response = (f"**PCR '{name}' Approved**\n"
                f"Item: {pcr_doc['item']}\n"
                f"Sources: {', '.join(pcr_doc['sources'])}\n"
                f"Rationale: {pcr_doc['rationale']}\n"
                f"**Status:** {pcr_doc['status'] or 'Draft?'}")
    await interaction.response.send_message(response)
    
    # Notify owner and shared users
    users_to_notify = []
    if not pcr_doc.get('shared_with'):
        users_to_notify = [pcr_doc['user_id']]
    else:
        users_to_notify = pcr_doc['shared_with'][:]
        if pcr_doc['user_id'] not in users_to_notify:
            users_to_notify.append(pcr_doc['user_id'])
    for uid in users_to_notify:
        user_obj = interaction.client.get_user(int(uid))
        if user_obj:
            try:
                await user_obj.send(f"**PCR '{name}' Approved!**\nItem: {pcr_doc['item']}\n"
                                      f"**Sources:** {', '.join(pcr_doc['sources']) if pcr_doc['sources'] else 'None'}\n"
                                      f"**Rationale:** {pcr_doc['rationale'] or 'None'}\n"
                                      f"**Status:** {pcr_doc['status'] or 'Draft'}")
            except discord.Forbidden:
                await interaction.response.send_message("I couldn't send a DM to one or more users. Please ask them to enable DMs.")

@pcr.command(name="pushback", description="Push back pending PCR forms (Maincomm only).")
async def pushback(interaction: discord.Interaction, name: str, reason: str):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to pushback pending PCRs.")
        return
    user_id = str(interaction.user.id)
    user_name = interaction.user.name
    pcr_doc = pcrs_collection.find_one({"name": name})
    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return
    update_fields = {"status": "Draft"}
    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    if not pcr_doc["private"]:
        log_audit(user_id, user_name, name, "pushback", "Pushed Back PCR")

    pcr_doc = pcrs_collection.find_one({"name": name})  # Fetch updated PCR
    response = (f"**PCR '{name}' Pushed Back**\n"
                f"Item: {pcr_doc['item']}\n"
                f"Sources: {', '.join(pcr_doc['sources'])}\n"
                f"Rationale: {pcr_doc['rationale']}\n"
                f"**Status:** {pcr_doc['status'] or 'Draft?'}")
    await interaction.response.send_message(response)
    
    users_to_notify = []
    if not pcr_doc.get('shared_with'):
        users_to_notify = [pcr_doc['user_id']]
    else:
        users_to_notify = pcr_doc['shared_with'][:]
        if pcr_doc['user_id'] not in users_to_notify:
            users_to_notify.append(pcr_doc['user_id'])
    for uid in users_to_notify:
        user_obj = interaction.client.get_user(int(uid))
        if user_obj:
            try:
                await user_obj.send(f"**PCR '{name}' Pushed Back!**\nItem: {pcr_doc['item']}\n"
                                      f"**Sources:** {', '.join(pcr_doc['sources']) if pcr_doc['sources'] else 'None'}\n"
                                      f"**Rationale:** {pcr_doc['rationale'] or 'None'}\n"
                                      f"**Status:** {pcr_doc['status'] or 'Draft'}\n\n"
                                      f"**Reason:** {reason}")
            except discord.Forbidden:
                await interaction.response.send_message("I couldn't send a DM to one or more users. Please ask them to enable DMs.")

@pcr.command(name="reject", description="Reject pending PCR forms (Maincomm only).")
async def reject(interaction: discord.Interaction, name: str, reason: str):
    if not user_has_maincomm_role(interaction.user):
        await interaction.response.send_message("You don't have permission to reject pending PCRs.")
        return
    user_id = str(interaction.user.id)
    user_name = interaction.user.name
    pcr_doc = pcrs_collection.find_one({"name": name})
    if not pcr_doc:
        await interaction.response.send_message("PCR not found.")
        return
    update_fields = {"status": "Rejected"}
    pcrs_collection.update_one({"_id": pcr_doc["_id"]}, {"$set": update_fields})

    if not pcr_doc["private"]:
        log_audit(user_id, user_name, name, "reject", "Rejected PCR")

    pcr_doc = pcrs_collection.find_one({"name": name})  # Fetch updated PCR
    response = (f"**PCR '{name}' Rejected**\n"
                f"Item: {pcr_doc['item']}\n"
                f"Sources: {', '.join(pcr_doc['sources'])}\n"
                f"Rationale: {pcr_doc['rationale']}\n"
                f"**Status:** {pcr_doc['status'] or 'Draft?'}")
    await interaction.response.send_message(response)
    
    users_to_notify = []
    if not pcr_doc.get('shared_with'):
        users_to_notify = [pcr_doc['user_id']]
    else:
        users_to_notify = pcr_doc['shared_with'][:]
        if pcr_doc['user_id'] not in users_to_notify:
            users_to_notify.append(pcr_doc['user_id'])
    for uid in users_to_notify:
        user_obj = interaction.client.get_user(int(uid))
        if user_obj:
            try:
                await user_obj.send(f"**PCR '{name}' Rejected!**\nItem: {pcr_doc['item']}\n"
                                      f"**Sources:** {', '.join(pcr_doc['sources']) if pcr_doc['sources'] else 'None'}\n"
                                      f"**Rationale:** {pcr_doc['rationale'] or 'None'}\n"
                                      f"**Status:** {pcr_doc['status'] or 'Draft'}\n\n"
                                      f"**Reason:** {reason}")
            except discord.Forbidden:
                await interaction.response.send_message("I couldn't send a DM to one or more users. Please ask them to enable DMs.")

#############################################
# New Source Search Command Group           #
#############################################

# This group provides an interactive reaction-based interface for searching item sources.
source_group = app_commands.Group(name="source", description="Search for item sources")

def extract_details(url: str):
    """
    Given a URL, extract cost and brand information heuristically.
    """
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return "N/A", "N/A"
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        cost_matches = re.findall(r'\$\d+(?:\.\d{1,2})?', text)
        cost = cost_matches[0] if cost_matches else "N/A"
        og_site = soup.find("meta", property="og:site_name")
        brand = og_site["content"] if og_site and "content" in og_site.attrs else "N/A"
        return cost, brand
    except Exception as e:
        print(f"Error extracting details from {url}: {e}")
        return "N/A", "N/A"
VALID_SHOPPING_DOMAINS_SG = [
    "shopee.sg", "lazada.sg", "qoo10.sg", "amazon.sg", "carousell.sg", "fairprice.com.sg",
    "giant.sg", "coldstorage.com.sg", "harveynorman.com.sg", "bestdenki.com.sg", "apple.com/sg"
]

def is_valid_singapore_seller(url):
    """Check if the URL belongs to a Singapore-based shopping website."""
    return any(domain in url for domain in VALID_SHOPPING_DOMAINS_SG)

async def search_item(query: str):
    """Search for an item using DuckDuckGo, filtering for valid Singapore sellers."""
    results_list = []
    ddgs = DDGS()
    results = ddgs.text(f"buy {query} Singapore OR ship to Singapore", max_results=20)  

    for r in results:
        url = r.get('href', '')
        if is_valid_singapore_seller(url):  # Filter for SG-based sellers only
            cost, brand = extract_details(url)
            results_list.append({
                'name': r.get('title', 'No title'),
                'cost': cost,
                'brand': brand,
                'source': url
            })

    return results_list

@source_group.command(name="search", description="Search for item sources")
async def search_command(interaction: discord.Interaction, item: str):
    await interaction.response.defer()  # Prevents timeout error

    search_results = await search_item(item)
    
    if not search_results:
        await interaction.followup.send("No results found.")
        return

    embed = discord.Embed(title=f"Search Results for {item}", color=discord.Color.blue())
    
    for i, res in enumerate(search_results, start=1):
        embed.add_field(name=f"{i}. {res['name']}", value=f"💰 {res['cost']} | 🏷️ {res['brand']} | 🔗 [Source]({res['source']})", inline=False)
    
    await interaction.followup.send(embed=embed)
#############################################
# Discord Bot Client                        #
#############################################

class Client(discord.Client):
    ROLE_NAME = "Member"  
    EMOJI = "✅"
    TRACKED_MESSAGE_ID = 1342135518338613272
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
            await self.tree.sync()
            print("Slash commands and context menus synced!")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def setup_hook(self):
        self.tree.add_command(pcr)
        self.tree.add_command(source_group)

    async def on_message(self, message):
        if message.author == self.user:
            return

        try:
            if self.user in message.mentions:
                response = Request(message.content, self.template)
            elif message.content == "/cook":
                if any(role.name == "Cooking" for role in message.author.roles):
                    response = Cooking(self.template)
                else:
                    response = "You don't have permission to use this command."
            else:
                return

            for i in range(0, len(response), 2000):
                await message.channel.send(response[i:i+2000])

        except Exception as e:
            print(f"Error: {e}")
            await message.channel.send("An error occurred. Please try again.")
            
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

# Initialize bot with intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True  

client = Client(intents=intents)
client.run(discordkey)
