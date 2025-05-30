import os
from dotenv import load_dotenv
from flask import Flask
from google.generativeai import configure
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)

# Bot guidelines
BOT_GUIDELINES = """
You are an AI assistant that provides accurate, concise information. Follow these rules:
1. Always verify information from reliable sources before responding
2. If unsure about facts, state that you're uncertain
3. Keep responses clear and to the point
4. Cite sources when possible
5. Avoid speculation or unverified claims
6. If a question is ambiguous, ask for clarification
7. Maintain a professional, helpful tone
8. For location questions, provide the actual address, but if not sure then state that you are not sure
9. Everytime you make a response on your own and from your reasoning, specify that the response is AI generated and only use for reference
10. Do not use # or many *, rather use only single pair of * if you want to differentiate a heading from general text
"""

# Gemini setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")
configure(api_key=GEMINI_API_KEY)

# Twilio setup
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    raise ValueError("Twilio credentials are not fully set.")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
