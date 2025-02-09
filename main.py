from dotenv import load_dotenv
import os 
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
import discord
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

        try:
            # If bot is mentioned, process the request
            if self.user in message.mentions:
                response = Request(message.content, self.template)
            
            elif message.content == "/cook":
                response = Cooking(self.template)

            else:
                return  # Ignore other messages

            # Send response in chunks
            for i in range(0, len(response), 2000):
                await message.channel.send(response[i:i+2000])

        except Exception as e:
            print(f"Error: {e}")
            await message.channel.send("An error occurred while processing your request.")

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

intents = discord.Intents.default()
intents.message_content = True

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
