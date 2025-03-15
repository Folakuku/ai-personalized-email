from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal
import os
from typing import Optional, List
import logging
from bson.objectid import ObjectId
from contextlib import asynccontextmanager
from datetime import datetime
from mailer import send_email
from model import email_chain
from schemas import DetailRequest, DetailsRequest, CallScriptRequest, MakeCallRequest
from db import ProspectModel, EmailHistoryModel, mongo_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("Application startup complete")

    yield

    # Shutdown code
    mongo_client.close()
    logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

llm = ChatGroq(model="llama3-8b-8192", temperature=0.5,
               max_tokens=None, timeout=None, max_retries=2)


def get_prospect(email: str) -> Optional[dict]:
    try:
        prospect = ProspectModel.find_one({"email": email})
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
            ProspectModel.update_one(
                {"email": email},
                {"$set": update_data}
            )
        else:
            # Create new prospect
            prospect_data["interaction_count"] = 0
            prospect_data["call_count"] = 0 if not call_outcome else 1
            ProspectModel.insert_one(prospect_data)
    except Exception as e:
        logger.error(f"Error saving/updating prospect: {str(e)}")
        raise


def determine_engagement_level(interaction_count: int) -> str:
    if interaction_count >= 4:
        return "High"
    elif interaction_count >= 2:
        return "Medium"
    return "Low"


def get_all_prospects():
    try:
        prospects = list(ProspectModel.find(
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
async def send_single_email(request: DetailRequest):
    try:
        prospect = request.prospect
        company_info = request.company_info
        representative = request.representative

        email = prospect.email.strip()
        industry = prospect.industry
        company_name = prospect.company_name
        contact_name = prospect.contact_name
        engagement_level = prospect.engagement_level
        phone_number = prospect.phone_number

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

        # Save email history
        EmailHistoryModel.insert_one({
            "prospect_email": email,
            "subject": subject,
            "body": email_body,
            "sent_at": datetime.now()
        })

        # Update interaction count
        ProspectModel.update_one(
            {"email": email},
            {"$inc": {"interaction_count": 1}}
        )

        return {"status": True, "email_sent_to": email, "body": email_body, "engagement_level": engagement_level_used}

    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/details")
async def send_emails(request: DetailsRequest):
    try:
        prospects = request.prospects
        company_info = request.company_info
        representative = request.representative

        emails_sent_to = []
        email_bodies = []

        for prospect in prospects:
            email = prospect.email.strip()
            industry = prospect.industry
            company_name = prospect.company_name
            contact_name = prospect.contact_name
            engagement_level = prospect.engagement_level
            phone_number = prospect.phone_number

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
            EmailHistoryModel.insert_one({
                "prospect_email": email,
                "subject": subject,
                "body": email_body,
                "sent_at": datetime.now()
            })

            # Update interaction count
            ProspectModel.update_one(
                {"email": email},
                {"$inc": {"interaction_count": 1}}
            )

        return {"status": True, "emails_sent_to": emails_sent_to, "bodies": email_bodies, "engagement_level": engagement_level_used}
    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
