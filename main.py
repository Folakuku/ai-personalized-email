# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
# from pathlib import Path
from pydantic import BaseModel, EmailStr
from typing import Literal
from model import email_chain
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Sigma Insurance Email",
    description="API to generate personalized cold emails for insurance prospects",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic model for prospect data
class ProspectData(BaseModel):
    email: EmailStr  # Validates that it's a proper email address
    # Restricts to specific values
    industry: Literal["tech", "finance", "healthcare"]
    company_name: str
    contact_name: str
    engagement_level: str

    class Config:
        # Example data for API docs
        json_schema = {
            "example": {
                "email": "jane.smith@healthcore.com",
                "industry": "healthcare",
                "company_name": "HealthCore Solutions",
                "contact_name": "Jane Smith",
                "engagement_level": "low (no prior interaction)"
            }
        }


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse("Welcome")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Accepts email, industry, company_name, contact_name, and engagement_level
@app.post("/emails")
# async def send_emails(request: Request, body: ProspectData):
async def send_emails(body: ProspectData):
    try:
        prospect_data = body.model_dump()
        {
            "email": "jane.smith@healthcore.com",
            "industry": "healthcare",
            "company_name": "HealthCore Solutions",
            "contact_name": "Jane Smith",
            "engagement_level": "low (no prior interaction)"
        }

        # Invoke the chain with the prospect data
        result = email_chain.invoke(prospect_data)

        return {"status": True, "body": body, "data": result}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error sending emails: {str(e)}")

# Accepts email, industry, company_name, contact_name, and engagement_level


@app.post("/api/applications")
# async def send_emails(request: Request, body: ProspectData):
async def send_emails(body: ProspectData):
    try:
        print(body)
        prospect_data = body.model_dump()
        {
            "email": "jane.smith@healthcore.com",
            "industry": "healthcare",
            "company_name": "HealthCore Solutions",
            "contact_name": "Jane Smith",
            "engagement_level": "low (no prior interaction)"
        }

        # Invoke the chain with the prospect data
        result = email_chain.invoke(prospect_data)

        return {"status": True, "body": body, "data": result}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error sending emails: {str(e)}")
