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
import os
import sqlite3
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=[
                   "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

llm = ChatGroq(model="llama3-8b-8192", temperature=0.5,
               max_tokens=None, timeout=None, max_retries=2)
sendgrid_client = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"),
                       os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")

DB_PATH = "prospects.db"


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            email TEXT PRIMARY KEY,
            industry TEXT NOT NULL,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            engagement_level TEXT DEFAULT 'Low',
            interaction_count INTEGER DEFAULT 0,
            phone_number TEXT,
            last_call_outcome TEXT,
            call_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_email TEXT,
            subject TEXT,
            body TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_email) REFERENCES prospects (email)
        )
    """)
    conn.commit()
    conn.close()


def get_prospect(email: str, conn=None) -> Optional[dict]:
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        close_conn = True
    else:
        close_conn = False
    cursor = conn.cursor()
    cursor.execute("SELECT email, industry, company_name, contact_name, engagement_level, interaction_count, phone_number, last_call_outcome, call_count FROM prospects WHERE email = ?", (email,))
    row = cursor.fetchone()
    logger.info(f"Prospect row for {email}: {row}")
    if close_conn:
        conn.close()
    if row:
        defaults = {"email": None, "industry": None, "company_name": None, "contact_name": None,
                    "engagement_level": "Low", "interaction_count": 0, "phone_number": None,
                    "last_call_outcome": None, "call_count": 0}
        values = list(row) + [None] * (9 - len(row))
        return {"email": values[0], "industry": values[1], "company_name": values[2], "contact_name": values[3],
                "engagement_level": values[4] or defaults["engagement_level"],
                "interaction_count": values[5] or defaults["interaction_count"],
                "phone_number": values[6], "last_call_outcome": values[7], "call_count": values[8] or defaults["call_count"]}
    return None


def save_or_update_prospect(email: str, industry: str, company_name: str, contact_name: str, engagement_level: str = "Low", phone_number: str = None, call=None, call_outcome: str = None, conn=None):
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        close_conn = True
    else:
        close_conn = False
    cursor = conn.cursor()
    existing = get_prospect(email, conn=conn)
    if existing:
        cursor.execute("""
            UPDATE prospects SET industry = ?, company_name = ?, contact_name = ?, engagement_level = ?, 
            phone_number = ?, last_call_outcome = ?, call_count = call_count + (CASE WHEN ? IS NOT NULL THEN 1 ELSE 0 END)
            WHERE email = ?
        """, (industry, company_name, contact_name, engagement_level, phone_number or existing["phone_number"], call_outcome, call_outcome, email))
    else:
        cursor.execute("""
            INSERT INTO prospects (email, industry, company_name, contact_name, engagement_level, phone_number, last_call_outcome, call_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (email, industry, company_name, contact_name, engagement_level, phone_number, call_outcome))
    if not close_conn:
        conn.commit()
    if close_conn:
        conn.commit()
        conn.close()


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

init_db()


def get_all_prospects():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT email, company_name, contact_name, phone_number FROM prospects")
    rows = cursor.fetchall()
    conn.close()
    prospects = [{"email": row[0], "company_name": row[1],
                  "contact_name": row[2], "phone_number": row[3]} for row in rows]
    logger.info(f"Fetched {len(prospects)} prospects from database")
    return prospects


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
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()

        for prospect in prospects:
            email = prospect["email"].strip()
            industry = prospect["industry"]
            company_name = prospect["company_name"]
            contact_name = prospect["contact_name"]
            engagement_level = prospect.get("engagement_level")
            phone_number = prospect.get("phone")

            if not email:
                continue

            # Correctly using keyword argument
            db_prospect = get_prospect(email, conn=conn)
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
                                    contact_name_used, engagement_level_used, phone_number_used, conn=conn)

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

            cursor.execute("""
                INSERT INTO email_history (prospect_email, subject, body)
                VALUES (?, ?, ?)
            """, (email, subject, email_body))
            cursor.execute("""
                UPDATE prospects SET interaction_count = interaction_count + 1 WHERE email = ?
            """, (email,))

        conn.commit()
        conn.close()
        return {"status": True, "emails_sent_to": emails_sent_to, "bodies": email_bodies, "engagement_level": engagement_level_used}
    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call-script")
async def generate_call_script(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        industry = body.get("industry")
        company_name = body.get("company_name")
        contact_name = body.get("contact_name")
        engagement_level = body.get("engagement_level")
        representative = body.get("representative")
        phone_number = body.get("phone_number")
        call_outcome = body.get("call_outcome")

        if not all([email, industry, company_name, contact_name, representative]):
            raise HTTPException(
                status_code=400, detail="Missing required fields")

        db_prospect = get_prospect(email)
        if db_prospect:
            industry_used = industry or db_prospect["industry"]
            company_name_used = company_name or db_prospect["company_name"]
            contact_name_used = contact_name or db_prospect["contact_name"]
            engagement_level_used = engagement_level or determine_engagement_level(
                db_prospect["interaction_count"])
            phone_number_used = phone_number or db_prospect["phone_number"]
        else:
            industry_used, company_name_used, contact_name_used, engagement_level_used, phone_number_used = industry, company_name, contact_name, engagement_level or "Low", phone_number

        if call_outcome or phone_number:
            save_or_update_prospect(email, industry_used, company_name_used,
                                    contact_name_used, engagement_level_used, phone_number_used, call_outcome)

        script = call_chain.invoke({
            "industry": industry_used,
            "company_name": company_name_used,
            "contact_name": contact_name_used,
            "engagement_level": engagement_level_used,
            "representative": representative
        })

        return {
            "status": "success",
            "email": email,
            "phone_number": phone_number_used,
            "script": script,
            "last_call_outcome": call_outcome or (db_prospect and db_prospect["last_call_outcome"])
        }
    except HTTPException as e:
        raise e  # Preserve the original HTTPException
    except Exception as e:
        logger.error(f"Error generating call script: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/make-call")
async def make_call(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        phone_number = body.get("phone_number")
        representative = body.get("representative")

        if not all([email, phone_number, representative]):
            raise HTTPException(
                status_code=400, detail="Missing required fields")

        db_prospect = get_prospect(email)
        if not db_prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")

        script = call_chain.invoke({
            "industry": db_prospect["industry"],
            "company_name": db_prospect["company_name"],
            "contact_name": db_prospect["contact_name"],
            "engagement_level": db_prospect["engagement_level"],
            "representative": representative
        })

        call = twilio_client.calls.create(
            twiml=f'<Response><Say voice="Polly.Joanna">{script}</Say></Response>',
            to=phone_number,
            from_=TWILIO_PHONE
        )

        save_or_update_prospect(email, db_prospect["industry"], db_prospect["company_name"], db_prospect["contact_name"],
                                db_prospect["engagement_level"], phone_number, "Attempted")

        return {"status": "success", "call_sid": call.sid, "script": script, "phone_number": phone_number}
    except TwilioRestException as e:
        logger.error(f"Twilio error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")
    except Exception as e:
        logger.error(f"Error making call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
