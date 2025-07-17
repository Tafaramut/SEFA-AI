from flask import Flask, request, session
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import uuid
import os
import logging
from paynow import Paynow
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=1),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# PayNow credentials
PAYNOW_INTEGRATION_ID = os.environ.get('PAYNOW_INTEGRATION_ID')
PAYNOW_INTEGRATION_KEY = os.environ.get('PAYNOW_INTEGRATION_KEY')

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Mock data storage (replace with actual database)
mock_registrations = {}
mock_tickets = {}

# Improved Templates
MAIN_MENU = """🏃‍♂️ *Welcome to Mr Pace Online Registration* 🏃‍♀️

Please select an option below:
1️⃣ Register for Heroes Marathon
2️⃣ Check Registration Status

Reply with the number of your choice."""

RACE_SELECTION = """🏃‍♂️ *Select Your Race Distance* 🏃‍♀️

Please choose your preferred race distance:
1️⃣ 5KM ($20)
2️⃣ 10KM ($20)
3️⃣ 21KM ($20)

Reply with the number of your choice (1-3)."""

REGISTRATION_FORM = """📝 *Registration Form*

Please fill in your details using this EXACT format:

Full Name: [Your Name]
Email: [Your Email]
Phone Number: [Your Phone]
National Id Number: [Your ID]
Gender: [Male/Female]
Date of Birth: [DD/MM/YYYY]
T-Shirt Size: [XS/S/M/L/XL/XXL]

⚠️ *Important:*
• Use the exact format above
• The phone number should be your EcoCash number
• Copy and paste the field names exactly as shown"""


# Additional helper function to make form parsing more robust
def parse_registration_form(message):
    """Parse registration form with better error handling"""
    lines = message.strip().split('\n')
    form_data = {}

    # Expected field mappings
    field_mappings = {
        'full name': 'full_name',
        'email': 'email',
        'phone number': 'phone_number',
        'national id number': 'national_id_number',
        'gender': 'gender',
        'date of birth': 'date_of_birth',
        't-shirt size': 't_shirt_size',
        't shirt size': 't_shirt_size',
        'tshirt size': 't_shirt_size'
    }

    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            # Normalize the key
            normalized_key = key.strip().lower()

            # Map to standard field name
            if normalized_key in field_mappings:
                form_data[field_mappings[normalized_key]] = value.strip()
            else:
                # Try fuzzy matching for common variations
                for expected_key, mapped_key in field_mappings.items():
                    if expected_key in normalized_key or normalized_key in expected_key:
                        form_data[mapped_key] = value.strip()
                        break

    return form_data


def handle_reset_commands(phone_key, message):
    """Handle reset and restart commands"""
    reset_commands = ['reset', 'restart', 'start over', 'menu', 'help', 'hi', 'hello', 'start']

    if message.lower().strip() in reset_commands:
        # Clear session data
        if phone_key in session:
            session.pop(phone_key, None)
            session.modified = True

        # Initialize fresh session
        session[phone_key] = {
            'state': bot.states['MAIN_MENU'],
            'data': {}
        }
        session.modified = True

        logger.info(f"Session reset for {phone_key}")
        return True
    return False


class ChatBot:
    def __init__(self):
        self.states = {
            'START': 'start',
            'MAIN_MENU': 'main_menu',
            'RACE_SELECTION': 'race_selection',
            'REGISTRATION_FORM': 'registration_form',
            'PAYMENT': 'payment',
            'TICKET_CHECK': 'ticket_check',
            'COMPLETED': 'completed'
        }
        logger.info("ChatBot initialized with states: %s", self.states)

    def get_user_state(self, phone_number):
        """Get current state for user"""
        logger.debug("Getting state for %s", phone_number)
        logger.debug("Current session data: %s", dict(session))

        if phone_number not in session:
            logger.info("New user session for %s", phone_number)
            session[phone_number] = {
                'state': self.states['START'],
                'data': {}
            }
            session.modified = True
            logger.debug("Created new session: %s", session[phone_number])

        state = session[phone_number].get('state', self.states['START'])
        logger.debug("Current state for %s: %s", phone_number, state)
        return state

    def set_user_state(self, phone_number, state):
        """Set state for user"""
        logger.debug("Setting state for %s to %s", phone_number, state)
        if phone_number not in session:
            session[phone_number] = {'data': {}}
        session[phone_number]['state'] = state
        session.modified = True
        logger.debug("New session data after state change: %s", dict(session))

    def get_user_data(self, phone_number):
        """Get user data"""
        logger.debug("Getting data for %s", phone_number)
        if phone_number not in session:
            logger.info("Creating new session for %s in get_user_data", phone_number)
            session[phone_number] = {
                'state': self.states['START'],
                'data': {}
            }
            session.modified = True
        return session[phone_number].get('data', {})

    def set_user_data(self, phone_number, key, value):
        """Set user data"""
        logger.debug("Setting data for %s: %s = %s", phone_number, key, value)
        if phone_number not in session:
            logger.info("Creating new session for %s in set_user_data", phone_number)
            session[phone_number] = {
                'state': self.states['START'],
                'data': {}
            }
        if 'data' not in session[phone_number]:
            session[phone_number]['data'] = {}
        session[phone_number]['data'][key] = value
        session.modified = True
        logger.debug("Updated session data: %s", session[phone_number]['data'])


# Initialize chatbot
bot = ChatBot()


# Add these debug functions to help identify issues

def debug_user_data(phone_key, context=""):
    """Debug function to log user data"""
    try:
        user_data = bot.get_user_data(phone_key)
        logger.info(f"DEBUG {context} - User data for {phone_key}: {user_data}")

        # Check for None values
        none_fields = [k for k, v in user_data.items() if v is None]
        if none_fields:
            logger.warning(f"DEBUG {context} - None values found in fields: {none_fields}")

        return user_data
    except Exception as e:
        logger.error(f"DEBUG {context} - Error getting user data: {str(e)}")
        return {}


def debug_session_state(phone_key, context=""):
    """Debug function to log session state"""
    try:
        current_state = bot.get_user_state(phone_key)
        session_data = session.get(phone_key, {})
        logger.info(f"DEBUG {context} - State: {current_state}, Session: {session_data}")
    except Exception as e:
        logger.error(f"DEBUG {context} - Error getting session state: {str(e)}")


# Modified webhook function with better debugging
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        # Initialize response early
        resp = MessagingResponse()
        msg = resp.message()

        # Get message data
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')

        if not incoming_msg or not from_number:
            logger.error("Invalid request - missing message or from number")
            return "Invalid request", 400

        # Clean phone number for session key
        phone_key = from_number.replace('whatsapp:', '')
        logger.info(f"=== New Message ===")
        logger.info(f"From: {phone_key}")
        logger.info(f"Message: {incoming_msg}")

        # CHECK FOR RESET COMMANDS FIRST (before any other processing)
        if handle_reset_commands(phone_key, incoming_msg):
            msg.body(MAIN_MENU)
            return str(resp)

        # Ensure we don't process further if it was a reset command
        current_state = bot.get_user_state(phone_key)
        if current_state == bot.states['START'] and incoming_msg.lower().strip() not in ['reset', 'restart',
                                                                                         'start over', 'menu', 'help',
                                                                                         'hi', 'hello', 'start']:
            # Only show main menu for actual START state, not after reset
            pass

        # Debug session before processing
        debug_session_state(phone_key, "BEFORE_PROCESSING")

        # Ensure session is properly initialized
        if phone_key not in session:
            logger.info("Initializing new session")
            session[phone_key] = {
                'state': bot.states['START'],
                'data': {}
            }
            session.modified = True

        # Get current state with debug logging
        current_state = bot.get_user_state(phone_key)
        logger.info(f"Current state: {current_state}")

        # Debug user data before processing
        debug_user_data(phone_key, "BEFORE_PROCESSING")

        # Handle different states
        try:
            if current_state == bot.states['START']:
                logger.info("Processing START state")
                msg.body(MAIN_MENU)
                bot.set_user_state(phone_key, bot.states['MAIN_MENU'])

            elif current_state == bot.states['MAIN_MENU']:
                logger.info("Processing MAIN_MENU state")
                response_text = handle_main_menu(phone_key, incoming_msg)
                msg.body(response_text)

            elif current_state == bot.states['RACE_SELECTION']:
                logger.info("Processing RACE_SELECTION state")
                response_text = handle_race_selection(phone_key, incoming_msg)
                msg.body(response_text)

            elif current_state == bot.states['REGISTRATION_FORM']:
                logger.info("Processing REGISTRATION_FORM state")
                debug_user_data(phone_key, "BEFORE_REGISTRATION")
                response_text = handle_registration_form(phone_key, incoming_msg)
                debug_user_data(phone_key, "AFTER_REGISTRATION")
                msg.body(response_text)

            elif current_state == bot.states['PAYMENT']:
                logger.info("Processing PAYMENT state")
                debug_user_data(phone_key, "BEFORE_PAYMENT")
                response_text = handle_payment(phone_key, incoming_msg)
                debug_user_data(phone_key, "AFTER_PAYMENT")
                msg.body(response_text)

            elif current_state == bot.states['TICKET_CHECK']:
                logger.info("Processing TICKET_CHECK state")
                response_text = handle_ticket_check(phone_key, incoming_msg)
                msg.body(response_text)

            elif current_state == bot.states['COMPLETED']:
                logger.info("Processing COMPLETED state")
                msg.body("Your previous session has been completed. Starting a new one!\n\n" + MAIN_MENU)
                bot.set_user_state(phone_key, bot.states['MAIN_MENU'])

            else:
                logger.warning(f"Unknown state: {current_state}, resetting to MAIN_MENU")
                msg.body("Something went wrong. Let's start over.\n\n" + MAIN_MENU)
                bot.set_user_state(phone_key, bot.states['MAIN_MENU'])

        except Exception as e:
            logger.error(f"Error processing state {current_state}: {str(e)}", exc_info=True)
            # Debug data when error occurs
            debug_user_data(phone_key, "ERROR_STATE")
            debug_session_state(phone_key, "ERROR_STATE")
            msg.body("Sorry, something went wrong. Let's start over.\n\n" + MAIN_MENU)
            bot.set_user_state(phone_key, bot.states['MAIN_MENU'])

        # Debug session after processing
        debug_session_state(phone_key, "AFTER_PROCESSING")
        debug_user_data(phone_key, "AFTER_PROCESSING")

        # Final session state
        logger.info(f"Final state: {bot.get_user_state(phone_key)}")

        # Force session save
        session.modified = True

        return str(resp)

    except Exception as e:
        logger.error(f"Critical error in webhook: {str(e)}", exc_info=True)
        resp = MessagingResponse()
        resp.message("Sorry, something went wrong. Please try again.\n\n" + MAIN_MENU)
        return str(resp)


def handle_main_menu(phone_key, message):
    """Handle main menu selection"""
    message = message.strip()
    logger.info(f"Handling main menu selection: {message}")

    if message == "1":
        logger.info("User selected: Register for Heroes Marathon")
        bot.set_user_state(phone_key, bot.states['RACE_SELECTION'])
        # Clear any previous race selection
        bot.set_user_data(phone_key, 'event_type', 'heroes_marathon')
        logger.info(f"State set to RACE_SELECTION for {phone_key}")
        return RACE_SELECTION

    elif message == "2":
        logger.info("User selected: Check Registration Status")
        bot.set_user_state(phone_key, bot.states['TICKET_CHECK'])
        bot.set_user_data(phone_key, 'check_type', 'heroes_status')
        logger.info(f"State set to TICKET_CHECK for {phone_key}")
        return "Please enter your ticket number to check your registration status:"

    else:
        logger.warning(f"Invalid menu option selected: {message}")
        return "❌ Invalid option. Please select 1 or 2:\n\n" + MAIN_MENU


def handle_race_selection(phone_key, message):
    """Handle race distance selection with number options"""
    try:
        # Clean the input
        selection = message.strip()
        logger.info(f"Handling race selection: {selection}")

        # Map of number options to race details
        race_options = {
            '1': {'distance': '5KM', 'price': 20, 'display': '5KM ($20)'},
            '2': {'distance': '10KM', 'price': 20, 'display': '10KM ($20)'},
            '3': {'distance': '21KM', 'price': 20, 'display': '21KM ($20)'}
        }

        if selection in race_options:
            selected_race = race_options[selection]
            logger.info(f"Race selected: {selected_race}")

            # Store race selection in user data
            bot.set_user_data(phone_key, 'race_distance', selected_race['distance'])
            bot.set_user_data(phone_key, 'race_price', selected_race['price'])

            # Move to registration form state
            bot.set_user_state(phone_key, bot.states['REGISTRATION_FORM'])
            logger.info(f"State set to REGISTRATION_FORM for {phone_key}")

            return (
                f"You've selected: {selected_race['display']}\n\n"
                f"{REGISTRATION_FORM}"
            )
        else:
            # Show error with available options
            options_text = '\n'.join([f"{num}. {race['display']}" for num, race in race_options.items()])
            logger.warning(f"Invalid race selection: {selection}")
            return (
                "❌ Invalid selection.\n\n"
                "Please select a race distance by number:\n"
                f"{options_text}\n\n"
                "Reply with 1, 2, or 3."
            )
    except Exception as e:
        logger.error(f"Error in handle_race_selection: {str(e)}", exc_info=True)
        return (
            "❌ An error occurred while processing your selection.\n\n"
            "Please try again or contact support if the issue persists.\n\n"
            "Here are the available options:\n"
            "1. 5KM ($20)\n"
            "2. 10KM ($20)\n"
            "3. 21KM ($20)\n\n"
            "Reply with 1, 2, or 3."
        )


def handle_registration_form(phone_key, message):
    """Handle registration form submission"""
    try:
        # Parse the form data
        lines = message.strip().split('\n')
        form_data = {}

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                # Normalize field names - handle both "T-Shirt Size" and "T Shirt Size"
                normalized_key = key.strip().lower().replace(' ', '_').replace('-', '_')
                form_data[normalized_key] = value.strip()

        # Debug: Print parsed form data
        logger.info(f"Parsed form data: {form_data}")

        # Validate required fields with normalized names
        required_fields = ['full_name', 'email', 'phone_number', 'national_id_number',
                           'gender', 'date_of_birth', 't_shirt_size']

        missing_fields = []
        for field in required_fields:
            if field not in form_data or not form_data[field]:
                missing_fields.append(field.replace('_', ' ').title())

        if missing_fields:
            logger.warning(f"Missing fields: {missing_fields}")
            logger.warning(f"Available fields: {list(form_data.keys())}")
            return f"Missing required fields: {', '.join(missing_fields)}\n\nPlease fill the form again:\n\n{REGISTRATION_FORM}"

        # Additional validation
        # Validate email format
        email = form_data.get('email', '')
        if '@' not in email:
            return "Please enter a valid email address.\n\nPlease fill the form again:\n\n{REGISTRATION_FORM}"

        # Validate phone number
        phone = form_data.get('phone_number', '')
        if not phone.replace('+', '').replace(' ', '').isdigit():
            return "Please enter a valid phone number.\n\nPlease fill the form again:\n\n{REGISTRATION_FORM}"

        # Validate gender
        gender = form_data.get('gender', '').lower()
        if gender not in ['male', 'female', 'm', 'f']:
            return "Please enter a valid gender (Male/Female).\n\nPlease fill the form again:\n\n{REGISTRATION_FORM}"

        # Validate T-shirt size
        tshirt_size = form_data.get('t_shirt_size', '').upper()
        valid_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
        if tshirt_size not in valid_sizes:
            return f"Please enter a valid T-shirt size ({'/'.join(valid_sizes)}).\n\nPlease fill the form again:\n\n{REGISTRATION_FORM}"

        # Store form data
        user_data = bot.get_user_data(phone_key)
        user_data.update(form_data)

        # Generate ticket number
        ticket_number = f"T{str(uuid.uuid4().int)[:6]}"
        bot.set_user_data(phone_key, 'ticket_number', ticket_number)

        # Mock registration API call
        registration_result = mock_register_participant(user_data)

        if registration_result['success']:
            bot.set_user_state(phone_key, bot.states['PAYMENT'])
            race_distance = user_data.get('race_distance', 'N/A')
            race_price = user_data.get('race_price', 20)

            return (
                f"✅ Registration Successful!\n\n"
                f"📝 Registration Details:\n"
                f"• Name: {form_data.get('full_name')}\n"
                f"• Race: {race_distance}\n"
                f"• Price: ${race_price}\n"
                f"• Ticket: {ticket_number}\n\n"
                f"💰 Payment Required:\n"
                f"Please enter your EcoCash phone number to complete payment:"
            )
        else:
            return "❌ Registration failed. Please try again or contact support."

    except Exception as e:
        logger.error(f"Error processing form: {str(e)}", exc_info=True)
        return f"❌ Error processing form. Please make sure you follow the exact format:\n\n{REGISTRATION_FORM}"


def handle_payment(phone_key, message):
    """Handle payment process with escape options"""
    message_lower = message.lower().strip()

    # Check for escape commands
    escape_commands = ['back', 'cancel', 'menu', 'skip', 'later']
    if message_lower in escape_commands:
        bot.set_user_state(phone_key, bot.states['MAIN_MENU'])
        return "Payment cancelled. Returning to main menu.\n\n" + MAIN_MENU

    phone_number = message.strip()

    # Validate phone number format
    if not phone_number or not phone_number.replace('+', '').replace(' ', '').replace('263', '').replace('0',
                                                                                                         '').isdigit():
        return (
            "Please enter a valid phone number for EcoCash payment.\n"
            "Example: 0771234567 or 263771234567\n\n"
            "Or type 'menu' to return to the main menu."
        )

    user_data = bot.get_user_data(phone_key)
    user_data['payment_phone'] = phone_number

    # Use the improved payment function with polling
    payment_result = initiate_payment_with_polling(user_data, phone_key)

    if payment_result.get('success'):
        ticket_number = user_data.get('ticket_number')
        # Store successful registration
        mock_tickets[ticket_number] = {
            'status': 'pending_payment',
            'user_data': user_data,
            'payment_status': 'pending',
            'transaction_id': payment_result.get('transaction_id'),
            'poll_url': payment_result.get('poll_url'),
            'registration_date': datetime.now().isoformat()
        }

        bot.set_user_state(phone_key, bot.states['COMPLETED'])
        return (
            "🚀 Payment Request Sent! 🚀\n\n"
            f"• Check your EcoCash menu (*482#) to complete payment\n"
            f"• Ticket Number: {ticket_number}\n"
            f"• Amount: ${user_data.get('race_price', 20)}\n\n"
            "You'll receive an automatic notification once payment is confirmed. "
            "You can also check your registration status anytime by sending 'menu' and selecting option 2."
        )
    else:
        # Store failed payment attempt
        ticket_number = user_data.get('ticket_number')
        if ticket_number:
            mock_tickets[ticket_number] = {
                'status': 'payment_failed',
                'user_data': user_data,
                'payment_status': 'failed',
                'error_message': payment_result.get('message', 'Unknown error'),
                'registration_date': datetime.now().isoformat()
            }

        return (
            "❌ Payment Failed ❌\n\n"
            f"Error: {payment_result.get('message', 'Unknown error')}\n\n"
            f"Your ticket number is: {ticket_number}\n"
            "Your registration is saved. You can complete payment later.\n\n"
            "Type 'menu' to return to the main menu or try payment again with a different number."
        )


def poll_and_notify_user(phone_key, poll_url, ticket_number):
    """Poll payment status and notify user when complete"""
    try:
        paynow = Paynow(
            PAYNOW_INTEGRATION_ID,
            PAYNOW_INTEGRATION_KEY,
            'http://example.com/return',
            'http://example.com/result'
        )

        max_attempts = 30  # Poll for 5 minutes (30 * 10 seconds)
        attempt = 0

        while attempt < max_attempts:
            try:
                status = paynow.check_transaction_status(poll_url)

                if status.paid:
                    # Payment successful
                    logger.info(f"Payment successful for ticket {ticket_number}")

                    # Update ticket status
                    if ticket_number in mock_tickets:
                        mock_tickets[ticket_number]['payment_status'] = 'paid'
                        mock_tickets[ticket_number]['status'] = 'confirmed'
                        mock_tickets[ticket_number]['transaction_id'] = status.transaction_reference

                    # Send success notification
                    send_whatsapp_notification(
                        phone_key,
                        f"✅ Payment Confirmed! ✅\n\n"
                        f"Your registration is now complete!\n"
                        f"• Ticket: {ticket_number}\n"
                        f"• Status: CONFIRMED\n"
                        f"• Transaction ID: {status.transaction_reference}\n\n"
                        f"See you at the race! 🏃‍♂️🏃‍♀️"
                    )
                    break

                elif status.failed:
                    # Payment failed
                    logger.info(f"Payment failed for ticket {ticket_number}")

                    # Update ticket status
                    if ticket_number in mock_tickets:
                        mock_tickets[ticket_number]['payment_status'] = 'failed'
                        mock_tickets[ticket_number]['status'] = 'payment_failed'

                    # Send failure notification
                    send_whatsapp_notification(
                        phone_key,
                        f"❌ Payment Failed ❌\n\n"
                        f"Your payment could not be processed.\n"
                        f"• Ticket: {ticket_number}\n"
                        f"• Status: PAYMENT FAILED\n\n"
                        f"Please try again or contact support."
                    )
                    break

                else:
                    # Payment still pending
                    logger.info(f"Payment still pending for ticket {ticket_number} (attempt {attempt + 1})")

            except Exception as e:
                logger.error(f"Error checking payment status: {str(e)}")

            attempt += 1
            time.sleep(10)  # Wait 10 seconds before next poll

        # If we exit the loop without success or failure, it timed out
        if attempt >= max_attempts:
            logger.warning(f"Payment polling timed out for ticket {ticket_number}")
            send_whatsapp_notification(
                phone_key,
                f"⏰ Payment Status Update ⏰\n\n"
                f"We're still processing your payment.\n"
                f"• Ticket: {ticket_number}\n"
                f"• Status: PROCESSING\n\n"
                f"You'll receive an update once the payment is confirmed."
            )

    except Exception as e:
        logger.error(f"Error in payment polling: {str(e)}", exc_info=True)


def send_whatsapp_notification(phone_key, message):
    """Send WhatsApp notification to user"""
    try:
        # Format phone number for Twilio
        to_number = f"whatsapp:{phone_key}"

        message = client.messages.create(
            body=message,
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            to=to_number
        )

        logger.info(f"Notification sent to {phone_key}: {message.sid}")

    except Exception as e:
        logger.error(f"Error sending WhatsApp notification: {str(e)}")

def handle_ticket_check(phone_key, message):
    """Handle ticket number verification and payment status check"""
    ticket_number = message.strip().upper()

    if ticket_number in mock_tickets:
        ticket_info = mock_tickets[ticket_number]

        # Format event name for display
        event_type = ticket_info.get('user_data', {}).get('event_type', 'Event').replace('_', ' ').title()

        # Common ticket info
        response = [
            f"🎟️ *Ticket Status* 🎟️",
            f"• Ticket: {ticket_number}",
            f"• Event: {event_type}",
            f"• Status: {ticket_info.get('status', 'unknown').replace('_', ' ').title()}",
            f"• Payment: {ticket_info.get('payment_status', 'unknown').title()}",
            f"• Date: {ticket_info.get('registration_date', 'N/A')}"
        ]

        # Add payment-specific information
        if ticket_info.get('payment_status') == 'paid':
            response.extend([
                "",
                "✅ *Payment Confirmed*",
                f"• Amount: ${ticket_info.get('user_data', {}).get('race_price', 20)}",
                f"• Transaction ID: {ticket_info.get('transaction_id', 'N/A')}"
            ])
        elif ticket_info.get('payment_status') == 'pending':
            response.extend([
                "",
                "⏳ *Payment Pending*",
                "Please check your EcoCash menu to complete the payment.",
                f"• Amount: ${ticket_info.get('user_data', {}).get('race_price', 20)}"
            ])
        elif ticket_info.get('payment_status') == 'failed':
            response.extend([
                "",
                "❌ *Payment Failed*",
                f"Error: {ticket_info.get('error_message', 'Unknown error')}",
                "Please try making the payment again."
            ])

        # Add participant info
        if 'user_data' in ticket_info:
            user = ticket_info['user_data']
            response.extend([
                "",
                "👤 *Participant Details*",
                f"• Name: {user.get('full_name', 'N/A')}",
                f"• Race: {user.get('race_distance', 'N/A')}"
            ])

        return "\n".join(response)
    else:
        return (
            "❌ *Ticket Not Found*\n\n"
            f"We couldn't find a ticket with number: {ticket_number}\n\n"
            "Please check the number and try again, or contact support if you need assistance."
        )


def mock_register_participant(user_data):
    """Mock registration API - replace with actual API call"""
    # TODO: Replace with actual registration API call
    # registration_api_url = "https://api.example.com/register"
    # response = requests.post(registration_api_url, json=user_data)
    # return response.json()

    # Mock successful registration
    return {
        'success': True,
        'ticket_number': user_data.get('ticket_number'),
        'message': 'Registration successful'
    }


def initiate_payment_with_polling(user_data, phone_key):
    """Initiate payment with background polling - based on your working version"""
    try:
        # Check if PayNow credentials are available
        if not PAYNOW_INTEGRATION_ID or not PAYNOW_INTEGRATION_KEY:
            logger.error("PayNow credentials not configured")
            return {
                'success': False,
                'message': 'Payment system not configured. Please contact support.'
            }

        # Initialize PayNow
        paynow = Paynow(
            PAYNOW_INTEGRATION_ID,
            PAYNOW_INTEGRATION_KEY,
            'http://example.com/return',
            'http://example.com/result'
        )

        # Get and validate phone number
        ecocash_number = user_data.get('payment_phone')
        if not ecocash_number:
            return {
                'success': False,
                'message': 'Payment phone number is required'
            }

        # Clean and format phone number
        ecocash_number = str(ecocash_number).strip()
        if ecocash_number.startswith('0') and len(ecocash_number) == 10:
            ecocash_number = '263' + ecocash_number[1:]
        elif ecocash_number.startswith('+263'):
            ecocash_number = ecocash_number[1:]
        elif ecocash_number.startswith('263') and len(ecocash_number) == 12:
            pass  # Already correct
        else:
            return {
                'success': False,
                'message': 'Invalid phone number format. Please use format like 0771234567'
            }

        # Create payment
        ticket_number = user_data.get('ticket_number', 'Unknown')
        email = user_data.get('email', 'race@example.com')
        amount = float(user_data.get('race_price', 0.10))

        payment = paynow.create_payment(f'Marathon Registration - {ticket_number}', email)
        payment.add('Race Registration', amount)


        # Send payment request
        response = paynow.send_mobile(payment, ecocash_number, 'ecocash')

        if response.success:
            # Get transaction reference - fix the attribute error
            transaction_ref = getattr(response, 'transaction_reference', None) or getattr(response, 'reference',
                                                                                          'Unknown')

            # Add 30-second delay before responding
            logger.info(f"Payment initiated for {phone_key}, waiting 30 seconds for confirmation...")
            time.sleep(30)

            # Check payment status after delay
            try:
                status = paynow.check_transaction_status(response.poll_url)
                if status.paid:
                    # Payment successful
                    logger.info(f"✅ Payment confirmed for ticket {ticket_number}")
                    return {
                        'success': True,
                        'transaction_id': transaction_ref,
                        'poll_url': response.poll_url,
                        'message': 'Payment confirmed successfully!'
                    }
                elif status.failed:
                    # Payment failed
                    logger.info(f"❌ Payment failed for ticket {ticket_number}")
                    return {
                        'success': False,
                        'message': 'Payment was declined or failed. Please try again.'
                    }
                else:
                    # Payment still pending - start background polling
                    threading.Thread(
                        target=poll_and_notify_user,
                        args=(phone_key, response.poll_url, ticket_number),
                        daemon=True
                    ).start()

                    logger.info(f"⏳ Payment still pending for ticket {ticket_number}, polling started")
                    return {
                        'success': True,
                        'transaction_id': transaction_ref,
                        'poll_url': response.poll_url,
                        'message': 'Payment is being processed. You will receive a notification once confirmed.'
                    }
            except Exception as e:
                logger.error(f"Error checking payment status: {str(e)}")
                # Start background polling as fallback
                threading.Thread(
                    target=poll_and_notify_user,
                    args=(phone_key, response.poll_url, ticket_number),
                    daemon=True
                ).start()

                return {
                    'success': True,
                    'transaction_id': transaction_ref,
                    'poll_url': response.poll_url,
                    'message': 'Payment request sent. You will receive a notification once confirmed.'
                }

        error_msg = str(response.error) if hasattr(response, 'error') else "Payment failed"
        logger.error(f"Payment initiation failed: {error_msg}")
        return {
            'success': False,
            'message': f'Failed to initiate payment: {error_msg}'
        }

    except Exception as e:
        logger.error(f"Exception occurred during payment initiation: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'Payment processing error: {str(e)}'
        }


def mock_check_registration_status(ticket_number):
    """Mock registration status check - replace with actual API call"""
    # TODO: Replace with actual status check API call
    # status_api_url = f"https://api.example.com/status/{ticket_number}"
    # response = requests.get(status_api_url)
    # return response.json()

    # Mock status check
    if ticket_number in mock_tickets:
        return mock_tickets[ticket_number]
    else:
        return {'found': False}


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}


if __name__ == '__main__':
    app.run(debug=True, port=5001)