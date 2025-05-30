from paynow import Paynow
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Create Paynow instance
paynow = Paynow(
    integration_id=os.getenv("PAYNOW_ID"),
    integration_key=os.getenv("PAYNOW_KEY"),
    return_url='http://localhost:5000/return',
    result_url='http://localhost:5000/result'
)

def process_payment(email, product_name, amount, phone_number, payment_method):
    """
    Process a mobile payment using Paynow API.
    payment_method: 'ecocash', 'onemoney', or 'innbucks'
    """
    try:
        payment = paynow.create_payment('WhatsApp Order', email)
        payment.add(product_name, amount)

        response = paynow.send_mobile(payment, phone_number, payment_method)

        if response.success:
            return {
                'success': True,
                'message': f"Payment request sent to {phone_number} via {payment_method}.",
                'poll_url': response.poll_url
            }
        else:
            return {
                'success': False,
                'message': f"Payment failed: {response.error}"
            }
    except Exception as e:
        return {
            'success': False,
            'message': f"An error occurred while processing payment: {str(e)}"
        }
