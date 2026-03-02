"""Webhook endpoints — Twilio SMS inbound, Gmail push notifications."""

from fastapi import APIRouter, Form, Request, Response
from twilio.twiml.messaging_response import MessagingResponse

from ingestion.sms_listener import handle_sms_webhook

router = APIRouter()


@router.post("/sms")
async def twilio_sms_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    NumMedia: int = Form(0),
):
    """Twilio delivers inbound SMS bids here."""
    result = await handle_sms_webhook(from_number=From, body=Body)
    # Return TwiML acknowledgement
    twiml = MessagingResponse()
    return Response(content=str(twiml), media_type="application/xml")
