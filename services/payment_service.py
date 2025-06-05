# services/payment_service.py
from paynow import Paynow
from datetime import datetime, timedelta
import time
import threading
from services.redis_utils import RedisService
from services.twilio_messaging import send_whatsapp_message
import logging

class PaymentService:

    def __init__(self):
        self.redis_service = RedisService()
        self.paynow = Paynow(
            '20700',
            '3741f3f9-dcdb-4424-9f14-049b740fe7c6',
            'https://sefai-695944432692.europe-west1.run.app/return-url',
            'https://sefai-695944432692.europe-west1.run.app/result-url'
        )

    def validate_ecocash_number(self, number: str) -> bool:
        return (number.isdigit() and len(number) == 10
                and number.startswith(('077', '078', '071')))

    def poll_and_notify_user(self, sender_number: str, poll_url: str):
        for _ in range(12):  # 2 minutes max (12 x 10 sec)
            status = self.paynow.check_transaction_status(poll_url)

            if status.paid:
                message = "✅ *Payment successful!* Thank you for your purchase. You now have full access for 30 days."
                session = self.redis_service.get_user_session(sender_number) or {}
                session['payment_expiry'] = str((datetime.now() + timedelta(days=30)).timestamp())
                self.redis_service.save_user_session(sender_number, session)
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

    def handle_payment_flow(self, sender_number: str, sender_name: str, user_message: str) -> dict:
        session = self.redis_service.get_user_session(sender_number) or {}
        step = session.get("payment_step")

        if step == "awaiting_number":
            return self._handle_awaiting_number(sender_number, user_message, session)
        elif step == "awaiting_confirmation":
            return self._handle_awaiting_confirmation(sender_number, user_message, session)
        else:
            return self._start_payment_flow(sender_number, user_message, session)

    def _handle_awaiting_number(self, sender_number: str, user_message: str, session: dict) -> dict:
        if self.validate_ecocash_number(user_message):
            session.update({
                "payment_phone": user_message,
                "payment_step": "awaiting_confirmation"
            })
            self.redis_service.save_user_session(sender_number, session)

            send_whatsapp_message(sender_number,
                                  f"📱 Confirm payment info:\nEcoCash Number: {user_message}\n"
                                  "Amount: USD 0.10\n\nReply *yes* to confirm or *no* to restart.")
            return {"status": "awaiting_confirmation"}

        send_whatsapp_message(sender_number,
                              "❌ Invalid number. Enter a valid Zimbabwean EcoCash number (e.g., 0771234567):")
        return {"status": "invalid_number"}

    def initiate_payment(self, sender_number: str, ecocash_number: str, amount: float = 0.10) -> dict:
        try:
            payment = self.paynow.create_payment('WhatsApp Subscription', f'josephmutswe@gmail.com')
            payment.add('1 Month Access', amount)

            response = self.paynow.send_mobile(payment, ecocash_number, 'ecocash')

            if response.success:
                threading.Thread(
                    target=self.poll_and_notify_user,
                    args=(sender_number, response.poll_url)
                ).start()
                return {"status": "success", "poll_url": response.poll_url}

            error_msg = str(response.error) if hasattr(response, 'error') else "Payment failed"
            logging.error(f"Payment initiation failed: {error_msg}")
            return {"status": "failed", "error": error_msg}
        except Exception as e:
            logging.exception("Exception occurred during payment initiation")
            return {"status": "failed", "error": str(e)}

    def _handle_awaiting_confirmation(self, sender_number: str, user_message: str, session: dict) -> dict:
        if user_message.lower() == 'yes':
            payment_result = self.initiate_payment(
                sender_number,
                session["payment_phone"]
            )

            if payment_result["status"] == "success":
                send_whatsapp_message(sender_number,
                                      f"✅ Payment request sent to {session['payment_phone']} "
                                      "via EcoCash.\nPlease complete the payment on your phone.")

                session.pop("payment_step", None)
                session.pop("payment_phone", None)
                self.redis_service.save_user_session(sender_number, session)
                return {"status": "payment_initiated"}

            send_whatsapp_message(sender_number,
                                  f"❌ Failed to initiate payment: {payment_result['error']}\n"
                                  "Please try again or contact support.")
            return {"status": "payment_failed"}

        elif user_message.lower() == 'no':
            session["payment_step"] = "awaiting_number"
            self.redis_service.save_user_session(sender_number, session)
            send_whatsapp_message(sender_number,
                                  "🔁 Let's try again. Please enter your EcoCash number (e.g., 0771234567):")
            return {"status": "restarted_payment"}

        send_whatsapp_message(sender_number,
                              "Please reply *yes* to confirm or *no* to restart.")
        return {"status": "invalid_confirmation"}

    def _start_payment_flow(self, sender_number: str, user_message: str, session: dict) -> dict:
        session.update({
            "payment_step": "awaiting_number",
            "pending_question": user_message
        })
        self.redis_service.save_user_session(sender_number, session)

        send_whatsapp_message(sender_number,
                              "👋 Welcome to our payment system!\nNote: We currently support only *EcoCash* payments.\n\n"
                              "Please enter your EcoCash number (e.g., 0771234567):")
        return {"status": "awaiting_number"}