from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv
import os
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

sendgrid_client = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"),
                       os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")


def send_email(to: list, subject: str, message: str):

    if not FROM_EMAIL:
        raise ValueError("SENDGRID_FROM_EMAIL not set")
    email = Mail(from_email=FROM_EMAIL, to_emails=to,
                 subject=subject, plain_text_content=message)
    response = sendgrid_client.send(email)
    logger.info(
        f"Sending email from: {FROM_EMAIL} to: {to}, subject: {subject}")
    logger.info(f"Email sent: {response.status_code}")
    return response
