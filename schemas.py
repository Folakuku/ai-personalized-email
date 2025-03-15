from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Literal

# Pydantic Models for request/response validation


class Prospect(BaseModel):
    """Represents a single insurance prospect."""
    email: EmailStr = Field(...,
                            description="Prospect's email address (required)")
    industry: Literal["technology", "finance", "health"] = Field(...,
                                                                 description="Industry: e.g., technology, finance, health (required)")
    company_name: str = Field(...,
                              description="Prospect's company name (required)")
    contact_name: str = Field(...,
                              description="Contact person's name (required)")
    engagement_level: Optional[str] = Field(
        default="Low", description="Engagement level: Low, Medium, High (optional)")
    phone_number: Optional[str] = Field(
        default=None, description="Phone number in E.164 format, e.g., +2348166113016 (optional)")

    @field_validator("engagement_level")
    @classmethod
    def validate_engagement_level(cls, v):
        """Validate that engagement_level is one of Low, Medium, High."""
        valid_levels = {"Low", "Medium", "High"}
        if v and v not in valid_levels:
            raise ValueError(f"Engagement level must be one of {valid_levels}")
        return v


class DetailRequest(BaseModel):
    """Request payload for sending emails to multiple prospects."""
    prospect: Prospect = Field(...,
                               description="Prospect to email (required)")
    company_info: str = Field(
        ..., description="Company info, e.g., 'Sigma Insurance\n123 Main St' (required)")
    representative: str = Field(
        ..., description="Representative name and title, e.g., 'Fola Admin, Agent' (required)")


class DetailsRequest(BaseModel):
    """Request payload for sending emails to multiple prospects."""
    prospects: List[Prospect] = Field(...,
                                      description="List of prospects to email (required)")
    company_info: str = Field(
        ..., description="Company info, e.g., 'Sigma Insurance\n123 Main St' (required)")
    representative: str = Field(
        ..., description="Representative name and title, e.g., 'Fola Admin, Agent' (required)")


class CallScriptRequest(BaseModel):
    """Request payload for generating a call script."""
    email: EmailStr = Field(...,
                            description="Prospect's email address (required)")
    industry: Optional[str] = Field(
        default=None, description="Industry (optional, falls back to DB)")
    company_name: Optional[str] = Field(
        default=None, description="Company name (optional, falls back to DB)")
    contact_name: Optional[str] = Field(
        default=None, description="Contact name (optional, falls back to DB)")
    engagement_level: Optional[str] = Field(
        default=None, description="Engagement level: Low, Medium, High (optional, falls back to DB)")
    phone_number: Optional[str] = Field(
        default=None, description="Phone number (optional, falls back to DB)")
    representative: Optional[str] = Field(
        default=None, description="Representative (optional, falls back to DB)")
    call_outcome: Optional[str] = Field(
        default=None, description="Outcome of the call, e.g., 'Attempted' (optional)")

    @field_validator("engagement_level")
    @classmethod
    def validate_engagement_level(cls, v):
        """Validate that engagement_level is one of Low, Medium, High."""
        if v and v not in {"Low", "Medium", "High"}:
            raise ValueError("Engagement level must be Low, Medium, or High")
        return v


class MakeCallRequest(BaseModel):
    """Request payload for making an automated phone call."""
    email: EmailStr = Field(...,
                            description="Prospect's email address (required)")
    phone_number: Optional[str] = Field(
        default=None, description="Phone number (optional, falls back to DB)")
    representative: Optional[str] = Field(
        default=None, description="Representative (optional, falls back to DB)")


db = {"email", "industry_used", "company_used", "contact_name_used",
      "engagement_level_used", "phone_number_used", None, None, "company_info", "representative"}
details = {
    "prospects": [
        {
            "email": "folanathanzy@gmail.com",
            "industry": "technology",
            "company_name": "TechCorp",
            "contact_name": "Fola Nathan",
            "engagement_level": "Medium",
            "phone_number": "+2349069552306"
        },
        {
            "email": "nathanzyfola@gmail.com",
            "industry": "finance",
            "company_name": "FinSecure",
            "contact_name": "Nathanzy Fola",
            "engagement_level": "High",
            "phone_number": "+2349069552306"
        }
    ],
    "company_info": "Sigma Insurance specializes in providing customized insurance solutions for various industries.",
    "representative": {
        "name": "Folahanmi Ojokuku",
        "email": "ojokukufolahanmi@gmail.com",
        "phone": "+2348097164378"
    }
}
