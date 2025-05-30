import json
from config.settings import twilio_client, TWILIO_PHONE_NUMBER

def send_whatsapp_message(recipient_number, message):
    max_segment_length = 1600
    segments = [message[i:i + max_segment_length] for i in range(0, len(message), max_segment_length)]

    for segment in segments:
        try:
            message = twilio_client.messages.create(
                body=segment,
                from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
                to=recipient_number
            )
            print(f"Message sent to {recipient_number}: {message.sid}")
        except Exception as e:
            print(f"Twilio send error: {e}")
            break

def send_template_message(to, name, template_sid):
    try:
        sids = template_sid if isinstance(template_sid, list) else [template_sid]
        for sid in sids:
            message = twilio_client.messages.create(
                from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
                to=to,
                content_sid=sid,
                content_variables=json.dumps({"1": name})
            )
            print(f"Template message sent to {to}: {message.sid}")
    except Exception as e:
        print(f"Template send error: {e}")
