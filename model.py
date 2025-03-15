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
from typing import Optional
import os

# Load environment variables
load_dotenv()

# Initialize the language model
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama3-8b-8192",
    temperature=0.5,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Initialize Sendgrid
sendgrid_client = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"),
                       os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")


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


# Prompt template for generating personalized cold emails
# email_template = ChatPromptTemplate.from_messages([
#     ("system", "You are a marketing expert for Sigma Insurance, crafting personalized cold emails to prospects."),
#     ("human", (
#         "Generate a cold email for a prospect in the {industry} industry.\n"
#         "Prospect details: Company Name: {company_name}, Contact Name: {contact_name}, "
#         "Engagement Level: {engagement_level}.\n"
#         "Tailor the email based on the industry, engagement level, and address potential objections.\n"
#         "Subject: Sigma Insurance Marketing\n"
#         "Include a professional greeting, a personalized value proposition, "
#         "an objection handler, a call-to-action, and advice to me (the marketer) on further engagement."
#     ))
# ])

# # Define industry-specific branches
# industry_branches = RunnableBranch(
#     # Tech industry branch: Emphasize innovation
#     (lambda x: "tech" in x["industry"].lower(),
#      email_template | llm | StrOutputParser()),

#     # Finance industry branch: Emphasize security & ROI
#     (lambda x: "finance" in x["industry"].lower(),
#      email_template | llm | StrOutputParser()),

#     # Healthcare industry branch: Emphasize compliance & efficiency
#     (lambda x: "healthcare" in x["industry"].lower(),
#      email_template | llm | StrOutputParser()),

#     # Default branch for unrecognized industries
#     email_template | llm | StrOutputParser()
# )

# # Full chain: Directly invoke the branch logic
# email_chain = industry_branches
