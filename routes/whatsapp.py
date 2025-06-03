# routes/whatsapp.py
from flask import Blueprint, request, jsonify
from services.twilio_messaging import send_template_message, send_whatsapp_message
from services.gemini import generate_gemini_response
from services.redis_utils import RedisService
from paynow import Paynow
from data.conversation_tree import conversation_tree
import time
import re
import threading
from datetime import datetime, timedelta

whatsapp_bp = Blueprint('whatsapp', __name__)
redis_service = RedisService()

# Paynow Configuration
paynow = Paynow(
    '20700',
    '3741f3f9-dcdb-4424-9f14-049b740fe7c6',
    'https://yourdomain.com/return-url',
    'https://yourdomain.com/cancel-url'
)

def clean_response(text):
    text = re.sub(r'[#*_`]+', '', text)
    return text.strip()

def poll_and_notify_user(sender_number, poll_url):
    """Polls payment status and sends result to user via WhatsApp."""
    for _ in range(12):  # 2 minutes max (12 x 10 sec)
        status = paynow.check_transaction_status(poll_url)

        if status.paid:
            message = "✅ *Payment successful!* Thank you for your purchase. You now have full access for 30 days."
            # Update user session with payment expiry
            session = redis_service.get_user_session(sender_number) or {}
            session['payment_expiry'] = str((datetime.now() + timedelta(days=30)).timestamp())
            redis_service.save_user_session(sender_number, session)
            break
        elif status.status == 'cancelled':
            message = "❌ *Payment cancelled.*"
            break
        elif status.status in ['failed', 'reversed']:
            message = f"❌ *Payment failed.* Status: {status.status}"
            break
        elif status.status == 'awaiting delivery':
            message = "⌛ *Payment received*, waiting for delivery confirmation."
            break
        time.sleep(10)
    else:
        message = "⚠️ *Payment not confirmed yet.* Please check your EcoCash menu to complete it manually."

    send_whatsapp_message(sender_number, message)


def handle_payment_flow(sender_number, sender_name, user_message):
    session = redis_service.get_user_session(sender_number) or {}
    step = session.get("payment_step")

    if step == "awaiting_number":
        # Validate EcoCash number
        if (user_message.isdigit() and len(user_message) == 10
                and user_message.startswith(('077', '078', '071'))):
            session.update({
                "payment_phone": user_message,
                "payment_step": "awaiting_confirmation"
            })
            redis_service.save_user_session(sender_number, session)

            send_whatsapp_message(sender_number,
                                  f"📱 Confirm payment info:\nEcoCash Number: {user_message}\n"
                                  "Amount: USD 0.10\n\nReply *yes* to confirm or *no* to restart.")
            return {"status": "awaiting_confirmation"}, 200
        else:
            send_whatsapp_message(sender_number,
                                  "❌ Invalid number. Enter a valid Zimbabwean EcoCash number (e.g., 0771234567):")
            return {"status": "invalid_number"}, 200

    elif step == "awaiting_confirmation":
        if user_message.lower() == 'yes':
            # Create and send payment
            payment = paynow.create_payment('WhatsApp Subscription', f'{sender_number}@yourapp.com')
            payment.add('1 Month Access', 0.10)

            response = paynow.send_mobile(payment,
                                          session["payment_phone"],
                                          'ecocash')

            if response.success:
                # Start polling in background
                threading.Thread(
                    target=poll_and_notify_user,
                    args=(sender_number, response.poll_url)
                ).start()

                send_whatsapp_message(sender_number,
                                      f"✅ Payment request sent to {session['payment_phone']} "
                                      "via EcoCash.\nPlease complete the payment on your phone.")

                # Clear payment state but keep pending question
                session.pop("payment_step", None)
                session.pop("payment_phone", None)
                redis_service.save_user_session(sender_number, session)

                return {"status": "payment_initiated"}, 200
            else:
                send_whatsapp_message(sender_number,
                                      f"❌ Failed to initiate payment: {response.error}\n"
                                      "Please try again or contact support.")
                return {"status": "payment_failed"}, 200

        elif user_message.lower() == 'no':
            session["payment_step"] = "awaiting_number"
            redis_service.save_user_session(sender_number, session)
            send_whatsapp_message(sender_number,
                                  "🔁 Let's try again. Please enter your EcoCash number (e.g., 0771234567):")
            return {"status": "restarted_payment"}, 200
        else:
            send_whatsapp_message(sender_number,
                                  "Please reply *yes* to confirm or *no* to restart.")
            return {"status": "invalid_confirmation"}, 200

    # Default case - start payment flow
    session.update({
        "payment_step": "awaiting_number",
        "pending_question": user_message
    })
    redis_service.save_user_session(sender_number, session)

    send_whatsapp_message(sender_number,
                          "👋 Welcome to our payment system!\nNote: We currently support only *EcoCash* payments.\n\n"
                          "Please enter your EcoCash number (e.g., 0771234567):")
    return {"status": "awaiting_number"}, 200


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

        # Check if user has active payment
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
            payment_result = handle_payment_flow(sender_number, sender_name, user_message)
            if payment_result:
                return jsonify(payment_result[0]), payment_result[1]

        current_state = session["current"]
        history = session.get("history", [])

        # Check for next keyword matches in conversation tree
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
                    return jsonify({"status": "template_sent"}), 200

        # If no keyword match, handle free-form input
        if has_active_payment:
            # For paid users, use Gemini with conversation history
            history_messages = redis_service.get_conversation_history(sender_number)
            gemini_response = generate_gemini_response(user_message, history_messages)
            send_whatsapp_message(sender_number, clean_response(gemini_response))
            redis_service.add_to_conversation_history(sender_number, "assistant", gemini_response)
        else:
            # For non-paid users, check if they want to pay
            if any(word in user_message for word in ["pay", "payment", "subscribe", "access"]):
                session["payment_step"] = "awaiting_number"
                session["pending_question"] = incoming_message
                redis_service.save_user_session(sender_number, session)
                send_template_message(sender_number, sender_name, "HX9a38645ef48259d6bb3556f74236e980")
                return jsonify({"status": "awaiting_payment_method"}), 200
            else:
                # Re-send the last template if user didn't follow expected path
                if session.get("last_template"):
                    send_template_message(sender_number, sender_name, session["last_template"])
                else:
                    send_whatsapp_message(sender_number, "Please select one of the menu options to continue.")

        return jsonify({"status": "message_processed"}), 200

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    # # 🛠️ DEFAULT FALLBACK RETURN to avoid returning None
    # return jsonify({"status": "no_action_taken"}), 200
