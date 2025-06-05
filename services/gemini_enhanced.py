# services/gemini_enhanced.py
import google.generativeai as genai
from services.qdrant_service import QdrantService
import os
from typing import List, Dict, Optional
import logging


class EnhancedGeminiService:
    def __init__(self):
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.qdrant_service = QdrantService()
        self.logger = logging.getLogger(__name__)

    def generate_enhanced_response(self,
                                   user_message: str,
                                   user_number: str,
                                   conversation_history: List[Dict] = None,
                                   include_global_context: bool = True) -> str:
        """Generate response using Gemini with Qdrant context"""
        try:
            # Get relevant context from Qdrant
            user_context = self.qdrant_service.get_user_conversation_context(
                user_number, user_message, limit=3
            )

            global_context = ""
            if include_global_context:
                global_context = self.qdrant_service.get_global_conversation_context(
                    user_message, limit=3
                )

            # Build the prompt with context
            prompt_parts = []

            # System context
            prompt_parts.append(
                "You are a helpful WhatsApp chatbot assistant. Provide clear, concise, and helpful responses. "
                "Use the conversation context below to provide more personalized and relevant answers."
            )

            # Add user-specific context if available
            if user_context:
                prompt_parts.append(f"\n{user_context}")

            # Add global context if available
            if global_context:
                prompt_parts.append(f"\n{global_context}")

            # Add recent conversation history
            if conversation_history:
                prompt_parts.append("\nRecent conversation:")
                for msg in conversation_history[-5:]:  # Last 5 messages
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    prompt_parts.append(f"{role}: {msg.get('content', '')}")

            # Add current user message
            prompt_parts.append(f"\nUser's current question: {user_message}")
            prompt_parts.append("\nPlease provide a helpful response:")

            full_prompt = "\n".join(prompt_parts)

            # Generate response with Gemini
            response = self.model.generate_content(full_prompt)
            generated_response = response.text

            # Store the conversation in Qdrant for future context
            self.qdrant_service.store_conversation(
                user_number=user_number,
                message=user_message,
                response=generated_response,
                message_type="ai_conversation"
            )

            return generated_response

        except Exception as e:
            self.logger.error(f"Error generating enhanced response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."

    def generate_contextual_response(self,
                                     user_message: str,
                                     user_number: str,
                                     specific_context: str = None) -> str:
        """Generate response with specific context provided"""
        try:
            prompt_parts = [
                "You are a helpful WhatsApp chatbot assistant. Use the provided context to give accurate and helpful responses."
            ]

            if specific_context:
                prompt_parts.append(f"\nContext: {specific_context}")

            prompt_parts.append(f"\nUser question: {user_message}")
            prompt_parts.append("\nResponse:")

            full_prompt = "\n".join(prompt_parts)

            response = self.model.generate_content(full_prompt)
            generated_response = response.text

            # Store the conversation
            self.qdrant_service.store_conversation(
                user_number=user_number,
                message=user_message,
                response=generated_response,
                message_type="contextual_conversation"
            )

            return generated_response

        except Exception as e:
            self.logger.error(f"Error generating contextual response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."

    def search_and_respond(self, user_message: str, user_number: str) -> str:
        """Search Qdrant for relevant info and generate response"""
        try:
            # Search for relevant conversations
            similar_conversations = self.qdrant_service.search_similar_conversations(
                user_message, user_number=None, limit=5
            )

            if not similar_conversations:
                return self.generate_enhanced_response(user_message, user_number, include_global_context=False)

            # Build context from similar conversations
            context_parts = []
            for conv in similar_conversations:
                if conv["message_type"] == "bot":
                    context_parts.append(conv["message"][:200])

            context = "\n".join(context_parts)

            prompt = f"""
            Based on similar previous conversations, here's relevant information:
            {context}

            User's question: {user_message}

            Please provide a comprehensive answer that incorporates the relevant information above while directly addressing the user's question:
            """

            response = self.model.generate_content(prompt)
            generated_response = response.text

            # Store the conversation
            self.qdrant_service.store_conversation(
                user_number=user_number,
                message=user_message,
                response=generated_response,
                message_type="search_based_conversation"
            )

            return generated_response

        except Exception as e:
            self.logger.error(f"Error in search and respond: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."


# Backward compatibility function
def generate_gemini_response(user_message: str, conversation_history: List[Dict] = None,
                             user_number: str = None) -> str:
    """Backward compatible function that uses enhanced Gemini service"""
    service = EnhancedGeminiService()

    if user_number:
        return service.generate_enhanced_response(
            user_message=user_message,
            user_number=user_number,
            conversation_history=conversation_history
        )
    else:
        # Fallback to basic Gemini without Qdrant integration
        try:
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            model = genai.GenerativeModel('gemini-1.5-flash')

            prompt_parts = []
            if conversation_history:
                prompt_parts.append("Previous conversation:")
                for msg in conversation_history[-5:]:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    prompt_parts.append(f"{role}: {msg.get('content', '')}")

            prompt_parts.append(f"User: {user_message}")
            prompt_parts.append("Assistant:")

            response = model.generate_content("\n".join(prompt_parts))
            return response.text

        except Exception as e:
            return "I apologize, but I'm having trouble processing your request right now. Please try again."