from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableParallel, RunnableLambda
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

# Base prompt template for Afrobeat music expertise
base_prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in Nigerian Afrobeat music."),
])


def create_impact_prompt(highlights: str):
    """Create a prompt for analyzing the positive impact based on the highlights."""
    impact_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert in Nigerian Afrobeat music."),
        ("human", (
            "Given these highlights about Afrobeat: {highlights}\n\n"
            "List the positive impacts these highlights have had "
            "on the Nigerian music scene, cultural identity, or global influence."
        )),
    ])
    return impact_template.format_prompt(highlights=highlights)


def create_challenges_prompt(highlights: str):
    """Create a prompt for analyzing the challenges or controversies based on the highlights."""
    challenges_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert in Nigerian Afrobeat music."),
        ("human", (
            "Given these highlights about Afrobeat: {highlights}\n\n"
            "Discuss any challenges, controversies, or criticisms that might arise "
            "from these highlights—such as commercialization, cultural misappropriation, "
            "or stylistic disputes."
        )),
    ])
    return challenges_template.format_prompt(highlights=highlights)


def combine_impact_challenges(impact: str, challenges: str):
    """Combine the positive impacts and potential challenges into a final response."""
    return (
        f"### Analysis of Afrobeat Highlights\n\n"
        f"**Positive Impacts:**\n{impact}\n\n"
        f"**Challenges and Controversies:**\n{challenges}\n\n"
        f"### Conclusion\nThis combined analysis reflects the multifaceted influence "
        f"of Afrobeat on the Nigerian music scene, cultural identity, and global stage, "
        f"while also addressing potential challenges that may arise."
    )


# Example usage
highlights = (
    "List the main highlights of (music topic). "
    "Focus on historical origins, cultural influences, key artists, "
    "and anything else that stands out."
)

# Generate prompts
impact_prompt = create_impact_prompt(highlights)
challenges_prompt = create_challenges_prompt(highlights)

# Placeholder for LLM responses (to be implemented with actual LLM calls)
impact_response = llm.invoke(impact_prompt)  # Simulated response
challenges_response = llm.invoke(challenges_prompt)  # Simulated response

# Combine and print the final response
final_response = combine_impact_challenges(
    impact_response, challenges_response)
print(final_response)
