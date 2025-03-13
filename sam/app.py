from langchain_google_community import GmailToolkit
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
import os
from dotenv import load_dotenv

load_dotenv()

toolkit = GmailToolkit()

tools = toolkit.get_tools()
tools



# Find the send message tool
send_message_tool = next(tool for tool in tools if tool.name == "send_gmail_message")

# Define email details
email_data = {
    "to": ["nwasamobi@gmail.com"],  # Replace with actual recipient email(s)
    "subject": "Test Email from LangChain",
    "message": "Hello, this is a test email using LangChain's Gmail integration!",
#     "cc": ["cc@example.com"],  # Optional
#     "bcc": ["bcc@example.com"],  # Optional
 }

# Send the email
response = send_message_tool.run(email_data)

# Print response
print(response)

# # Initialize GROQ LLM
# llm = ChatGroq(
#     api_key=os.getenv("GROQ_API_KEY"),
#     model="llama3-8b-8192",  # Model can be changed depending on your needs
#     temperature=0.2,
#     max_tokens=None
# )

# agent_executor = create_react_agent(llm, tools)
# example_query = "Draft an email to Samuel, his email is nwasamobi@gmail.com thanking them for coffee."

# events = agent_executor.stream(
#     {"messages": [("user", example_query)]},
#     stream_mode="values",
# )
# for event in events:
#     event["messages"][-1].pretty_print()

from langchain_google_community import GmailToolkit
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
import os
from dotenv import load_dotenv

load_dotenv()

toolkit = GmailToolkit()

tools = toolkit.get_tools()

# Find the send message tool
send_message_tool = next(tool for tool in tools if tool.name == "send_gmail_message")

# Function to send an email
def send_email(to: list, subject: str, message: str):
    """
    Sends an email using Gmail integration.
    
    Parameters:
    - to (list): List of recipient email addresses.
    - subject (str): The subject line of the email.
    - message (str): The body content of the email.
    
    Returns:
    - Response from the Gmail API.
    """
    email_data = {
        "to": to,  # Recipient email(s)
        "subject": subject,  # Email subject
        "message": message,  # Email body
    }
    return send_message_tool.run(email_data)

# Initialize LLM
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama3-8b-8192",
    temperature=0.2,
    max_tokens=None
)

agent_executor = create_react_agent(llm, tools)

# Example input query for LLM
example_query = "Send an email to Tom, tom@automaly.io, telling him he is a good coach, the email should sound friendly"

events = agent_executor.stream(
    {"messages": [("user", example_query)]},
    stream_mode="values",
)

for event in events:
    event["messages"][-1].pretty_print()
