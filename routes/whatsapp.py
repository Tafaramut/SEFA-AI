# # routes/whatsapp.py
# from flask import Blueprint, request, jsonify
# from services.twilio_messaging import send_template_message, send_whatsapp_message
# from services.gemini import generate_gemini_response
# from services.redis_utils import RedisService
# from services.payment_service import PaymentService
# from data.conversation_tree import conversation_tree
# import re
#
# whatsapp_bp = Blueprint('whatsapp', __name__)
# redis_service = RedisService()
# payment_service = PaymentService()
#
#
# def clean_response(text):
#     text = re.sub(r'[#*_`]+', '', text)
#     return text.strip()
#
# # Add these endpoints to your main Flask app (where you have the /whatsapp route):
#
# @whatsapp_bp.route('/return-url', methods=['POST', 'GET'])
# def paynow_return():
#     """Handle Paynow return callback - when user completes/cancels payment"""
#     print(f"Paynow return callback: {request.form}")
#     print(f"Paynow return args: {request.args}")
#     # You can process the return data here if needed
#     return "Payment return processed", 200
#
# @whatsapp_bp.route('/result-url', methods=['POST', 'GET'])
# def paynow_result():
#     """Handle Paynow result callback - payment status updates"""
#     print(f"Paynow result callback: {request.form}")
#     print(f"Paynow result args: {request.args}")
#     # You can process the result data here if needed
#     return "Payment result processed", 200
#
# @whatsapp_bp.route('/whatsapp', methods=['POST'])
# def whatsapp_webhook():
#     try:
#         incoming_message = request.form.get('Body')
#         sender_number = request.form.get('From')
#         sender_name = request.form.get('ProfileName', 'there')
#
#         if not incoming_message or not sender_number:
#             send_whatsapp_message(sender_number, "Please respond with a valid message.")
#             return jsonify({"status": "invalid_input"}), 200
#
#         user_message = incoming_message.strip().lower()
#         session = redis_service.get_user_session(sender_number)
#
#         # Check if user has an active payment
#         has_active_payment = redis_service.check_payment_status(sender_number) if session else False
#
#         # Initialize user session if it's their first message
#         if not session:
#             session = {
#                 "current": conversation_tree["hi"],
#                 "history": [],
#                 "last_template": None
#             }
#             redis_service.save_user_session(sender_number, session)
#             send_template_message(sender_number, sender_name, conversation_tree["hi"]["template_sid"])
#             return jsonify({"status": "initial_template_sent"}), 200
#
#         # Add user message to conversation history
#         redis_service.add_to_conversation_history(sender_number, "user", user_message)
#
#         # Handle "start over"
#         if user_message == "start over":
#             session = {
#                 "current": conversation_tree["hi"],
#                 "history": [],
#                 "last_template": None
#             }
#             redis_service.save_user_session(sender_number, session)
#             send_template_message(sender_number, sender_name, conversation_tree["hi"]["template_sid"])
#             return jsonify({"status": "restarted"}), 200
#
#         # Handle "back"
#         if user_message == "back":
#             if session.get("history"):
#                 previous_state = session["history"].pop()
#                 session["current"] = previous_state
#                 redis_service.save_user_session(sender_number, session)
#                 send_template_message(sender_number, sender_name, previous_state["template_sid"])
#                 return jsonify({"status": "back_to_previous"}), 200
#             else:
#                 send_whatsapp_message(sender_number, "You're already at the beginning. Type 'Start Over' to restart.")
#                 return jsonify({"status": "no_previous_state"}), 200
#
#         # Get current state from session - MOVED THIS UP
#         current_state = session.get("current", conversation_tree["hi"])
#         history = session.get("history", [])
#
#         # Check if in payment flow
#         if "payment_step" in session:
#             payment_result = payment_service.handle_payment_flow(sender_number, sender_name, user_message)
#             if payment_result:
#                 if payment_result["status"] == "payment_initiated":
#                     return jsonify(payment_result), 200
#                 if payment_result["status"] == "payment_failed":
#                     return jsonify(payment_result), 200
#
#         # Skip payment flow if user is already paid
#         if session.get("is_paid"):
#             # Check for next keyword matches in conversation tree
#             keyword_matched = False
#             if "next" in current_state:
#                 next_steps = current_state["next"]
#                 for keyword in next_steps:
#                     if re.search(re.escape(keyword.lower()), user_message, re.IGNORECASE):
#                         next_state = next_steps[keyword]
#                         history.append(current_state)
#                         session["current"] = next_state
#                         session["history"] = history
#                         session["last_template"] = next_state.get("template_sid")
#                         redis_service.save_user_session(sender_number, session)
#
#                         send_template_message(sender_number, sender_name, next_state["template_sid"])
#                         keyword_matched = True
#                         return jsonify({"status": "template_sent"}), 200
#
#             # If no keyword match, handle free-form input
#             if not keyword_matched:
#                 history_messages = redis_service.get_conversation_history(sender_number)
#                 gemini_response = generate_gemini_response(user_message, history_messages)
#                 send_whatsapp_message(sender_number, clean_response(gemini_response))
#                 redis_service.add_to_conversation_history(sender_number, "assistant", gemini_response)
#                 return jsonify({"status": "message_processed"}), 200
#
#         # Handle payment prompts if not paid
#         if not has_active_payment:
#             # PAYMENT TRIGGER 1: Explicit payment keywords
#             if any(word in user_message for word in ["pay", "payment", "subscribe", "access"]):
#                 session["payment_step"] = "awaiting_number"
#                 session["pending_question"] = incoming_message
#                 redis_service.save_user_session(sender_number, session)
#                 send_template_message(sender_number, sender_name, "HX9a38645ef48259d6bb3556f74236e980")
#                 return jsonify({"status": "awaiting_payment_method"}), 200
#
#             # PAYMENT TRIGGER 2: End of conversation tree (no more templates)
#             elif "next" not in current_state or not current_state["next"]:
#                 session["payment_step"] = "awaiting_number"
#                 session["pending_question"] = incoming_message
#                 redis_service.save_user_session(sender_number, session)
#
#                 send_whatsapp_message(sender_number,
#                                       "To get personalized AI responses and continue our conversation, please subscribe to our premium service.")
#                 send_template_message(sender_number, sender_name, "HX9a38645ef48259d6bb3556f74236e980")
#                 return jsonify({"status": "end_of_tree_payment_prompt"}), 200
#
#         return jsonify({"status": "message_processed"}), 200
#
#     except Exception as e:
#         print(f"Error processing webhook: {e}")
#         return jsonify({"status": "error", "message": str(e)}), 500

# routes/whatsapp.py
from flask import Blueprint, request, jsonify
from services.twilio_messaging import send_template_message, send_whatsapp_message
from services.gemini import generate_gemini_response
from services.redis_utils import RedisService
from services.payment_service import PaymentService
from data.conversation_tree import conversation_tree
import re

whatsapp_bp = Blueprint('whatsapp', __name__)
redis_service = RedisService()
payment_service = PaymentService()


def clean_response(text):
    text = re.sub(r'[#*_`]+', '', text)
    return text.strip()
# Add these endpoints to your main Flask app (where you have the /whatsapp route):

@whatsapp_bp.route('/return-url', methods=['POST', 'GET'])
def paynow_return():
    """Handle Paynow return callback - when user completes/cancels payment"""
    print(f"Paynow return callback: {request.form}")
    print(f"Paynow return args: {request.args}")
    # You can process the return data here if needed
    return "Payment return processed", 200

@whatsapp_bp.route('/result-url', methods=['POST', 'GET'])
def paynow_result():
    """Handle Paynow result callback - payment status updates"""
    print(f"Paynow result callback: {request.form}")
    print(f"Paynow result args: {request.args}")
    # You can process the result data here if needed
    return "Payment result processed", 200

@whatsapp_bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    try:
        incoming_message = request.form.get('Body')
        sender_number = request.form.get('From')
        sender_name = request.form.get('ProfileName', 'there')

        if not incoming_message or not sender_number:
            send_whatsapp_message(sender_number, "Please respond with a valid message.")
            return jsonify({"status": "invalid_input"}), 200

        user_message = incoming_message.strip().lower()
        session = redis_service.get_user_session(sender_number)

        # Check if user has an active payment
        has_active_payment = redis_service.check_payment_status(sender_number) if session else False

        # Initialize user session if it's their first message
        if not session:
            session = {
                "current": conversation_tree["hi"],
                "history": [],
                "last_template": None
            }
            redis_service.save_user_session(sender_number, session)
            send_template_message(sender_number, sender_name, conversation_tree["hi"]["template_sid"])
            return jsonify({"status": "initial_template_sent"}), 200

        # Add user message to conversation history
        redis_service.add_to_conversation_history(sender_number, "user", user_message)

        # Handle "start over"
        if user_message == "start over":
            session = {
                "current": conversation_tree["hi"],
                "history": [],
                "last_template": None
            }
            redis_service.save_user_session(sender_number, session)
            send_template_message(sender_number, sender_name, conversation_tree["hi"]["template_sid"])
            return jsonify({"status": "restarted"}), 200

        # Handle "back"
        if user_message == "back":
            if session.get("history"):
                previous_state = session["history"].pop()
                session["current"] = previous_state
                redis_service.save_user_session(sender_number, session)
                send_template_message(sender_number, sender_name, previous_state["template_sid"])
                return jsonify({"status": "back_to_previous"}), 200
            else:
                send_whatsapp_message(sender_number, "You're already at the beginning. Type 'Start Over' to restart.")
                return jsonify({"status": "no_previous_state"}), 200

        # Check if in payment flow
        if "payment_step" in session:
            payment_result = payment_service.handle_payment_flow(sender_number, sender_name, user_message)
            if payment_result:
                if payment_result["status"] == "payment_initiated":
                    return jsonify(payment_result), 200
                if payment_result["status"] == "payment_failed":
                    return jsonify(payment_result), 200

        # Skip payment flow if user is already paid
        if session.get("is_paid"):
            # Continue with the conversation
            current_state = session["current"]
            history = session.get("history", [])

            # Check for next keyword matches in conversation tree
            keyword_matched = False
            if "next" in current_state:
                next_steps = current_state["next"]
                for keyword in next_steps:
                    if re.search(re.escape(keyword.lower()), user_message, re.IGNORECASE):
                        next_state = next_steps[keyword]
                        history.append(current_state)
                        session["current"] = next_state
                        session["last_template"] = next_state.get("template_sid")
                        redis_service.save_user_session(sender_number, session)

                        send_template_message(sender_number, sender_name, next_state["template_sid"])
                        keyword_matched = True
                        return jsonify({"status": "template_sent"}), 200

            # If no keyword match, handle free-form input
            if not keyword_matched:
                history_messages = redis_service.get_conversation_history(sender_number)
                gemini_response = generate_gemini_response(user_message, history_messages)
                send_whatsapp_message(sender_number, clean_response(gemini_response))
                redis_service.add_to_conversation_history(sender_number, "assistant", gemini_response)
                return jsonify({"status": "message_processed"}), 200

        # Handle payment prompts if not paid
        if not has_active_payment:
            # PAYMENT TRIGGER 1: Explicit payment keywords
            if any(word in user_message for word in ["pay", "payment", "subscribe", "access"]):
                session["payment_step"] = "awaiting_number"
                session["pending_question"] = incoming_message
                redis_service.save_user_session(sender_number, session)
                send_template_message(sender_number, sender_name, "HX9a38645ef48259d6bb3556f74236e980")
                return jsonify({"status": "awaiting_payment_method"}), 200

            # PAYMENT TRIGGER 2: End of conversation tree (no more templates)
            elif "next" not in current_state or not current_state["next"]:
                session["payment_step"] = "awaiting_number"
                session["pending_question"] = incoming_message
                redis_service.save_user_session(sender_number, session)

                send_whatsapp_message(sender_number,
                                      "To get personalized AI responses and continue our conversation, please subscribe to our premium service.")
                send_template_message(sender_number, sender_name, "HX9a38645ef48259d6bb3556f74236e980")
                return jsonify({"status": "end_of_tree_payment_prompt"}), 200

        return jsonify({"status": "message_processed"}), 200

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500