"""Twilio SMS outbound — sends Mapleview bid prices to farmers."""

from twilio.rest import Client
from config.settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER


def send_sms(to_number: str, message: str) -> str:
    """Send an SMS. Returns the Twilio message SID."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    msg = client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=to_number,
    )
    return msg.sid
