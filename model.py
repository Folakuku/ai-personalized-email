from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable.passthrough import RunnableBranch
from langchain_groq import ChatGroq

load_dotenv()

# Create the LLM
llm = ChatGroq(
    model="llama3-8b-8192",
    temperature=0.5,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Invoke with email, industry, company_name, contact_name, and engagement_level
# First classify into the appropriate industry technology, finance or health
# Next create 3 branches for the three industries and generate a personalized email based on the industry and engagement level
# With in each branch the email is set as the email directly, the subject is static as "Sigma Insurance Marketing", the response from the LLM is the body/message of the email
# Invoke with email, industry, company_name, contact_name, and engagement_level


# Classification template
classification_template = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant specialized in Nigerian Afrobeat music management."),
    ("human",
     "Classify this feedback regarding the Afrobeat performance as 'positive', 'negative', 'neutral', or 'escalate': {feedback}.")
])

# BRANCHES
# Positive feedback template
positive_feedback_template = ChatPromptTemplate.from_messages([
    ("system", "You are the manager for a top-tier Nigerian Afrobeat band, eager to provide gracious responses to fans."),
    ("human",
     "Generate a thank-you note for this positive feedback about our recent Afrobeat performance: {feedback}.")
])

# Negative feedback template
negative_feedback_template = ChatPromptTemplate.from_messages([
    ("system", "You are the manager for a top-tier Nigerian Afrobeat band, striving to address concerns sincerely."),
    ("human",
     "Generate a response that acknowledges and addresses this negative feedback related to the Afrobeat show: {feedback}.")
])

# Neutral feedback template
neutral_feedback_template = ChatPromptTemplate.from_messages([
    ("system", "You are the manager for a top-tier Nigerian Afrobeat band, always seeking more context to improve fan satisfaction."),
    ("human",
     "This feedback is somewhat neutral regarding our Afrobeat music. Request more details to help us improve: {feedback}.")
])

# Escalate feedback template
escalate_feedback_template = ChatPromptTemplate.from_messages([
    ("system", "You are the manager for a top-tier Nigerian Afrobeat band, sometimes needing external support for complex situations."),
    ("human",
     "Generate a message indicating that this feedback about the Afrobeat performance is critical and needs escalation to a senior manager: {feedback}.")
])

# Create the classification chain
classification_chain = classification_template | llm | StrOutputParser()

# Define the branches based on classification
branches = RunnableBranch(
    (lambda x: "positive" in x, positive_feedback_template | llm | StrOutputParser()),
    (lambda x: "negative" in x, negative_feedback_template | llm | StrOutputParser()),
    (lambda x: "neutral" in x, neutral_feedback_template | llm | StrOutputParser()),
    escalate_feedback_template | llm | StrOutputParser()
)

# Combine the classification and branching into a single chain
chain = classification_chain | branches

# Example feedback to test the chain
review = "The last performance was rather disappointing; the band seemed off-rhythm and the audio quality was poor."

# Invoke the chain with the feedback
result = chain.invoke({"feedback": review})

# Ex
# result = chain.invoke({
#     "email": "nathanzyfola@gmail.com",
#     "industry": "kidney importation",
#     "company_name": "Nathanzy",
#     "contact_name": "Folahanmi"
# })

# Print the result
print(result)
