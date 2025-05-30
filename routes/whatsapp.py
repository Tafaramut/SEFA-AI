from flask import Blueprint, request, jsonify
from services.twilio_messaging import send_template_message, send_whatsapp_message
from services.deepseek import generate_deepseek_response
from services.gemini import generate_gemini_response
from paynow import Paynow
from data.conversation_tree import conversation_tree
import time
import re
import threading

whatsapp_bp = Blueprint('whatsapp', __name__)
user_states = {}

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
            message = "✅ *Payment successful!* Thank you for your purchase."
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
    state = user_states.get(sender_number, {})
    step = state.get("payment_step")

    if step == "awaiting_number":
        # Validate EcoCash number
        if (user_message.isdigit() and len(user_message) == 10
                and user_message.startswith(('077', '078', '071'))):
            user_states[sender_number].update({
                "payment_phone": user_message,
                "payment_step": "awaiting_confirmation"
            })
            send_whatsapp_message(sender_number,
                                  f"📱 Confirm payment info:\nEcoCash Number: {user_message}\n"
                                  "Amount: USD 0.10\n\nReply *yes* to confirm or *no* to restart.")
            return {"status": "awaiting_confirmation"}, 200
        else:
            send_whatsapp_message(sender_number,
                                  "❌ Invalid number. Enter a valid Zimbabwean EcoCash number (e.g., 0771234567):")
            return {"status": "invalid_number"}, 200

    elif step == "awaiting_confirmation":
        if 'yes' in user_message:
            # Create and send payment
            payment = paynow.create_payment('WhatsApp Order', f'{sender_number}@yourapp.com')
            payment.add('Product Purchase', 0.10)

            response = paynow.send_mobile(payment,
                                          user_states[sender_number]["payment_phone"],
                                          'ecocash')

            if response.success:
                # Start polling in background
                threading.Thread(
                    target=poll_and_notify_user,
                    args=(sender_number, response.poll_url)
                ).start()

                send_whatsapp_message(sender_number,
                                      f"✅ Payment request sent to {user_states[sender_number]['payment_phone']} "
                                      "via EcoCash.\nPlease complete the payment on your phone.")

                # Return to normal flow
                original_message = user_states[sender_number].get("pending_question", "")
                gemini_reply = generate_gemini_response(original_message)
                send_whatsapp_message(sender_number, clean_response(gemini_reply))

                # Clear payment state
                user_states[sender_number].pop("payment_step", None)
                return {"status": "payment_initiated"}, 200
            else:
                send_whatsapp_message(sender_number,
                                      f"❌ Failed to initiate payment: {response.error}\n"
                                      "Please try again or contact support.")
                return {"status": "payment_failed"}, 200

        elif 'no' in user_message:
            user_states[sender_number]["payment_step"] = "awaiting_number"
            send_whatsapp_message(sender_number,
                                  "🔁 Let's try again. Please enter your EcoCash number (e.g., 0771234567):")
            return {"status": "restarted_payment"}, 200
        else:
            send_whatsapp_message(sender_number,
                                  "Please reply *yes* to confirm or *no* to restart.")
            return {"status": "invalid_confirmation"}, 200

    # Default case - start payment flow
    user_states[sender_number].update({
        "payment_step": "awaiting_number",
        "pending_question": user_message
    })
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

        if incoming_message and sender_number:
            user_message = incoming_message.strip().lower()

            # Initialize user session if it's their first message
            if sender_number not in user_states:
                user_states[sender_number] = {
                    "current": conversation_tree["hi"],
                    "history": []
                }
                send_template_message(sender_number, sender_name, conversation_tree["hi"]["template_sid"])
                return jsonify({"status": "initial_template_sent"}), 200

            state_data = user_states[sender_number]
            current_state = state_data["current"]
            history = state_data["history"]

            # Handle "start over"
            if user_message == "start over":
                user_states[sender_number]["current"] = conversation_tree["hi"]
                user_states[sender_number]["history"] = []
                send_template_message(sender_number, sender_name, conversation_tree["hi"]["template_sid"])
                return jsonify({"status": "restarted"}), 200

            # Handle "back"
            if user_message == "back":
                if history:
                    previous_state = history.pop()
                    user_states[sender_number]["current"] = previous_state
                    send_template_message(sender_number, sender_name, previous_state["template_sid"])
                    return jsonify({"status": "back_to_previous"}), 200
                else:
                    send_whatsapp_message(sender_number, "You're already at the beginning. Type 'Start Over' to restart.")
                    return jsonify({"status": "no_previous_state"}), 200

            # Check for next keyword matches
            if "next" in current_state:
                next_steps = current_state["next"]
                for keyword in next_steps:
                    if re.search(re.escape(keyword.lower()), user_message, re.IGNORECASE):
                        next_state = next_steps[keyword]
                        history.append(current_state)
                        user_states[sender_number]["current"] = next_state
                        send_template_message(sender_number, sender_name, next_state["template_sid"])
                        return jsonify({"status": "template_sent"}), 200

            # Check payment flow
            if "payment_step" in state_data:
                payment_result = handle_payment_flow(sender_number, sender_name, user_message)
                if payment_result:
                    return jsonify(payment_result[0]), payment_result[1]
            else:
                user_states[sender_number]["payment_step"] = "awaiting_method"
                user_states[sender_number]["pending_question"] = incoming_message
                send_template_message(sender_number, sender_name, "HX9a38645ef48259d6bb3556f74236e980")
                return jsonify({"status": "awaiting_payment_method"}), 200

        else:
            send_whatsapp_message(sender_number, "Please respond with a valid message.")
            return jsonify({"status": "invalid_input"}), 200

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    # 🛠️ DEFAULT FALLBACK RETURN to avoid returning None
    return jsonify({"status": "no_action_taken"}), 200
