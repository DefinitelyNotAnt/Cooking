from dotenv import load_dotenv
import os
import re
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
import random

# Load environment variables for the chatbot
load_dotenv()
api_key: str = os.getenv('apikey')
model: str = "deepseek-r1-distill-llama-70b"

# Initialize model
deepseek = ChatGroq(api_key=api_key, model_name=model)
parser = StrOutputParser()
deepseek_chain = deepseek | parser

# Load and split data
loader = TextLoader('data.txt', encoding='utf-8')
data = loader.load()

# Chatbot functions
def Cooking(template):
    question = """
    Give me a R take with a high R score. 
    Respond only with the text of the R take.
    Do not talk about movies, famous influencers outside Japan, or robotics.
    """
    formatted_template = template.format(context=data, question=question)
    answer = deepseek_chain.invoke(formatted_template)
    cleaned_answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    return cleaned_answer

def Request(request_text, template):
    formatted_template = template.format(context=data, question=request_text)
    answer = deepseek_chain.invoke(formatted_template)
    cleaned_answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    return cleaned_answer
