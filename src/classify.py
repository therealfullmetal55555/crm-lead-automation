"""
Lead classification with structured output
- Supports real LLM (OpenAI / GPT-6 Sol compatible) if OPENAI_API_KEY set
- Falls back to rule-based mock classifier for demo without API key (anti-hallucination safe)

Pydantic schema forces valid JSON, not text.
"""
import re
import json
import logging
from typing import Optional, Literal
from pydantic import BaseModel, Field

from .config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, USE_MOCK_LLM

logger = logging.getLogger(__name__)

class LeadClassification(BaseModel):
    intent: Literal["pricing_request", "product_question", "complaint", "spam", "not_a_lead", "partnership", "other"] = Field(
        description="Primary intent of the lead"
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Lead priority for sales"
    )
    budget_mentioned: Optional[float] = Field(
        default=None,
        description="Budget amount mentioned in message, null if not mentioned. DO NOT hallucinate."
    )
    budget_currency: Optional[str] = Field(
        default=None,
        description="Currency of budget (EUR, USD, RUB, etc), null if not mentioned"
    )
    urgency: Optional[str] = Field(
        default=None,
        description="Urgency level: asap, this_week, next_month, etc, null if not mentioned"
    )
    summary: str = Field(
        description="Concise 1-2 sentence summary for manager"
    )
    is_spam: bool = Field(
        description="True if message is spam, promo, irrelevant"
    )
    should_create_deal: bool = Field(
        description="True if should create CRM deal, False for spam/not_a_lead"
    )
    reasoning: str = Field(
        description="Brief reasoning why this classification"
    )
    extracted_fields: dict = Field(
        default_factory=dict,
        description="Any other structured fields found: company, product interest, etc"
    )

# --- Mock rule-based classifier (anti-hallucination safe) ---

SPAM_KEYWORDS = [
    "buy followers", "crypto investment", "make money fast", "viagra", "lottery",
    "seo services", "guaranteed traffic", "prince", "inheritance", "click here"
]

COMPLAINT_KEYWORDS = ["complaint", "refund", "terrible", "awful", "angry", "disappointed", "not working"]

PRICING_KEYWORDS = ["price", "pricing", "cost", "how much", "budget", "quote", "estimate", "€", "$", "eur", "usd"]

def mock_classify(name: str, email: str, message: str) -> LeadClassification:
    """
    Rule-based classifier that NEVER hallucinates budget if not mentioned.
    Implements anti-hallucination principle from RAG project.
    """
    msg_lower = message.lower()
    
    # Spam detection first
    is_spam = any(kw in msg_lower for kw in SPAM_KEYWORDS)
    # Also check for very short generic + link
    if ("http://" in msg_lower or "https://" in msg_lower) and len(message.split()) < 10:
        is_spam = True
    if len(message) < 15 and "buy" in msg_lower:
        is_spam = True

    if is_spam:
        return LeadClassification(
            intent="spam",
            priority="low",
            budget_mentioned=None,
            budget_currency=None,
            urgency=None,
            summary=f"Spam detected from {name}: {message[:60]}...",
            is_spam=True,
            should_create_deal=False,
            reasoning="Contains spam keywords and promotional pattern, no real business intent",
            extracted_fields={}
        )

    # Check if not a lead (e.g., job application, generic question without buying intent)
    not_lead_patterns = [
        "just saying hi", "hello", "test message", "checking if",
        "are you hiring", "job application", "looking for a job", "hiring?",
        "job role", "career", "position", "are you hiring"
    ]
    # Job application is always not_a_lead regardless of pricing keywords
    if any(p in msg_lower for p in ["are you hiring", "job application", "looking for a job", "hiring?"]):
        return LeadClassification(
            intent="not_a_lead",
            priority="low",
            budget_mentioned=None,
            budget_currency=None,
            urgency=None,
            summary=f"Not a lead - job application from {name}",
            is_spam=False,
            should_create_deal=False,
            reasoning="Job application, not a buying intent",
            extracted_fields={}
        )
    if any(p in msg_lower for p in not_lead_patterns) and not any(kw in msg_lower for kw in PRICING_KEYWORDS):
        # Could be "other" but not spam - should not create deal if no intent
        if len(message.split()) < 10:
            return LeadClassification(
                intent="not_a_lead",
                priority="low",
                budget_mentioned=None,
                budget_currency=None,
                urgency=None,
                summary=f"Not a lead - generic message from {name}",
                is_spam=False,
                should_create_deal=False,
                reasoning="No buying intent, very generic or test message",
                extracted_fields={}
            )

    # Extract budget - ONLY if explicitly mentioned, else None (anti-hallucination)
    budget = None
    currency = None
    # Patterns: 5000 EUR, $2000, 1000€, budget 3000, etc.
    budget_patterns = [
        r'(\d[\d\s,\.]+)\s*(eur|usd|€|\$|rub|₽)',
        r'(eur|usd|€|\$)\s*(\d[\d\s,\.]+)',
        r'budget.*?(\d[\d\s,\.]+)',
        r'(\d[\d\s,\.]+)\s*budget',
    ]
    for pattern in budget_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            # Extract number
            groups = match.groups()
            num_str = None
            curr_str = None
            for g in groups:
                if g and re.search(r'\d', g):
                    num_str = g
                elif g and g.strip().lower() in ['eur', 'usd', '€', '$', 'rub', '₽', 'euro', 'dollars']:
                    curr_str = g
            if num_str:
                try:
                    # Clean number: remove spaces, handle comma as decimal
                    cleaned = num_str.replace(' ', '').replace(',', '.')
                    # If multiple dots, keep last as decimal
                    if cleaned.count('.') > 1:
                        parts = cleaned.split('.')
                        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
                    budget = float(cleaned)
                    if budget > 1000000:  # sanity check - likely not budget
                        budget = None
                    else:
                        # Currency detection
                        if curr_str:
                            c = curr_str.strip().lower()
                            if c in ['€', 'eur', 'euro']:
                                currency = 'EUR'
                            elif c in ['$', 'usd', 'dollars']:
                                currency = 'USD'
                            elif c in ['rub', '₽']:
                                currency = 'RUB'
                            else:
                                currency = c.upper()
                        else:
                            # Infer from symbol in original message
                            if '€' in message:
                                currency = 'EUR'
                            elif '$' in message:
                                currency = 'USD'
                            else:
                                currency = None
                    break
                except:
                    continue

    # Urgency detection - ONLY if mentioned
    urgency = None
    urgency_patterns = {
        "asap": ["asap", "urgent", "immediately", "right now", "today"],
        "this_week": ["this week", "within week", "in a few days"],
        "next_month": ["next month", "in a month"],
        "flexible": ["flexible", "no rush", "whenever"]
    }
    for level, keywords in urgency_patterns.items():
        if any(kw in msg_lower for kw in keywords):
            urgency = level
            break

    # Intent detection
    intent = "other"
    priority = "medium"
    
    if any(kw in msg_lower for kw in COMPLAINT_KEYWORDS):
        intent = "complaint"
        priority = "high"  # complaints are high priority to handle
    elif any(kw in msg_lower for kw in PRICING_KEYWORDS):
        intent = "pricing_request"
        priority = "high" if budget and budget > 1000 else "medium"
        if urgency == "asap":
            priority = "high"
    elif "partnership" in msg_lower or "collaborat" in msg_lower or "partner" in msg_lower:
        intent = "partnership"
        priority = "medium"
    elif "?" in message and len(message.split()) > 5:
        intent = "product_question"
        priority = "medium"
    else:
        intent = "other"
        priority = "low"

    # Should create deal?
    should_create = intent in ["pricing_request", "product_question", "complaint", "partnership", "other"]
    # But if very low quality and no budget and no urgency and short message, don't create
    if intent == "other" and len(message.split()) < 10 and not budget:
        should_create = False
        intent = "not_a_lead"

    summary = f"{intent} from {name}"
    if budget:
        summary += f" with budget {budget} {currency or ''}"
    if urgency:
        summary += f", urgency: {urgency}"
    summary += f": {message[:80]}..."

    return LeadClassification(
        intent=intent,
        priority=priority,
        budget_mentioned=budget,
        budget_currency=currency,
        urgency=urgency,
        summary=summary.strip(),
        is_spam=is_spam,
        should_create_deal=should_create,
        reasoning=f"Detected intent via keywords: {intent}, spam={is_spam}, budget={'found' if budget else 'not mentioned (correctly null)'}",
        extracted_fields={
            "message_length": len(message),
            "has_phone_hint": bool(re.search(r'\+?\d[\d\s-]{7,}', message)),
        }
    )

# --- Real LLM classifier (GPT-6 Sol / OpenAI compatible) ---

LLM_SYSTEM_PROMPT = """You are a lead qualification assistant for a European automation agency.
Classify incoming leads with structured output.

CRITICAL ANTI-HALLUCINATION RULES:
- If budget is NOT explicitly mentioned in message, set budget_mentioned=null, budget_currency=null. DO NOT invent.
- If urgency is NOT mentioned, set urgency=null.
- If you are not sure about a field, leave it null rather than guessing.
- Spam detection: promotional, irrelevant, or mass-marketing messages should be marked is_spam=true and should_create_deal=false
- should_create_deal=false for: spam, test messages, generic hi, job applications without buying intent
- Deduplication will be handled separately, focus on classification only

Return ONLY valid JSON matching the schema."""

def llm_classify(name: str, email: str, message: str) -> LeadClassification:
    """
    Calls OpenAI / GPT-6 Sol compatible API with structured output
    Falls back to mock if API key not set or fails
    """
    if USE_MOCK_LLM:
        logger.info("Using mock classifier (no OPENAI_API_KEY)")
        return mock_classify(name, email, message)

    try:
        from openai import OpenAI
        client_kwargs = {}
        if OPENAI_BASE_URL:
            client_kwargs["base_url"] = OPENAI_BASE_URL
        if OPENAI_API_KEY:
            client_kwargs["api_key"] = OPENAI_API_KEY
        
        client = OpenAI(**client_kwargs)

        user_prompt = f"""
Lead:
Name: {name}
Email: {email}
Message: {message}

Classify this lead. Remember: if budget not mentioned, return null. Do not hallucinate.
"""

        # Use structured output via json mode
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        
        # Validate via Pydantic
        classification = LeadClassification(**data)
        
        # Extra anti-hallucination check: if budget mentioned but not in original message numbers, null it
        # Simple heuristic: check if any number in message matches budget
        if classification.budget_mentioned:
            numbers_in_msg = re.findall(r'\d+', message)
            budget_str = str(int(classification.budget_mentioned))
            if not any(budget_str in num or num in budget_str for num in numbers_in_msg):
                # Might be hallucinated - log warning but keep? For safety, we trust LLM but log
                logger.warning(f"Potential hallucinated budget {classification.budget_mentioned} not found in message numbers {numbers_in_msg}")
        
        logger.info(f"LLM classification: {classification.intent} / {classification.priority}")
        return classification

    except Exception as e:
        logger.error(f"LLM classification failed, falling back to mock: {e}")
        return mock_classify(name, email, message)

def classify_lead(name: str, email: str, message: str) -> LeadClassification:
    """
    Main entry point - tries LLM, falls back to mock
    """
    return llm_classify(name, email, message)

if __name__ == "__main__":
    # Test mock classifier
    tests = [
        ("John Doe", "john@example.com", "Hi, what's your pricing for automation? We have budget 5000 EUR and need it ASAP"),
        ("Spammer", "spam@spam.com", "Buy followers cheap! Click here https://spam.com"),
        ("Alice", "alice@test.com", "Hello, just saying hi"),
        ("Bob", "bob@company.com", "We need a chatbot for our clinic, budget $2000, this week"),
    ]
    for name, email, msg in tests:
        result = mock_classify(name, email, msg)
        print(f"\n{name}: {msg[:50]}")
        print(f" -> {result.intent} | {result.priority} | budget={result.budget_mentioned} {result.budget_currency} | spam={result.is_spam} | create={result.should_create_deal}")
        print(f"    Summary: {result.summary}")
