"""
Lead intake - validation and normalization
"""
import re
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

class RawLead(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Lead name")
    email: str = Field(..., description="Lead email")
    message: str = Field(..., min_length=5, max_length=5000, description="Lead message")
    source: str = Field(default="web_form", description="web_form | telegram | api")
    phone: Optional[str] = Field(default=None, description="Optional phone")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        # Simple regex, not strict EmailStr to avoid extra dependency
        pattern = r'^[^@]+@[^@]+\.[^@]+$'
        if not re.match(pattern, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Name too short')
        return v

    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        v = v.strip()
        if len(v) < 5:
            raise ValueError('Message too short')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return None
        # Keep only digits + +
        cleaned = re.sub(r'[^\d+]', '', v)
        if len(cleaned) < 7:
            return None
        return cleaned

class ValidatedLead(RawLead):
    lead_id: str = Field(default_factory=lambda: f"lead_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")
    normalized_email: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        self.normalized_email = self.email.lower().strip()

def validate_lead(data: dict) -> ValidatedLead:
    """
    Validates raw dict into ValidatedLead, raises ValidationError if invalid
    """
    raw = RawLead(**data)
    return ValidatedLead(**raw.model_dump())

# Example usage for Telegram bot intake
def from_telegram_message(tg_user: dict, text: str) -> ValidatedLead:
    """
    Convert Telegram message to lead
    tg_user: {id, first_name, last_name, username}
    """
    name = f"{tg_user.get('first_name','')} {tg_user.get('last_name','')}".strip() or tg_user.get('username','Telegram User')
    # Try to extract email from text if present, else use placeholder
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    email = email_match.group(0) if email_match else f"tg_{tg_user.get('id')}@telegram.local"
    return ValidatedLead(
        name=name,
        email=email,
        message=text,
        source="telegram"
    )
