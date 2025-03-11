# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
# from pathlib import Path
# from app import dynamic_memory_app
# from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse("Welcome")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Accepts email, industry, company_name, contact_name, and engagement_level
@app.post("/details")
async def send_emails(request: Request, body: str):

    return {"status": True, "body": body}
