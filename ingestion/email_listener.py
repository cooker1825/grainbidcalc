"""
Gmail API listener for markets@mapleviewgrain.ca.
Polls for new unread messages, processes each through the ingestion router,
then labels them as processed.

Polling interval: every 5 minutes via Celery beat.
Gmail scopes: gmail.readonly + gmail.modify
"""

# TODO: Implement Gmail API polling
# Reference: grainbot/gmail_client.py for auth patterns and label management

async def poll_email_inbox() -> dict:
    """Check for new unread bid emails and process each one."""
    raise NotImplementedError
