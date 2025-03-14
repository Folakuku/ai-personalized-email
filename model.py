from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableBranch
from langchain_groq import ChatGroq
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

# Prompt template for generating personalized cold emails
email_template = ChatPromptTemplate.from_messages([
    ("system", "You are a marketing expert for Sigma Insurance, crafting personalized cold emails to prospects."),
    ("human", (
        "Generate a cold email for a prospect in the {industry} industry.\n"
        "Prospect details: Company Name: {company_name}, Contact Name: {contact_name}, "
        "Engagement Level: {engagement_level}.\n"
        "Tailor the email based on the industry, engagement level, and address potential objections.\n"
        "Subject: Sigma Insurance Marketing\n"
        "Include a professional greeting, a personalized value proposition, "
        "an objection handler, a call-to-action, and advice to me (the marketer) on further engagement."
    ))
])

# Define industry-specific branches
industry_branches = RunnableBranch(
    # Tech industry branch: Emphasize innovation
    (lambda x: "tech" in x["industry"].lower(),
     email_template | llm | StrOutputParser()),

    # Finance industry branch: Emphasize security & ROI
    (lambda x: "finance" in x["industry"].lower(),
     email_template | llm | StrOutputParser()),

    # Healthcare industry branch: Emphasize compliance & efficiency
    (lambda x: "healthcare" in x["industry"].lower(),
     email_template | llm | StrOutputParser()),

    # Default branch for unrecognized industries
    email_template | llm | StrOutputParser()
)

# Full chain: Directly invoke the branch logic
email_chain = industry_branches

# Example prospect data
# prospect_data = {
#     "email": "jane.smith@healthcore.com",
#     "industry": "healthcare",
#     "company_name": "HealthCore Solutions",
#     "contact_name": "Jane Smith",
#     "engagement_level": "low (no prior interaction)"
# }

# # Invoke the chain with the prospect data
# result = email_chain.invoke(prospect_data)

# # Print the generated email
# print(result)
