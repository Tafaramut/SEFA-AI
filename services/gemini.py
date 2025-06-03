from google.generativeai import GenerativeModel
from datetime import datetime
import json

# Initialize the model
model = GenerativeModel(model_name="gemini-2.0-flash")


def generate_gemini_response(prompt, conversation_history=None):
    """
    Generate a response from Gemini, optionally using conversation history for context

    Args:
        prompt (str): The user's input message
        conversation_history (list): List of previous messages in the conversation
                                  Each item should be a dict with 'role' and 'message'

    Returns:
        str: The generated response
    """
    try:
        if conversation_history:
            # Format the conversation history for Gemini
            chat = model.start_chat(history=[])

            # Add history to the chat (excluding the current prompt)
            for msg in conversation_history:
                if msg['role'] == 'user':
                    chat.send_message(msg['message'])
                # Note: We don't add assistant responses to history to avoid confusion

            # Get response with context
            response = chat.send_message(prompt)
        else:
            # Single prompt without history
            response = model.generate_content(prompt)

        # Clean and return the response
        if response.text:
            return response.text
        else:
            return "I didn't get a response. Could you please rephrase your question?"

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Sorry, I encountered an error while processing your request. Please try again."