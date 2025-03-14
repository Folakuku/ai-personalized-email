from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch, RunnablePassthrough
from langchain_groq import ChatGroq
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from pydantic import BaseModel, EmailStr
from typing import Literal
import os
from pymongo import MongoClient
from typing import Optional
import logging
from bson.objectid import ObjectId
from contextlib import asynccontextmanager
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "prospects_db"
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
prospects_collection = db["prospects"]
email_history_collection = db["email_history"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    init_db()
    logger.info("Application startup complete")

    yield

    # Shutdown code
    client.close()
    logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

llm = ChatGroq(model="llama3-8b-8192", temperature=0.5,
               max_tokens=None, timeout=None, max_retries=2)
sendgrid_client = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"),
                       os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")


def init_db():
    # MongoDB doesn't require explicit table creation, but we can ensure indexes
    prospects_collection.create_index("email", unique=True)
    email_history_collection.create_index("prospect_email")


def get_prospect(email: str) -> Optional[dict]:
    try:
        prospect = prospects_collection.find_one({"email": email})
        if prospect:
            prospect["id"] = str(prospect["_id"])
            del prospect["_id"]
            # Set default values if fields are missing
            defaults = {
                "engagement_level": "Low",
                "interaction_count": 0,
                "call_count": 0
            }
            for key, value in defaults.items():
                prospect[key] = prospect.get(key, value)
            return prospect
        return None
    except Exception as e:
        logger.error(f"Error getting prospect: {str(e)}")
        return None


def save_or_update_prospect(email: str, industry: str, company_name: str, contact_name: str,
                            engagement_level: str = "Low", phone_number: str = None,
                            call_outcome: str = None):
    try:
        existing = get_prospect(email)
        prospect_data = {
            "email": email,
            "industry": industry,
            "company_name": company_name,
            "contact_name": contact_name,
            "engagement_level": engagement_level,
            "phone_number": phone_number,
            "last_call_outcome": call_outcome
        }

        if existing:
            # Update existing prospect
            update_data = {k: v for k, v in prospect_data.items()
                           if v is not None}
            if call_outcome:
                update_data["call_count"] = existing.get("call_count", 0) + 1
            prospects_collection.update_one(
                {"email": email},
                {"$set": update_data}
            )
        else:
            # Create new prospect
            prospect_data["interaction_count"] = 0
            prospect_data["call_count"] = 0 if not call_outcome else 1
            prospects_collection.insert_one(prospect_data)
    except Exception as e:
        logger.error(f"Error saving/updating prospect: {str(e)}")
        raise


def determine_engagement_level(interaction_count: int) -> str:
    if interaction_count >= 4:
        return "High"
    elif interaction_count >= 2:
        return "Medium"
    return "Low"


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


classification_template = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant for an insurance company classifying industries."),
    ("human",
     "Classify this industry into 'technology', 'finance', or 'health': {industry}. If it doesn't fit, default to 'technology'.")
])

tech_template = ChatPromptTemplate.from_messages([
    ("system", "You are an insurance agent crafting emails for tech prospects."),
    ("human", """Generate a friendly email body for {contact_name} at {company_name}. 
    Emphasize innovation and risk management. Tailor based on engagement level: {engagement_level} 
    (Low: introduce, Medium: follow-up, High: deepen connection). 
    Recommend: Low - 'Tech Starter Plan' ($500/year), Medium - 'Tech Growth Plan' ($1,200/year), High - 'Tech Enterprise Plan' ($3,000/year).
    Include company info: {company_info} and representative: {representative}. Subject: {subject}""")
])

finance_template = ChatPromptTemplate.from_messages([
    ("system", "You are an insurance agent crafting emails for finance prospects."),
    ("human", """Generate a friendly email body for {contact_name} at {company_name}. 
    Emphasize security and ROI. Tailor based on engagement level: {engagement_level} 
    (Low: introduce, Medium: follow-up, High: deepen connection). 
    Recommend: Low - 'Finance Essentials Plan' ($600/year), Medium - 'Finance Secure Plan' ($1,500/year), High - 'Finance Elite Plan' ($4,000/year).
    Include company info: {company_info} and representative: {representative}. Subject: {subject}""")
])

health_template = ChatPromptTemplate.from_messages([
    ("system", "You are an insurance agent crafting emails for healthcare prospects."),
    ("human", """Generate a friendly email body for {contact_name} at {company_name}. 
    Emphasize compliance and efficiency. Tailor based on engagement level: {engagement_level} 
    (Low: introduce, Medium: follow-up, High: deepen connection). 
    Recommend: Low - 'Health Basic Plan' ($550/year), Medium - 'Health Pro Plan' ($1,300/year), High - 'Health Premium Plan' ($3,500/year).
    Include company info: {company_info} and representative: {representative}. Subject: {subject}""")
])

tech_call_template = ChatPromptTemplate.from_messages([
    ("system", "You are an insurance agent crafting cold call scripts for tech prospects."),
    ("human", """Generate a concise cold call script for {contact_name} at {company_name}. 
    Emphasize innovation and risk management. Tailor based on engagement level: {engagement_level} 
    (Low: introduce, Medium: follow-up, High: deepen connection). 
    Recommend: Low - 'Tech Starter Plan' ($500/year), Medium - 'Tech Growth Plan' ($1,200/year), High - 'Tech Enterprise Plan' ($3,000/year).
    Include representative: {representative}.""")
])

finance_call_template = ChatPromptTemplate.from_messages([
    ("system", "You are an insurance agent crafting cold call scripts for finance prospects."),
    ("human", """Generate a concise cold call script for {contact_name} at {company_name}. 
    Emphasize security and ROI. Tailor based on engagement level: {engagement_level} 
    (Low: introduce, Medium: follow-up, High: deepen connection). 
    Recommend: Low - 'Finance Essentials Plan' ($600/year), Medium - 'Finance Secure Plan' ($1,500/year), High - 'Finance Elite Plan' ($4,000/year).
    Include representative: {representative}.""")
])

health_call_template = ChatPromptTemplate.from_messages([
    ("system", "You are an insurance agent crafting cold call scripts for healthcare prospects."),
    ("human", """Generate a concise cold call script for {contact_name} at {company_name}. 
    Emphasize compliance and efficiency. Tailor based on engagement level: {engagement_level} 
    (Low: introduce, Medium: follow-up, High: deepen connection). 
    Recommend: Low - 'Health Basic Plan' ($550/year), Medium - 'Health Pro Plan' ($1,300/year), High - 'Health Premium Plan' ($3,500/year).
    Include representative: {representative}.""")
])

classification_chain = classification_template | llm | StrOutputParser()
branches = RunnableBranch(
    (lambda x: "technology" in classification_chain.invoke(
        {"industry": x["industry"]}).lower(), tech_template | llm | StrOutputParser()),
    (lambda x: "finance" in classification_chain.invoke(
        {"industry": x["industry"]}).lower(), finance_template | llm | StrOutputParser()),
    (lambda x: "health" in classification_chain.invoke(
        {"industry": x["industry"]}).lower(), health_template | llm | StrOutputParser()),
    tech_template | llm | StrOutputParser()
)
email_chain = RunnablePassthrough() | branches

call_classification_chain = classification_template | llm | StrOutputParser()
call_branches = RunnableBranch(
    (lambda x: "technology" in call_classification_chain.invoke(
        {"industry": x["industry"]}).lower(), tech_call_template | llm | StrOutputParser()),
    (lambda x: "finance" in call_classification_chain.invoke(
        {"industry": x["industry"]}).lower(), finance_call_template | llm | StrOutputParser()),
    (lambda x: "health" in call_classification_chain.invoke(
        {"industry": x["industry"]}).lower(), health_call_template | llm | StrOutputParser()),
    tech_call_template | llm | StrOutputParser()
)
call_chain = RunnablePassthrough() | call_branches


def get_all_prospects():
    try:
        prospects = list(prospects_collection.find(
            {},
            {"email": 1, "company_name": 1, "contact_name": 1,
                "phone_number": 1, "_id": 0}
        ))
        logger.info(f"Fetched {len(prospects)} prospects from database")
        return prospects
    except Exception as e:
        logger.error(f"Error fetching all prospects: {str(e)}")
        return []


@app.get("/get-prospects")
async def get_prospects():
    try:
        prospects = get_all_prospects()
        logger.info(f"Returning {len(prospects)} prospects to client")
        return JSONResponse(content={"prospects": prospects}, status_code=200)
    except Exception as e:
        logger.error(f"Error fetching prospects: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/plans")
def get_insurance_plans():
    plans = {
        "Technology": {
            "Low": {"name": "Tech Starter Plan", "cost": "$500/year", "description": "Basic cyber liability coverage"},
            "Medium": {"name": "Tech Growth Plan", "cost": "$1,200/year", "description": "Cyber + IP protection"},
            "High": {"name": "Tech Enterprise Plan", "cost": "$3,000/year", "description": "Comprehensive coverage"}
        },
        "Finance": {
            "Low": {"name": "Finance Essentials Plan", "cost": "$600/year", "description": "Fraud protection"},
            "Medium": {"name": "Finance Secure Plan", "cost": "$1,500/year", "description": "Fraud + data breach"},
            "High": {"name": "Finance Elite Plan", "cost": "$4,000/year", "description": "Full security suite"}
        },
        "Health": {
            "Low": {"name": "Health Basic Plan", "cost": "$550/year", "description": "Compliance coverage"},
            "Medium": {"name": "Health Pro Plan", "cost": "$1,300/year", "description": "Compliance + liability"},
            "High": {"name": "Health Premium Plan", "cost": "$3,500/year", "description": "Comprehensive protection"}
        }
    }
    return {"status": "success", "plans": plans}


class ProspectData(BaseModel):
    email: EmailStr  # Validates that it's a proper email address
    # Restricts to specific values
    industry: Literal["tech", "finance", "healthcare"]
    company_name: str
    contact_name: str
    engagement_level: str


@app.post("/email")
async def send_email(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        company_name = body.get("companyName")
        firstName = body.get("firstName")
        lastName = body.get("lastName")
        industry = body.get("industrySector")
        coverageAmount = body.get("coverageAmount")
        industryType = body.get("industryType")
        status = body.get("status")

        company_info = "Sigma Insurance specializes in providing customized insurance solutions for various industries."
        representative = {
            "name": firstName + " " + lastName,
            "email": email,
            "phone": "+23480754433"
        }

        emails_sent_to = []
        email_bodies = []

        # email = prospect["email"].strip()
        # industry = prospect["industry"]
        # company_name = prospect["company_name"]
        # contact_name = prospect["contact_name"]
        engagement_level = "Medium"
        phone_number = "+23480754433"

        db_prospect = get_prospect(email)
        if db_prospect:
            industry_used = industry or db_prospect["industry"]
            company_name_used = company_name or db_prospect["company_name"]
            contact_name_used = firstName or db_prospect["contact_name"]
            engagement_level_used = engagement_level if engagement_level is not None else db_prospect[
                "engagement_level"]
            phone_number_used = phone_number or db_prospect["phone_number"]
        else:
            industry_used, company_name_used, contact_name_used = industry, company_name, firstName
            engagement_level_used = engagement_level if engagement_level is not None else "Low"
            phone_number_used = phone_number

        save_or_update_prospect(email, industry_used, company_name_used,
                                contact_name_used, engagement_level_used, phone_number_used)

        subject = {
            "technology": {"Low": f"Protecting Your Innovations at {company_name_used}", "Medium": f"Next Steps for Risk Management at {company_name_used}", "High": f"Customized Insurance Solutions for {company_name_used}"},
            "finance": {"Low": f"Secure Your Financial Future with {company_name_used}", "Medium": f"Protect Your Financial Firm's Assets with {company_name_used}", "High": f"Tailored Security Solutions for {company_name_used}"},
            "health": {"Low": f"Ensure Compliance at {company_name_used}", "Medium": f"Efficiency and Compliance for {company_name_used}", "High": f"Advanced Protection for {company_name_used}"}
        }.get(industry_used.lower(), {"Low": "Sigma Insurance Marketing"})[engagement_level_used]

        email_body = email_chain.invoke({
            "industry": industry_used,
            "company_name": company_name_used,
            "contact_name": contact_name_used,
            "engagement_level": engagement_level_used,
            "company_info": company_info,
            "representative": representative,
            "subject": subject
        })

        send_email(to=[email], subject=subject, message=email_body)
        emails_sent_to.append(email)
        email_bodies.append(email_body)

        # Save email history
        email_history_collection.insert_one({
            "prospect_email": email,
            "subject": subject,
            "body": email_body,
            "sent_at": datetime.now()
        })

        # Update interaction count
        prospects_collection.update_one(
            {"email": email},
            {"$inc": {"interaction_count": 1}}
        )

        return {"status": True, "emails_sent_to": emails_sent_to, "bodies": email_bodies, "engagement_level": engagement_level_used}

    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/details")
async def send_emails(request: Request):
    try:
        body = await request.json()
        prospects = body.get("prospects")
        company_info = body.get("company_info")
        representative = body.get("representative")
        if not prospects or not company_info or not representative:
            raise HTTPException(
                status_code=400, detail="Missing required fields")

        emails_sent_to = []
        email_bodies = []

        for prospect in prospects:
            email = prospect["email"].strip()
            industry = prospect["industry"]
            company_name = prospect["company_name"]
            contact_name = prospect["contact_name"]
            engagement_level = prospect.get("engagement_level")
            phone_number = prospect.get("phone")

            if not email:
                continue

            db_prospect = get_prospect(email)
            if db_prospect:
                industry_used = industry or db_prospect["industry"]
                company_name_used = company_name or db_prospect["company_name"]
                contact_name_used = contact_name or db_prospect["contact_name"]
                engagement_level_used = engagement_level if engagement_level is not None else db_prospect[
                    "engagement_level"]
                phone_number_used = phone_number or db_prospect["phone_number"]
            else:
                industry_used, company_name_used, contact_name_used = industry, company_name, contact_name
                engagement_level_used = engagement_level if engagement_level is not None else "Low"
                phone_number_used = phone_number

            save_or_update_prospect(email, industry_used, company_name_used,
                                    contact_name_used, engagement_level_used, phone_number_used)

            subject = {
                "technology": {"Low": f"Protecting Your Innovations at {company_name_used}", "Medium": f"Next Steps for Risk Management at {company_name_used}", "High": f"Customized Insurance Solutions for {company_name_used}"},
                "finance": {"Low": f"Secure Your Financial Future with {company_name_used}", "Medium": f"Protect Your Financial Firm’s Assets with {company_name_used}", "High": f"Tailored Security Solutions for {company_name_used}"},
                "health": {"Low": f"Ensure Compliance at {company_name_used}", "Medium": f"Efficiency and Compliance for {company_name_used}", "High": f"Advanced Protection for {company_name_used}"}
            }.get(industry_used.lower(), {"Low": "Sigma Insurance Marketing"})[engagement_level_used]

            email_body = email_chain.invoke({
                "industry": industry_used,
                "company_name": company_name_used,
                "contact_name": contact_name_used,
                "engagement_level": engagement_level_used,
                "company_info": company_info,
                "representative": representative,
                "subject": subject
            })

            send_email(to=[email], subject=subject, message=email_body)
            emails_sent_to.append(email)
            email_bodies.append(email_body)

            # Save email history
            email_history_collection.insert_one({
                "prospect_email": email,
                "subject": subject,
                "body": email_body,
                "sent_at": datetime.now()
            })

            # Update interaction count
            prospects_collection.update_one(
                {"email": email},
                {"$inc": {"interaction_count": 1}}
            )

        return {"status": True, "emails_sent_to": emails_sent_to, "bodies": email_bodies, "engagement_level": engagement_level_used}
    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
