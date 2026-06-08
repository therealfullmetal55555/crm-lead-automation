"""
HubSpot CRM client with deduplication
- Supports real HubSpot API via private app token
- Mock mode if no token (for portfolio demo without real CRM)

HubSpot API docs:
- Contacts: POST /crm/v3/objects/contacts/search, POST /crm/v3/objects/contacts
- Deals: POST /crm/v3/objects/deals
- Associations: POST /crm/v3/associations/{fromType}/{toType}/batch/create or v4

Deduplication: search contact by email first, update if exists, else create.
"""
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import httpx

from .config import HUBSPOT_API_KEY, HUBSPOT_BASE_URL, USE_MOCK_CRM, DEAL_PIPELINE, DEAL_STAGE
from .lead_intake import ValidatedLead
from .classify import LeadClassification

logger = logging.getLogger(__name__)

# --- Mock CRM for demo without API key ---

class MockCRMStorage:
    """In-memory mock CRM that simulates HubSpot behavior"""
    def __init__(self):
        self.contacts: Dict[str, dict] = {}  # email -> contact
        self.deals: Dict[str, dict] = {}  # deal_id -> deal
        self.next_contact_id = 1001
        self.next_deal_id = 2001

    def search_contact_by_email(self, email: str) -> Optional[dict]:
        return self.contacts.get(email.lower())

    def create_or_update_contact(self, lead: ValidatedLead, classification: LeadClassification) -> dict:
        email = lead.normalized_email
        existing = self.search_contact_by_email(email)
        
        contact_data = {
            "email": email,
            "firstname": lead.name.split()[0] if lead.name else "",
            "lastname": " ".join(lead.name.split()[1:]) if len(lead.name.split()) > 1 else "",
            "phone": lead.phone or "",
            "lead_intent": classification.intent,
            "lead_priority": classification.priority,
            "lead_summary": classification.summary,
            "lead_source": lead.source,
            "budget": classification.budget_mentioned,
            "budget_currency": classification.budget_currency,
            "urgency": classification.urgency,
            "last_message": lead.message[:500],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing:
            # Update
            contact_id = existing["id"]
            existing.update(contact_data)
            existing["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"[MOCK] Updated contact {contact_id} for {email} (deduplication)")
            return existing
        else:
            # Create
            contact_id = str(self.next_contact_id)
            self.next_contact_id += 1
            contact = {
                "id": contact_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **contact_data
            }
            self.contacts[email] = contact
            logger.info(f"[MOCK] Created contact {contact_id} for {email}")
            return contact

    def create_deal(self, contact: dict, lead: ValidatedLead, classification: LeadClassification) -> Optional[dict]:
        if not classification.should_create_deal:
            logger.info(f"[MOCK] Skipping deal creation for {lead.email} - should_create_deal=False")
            return None

        # Check if deal already exists for this contact recently? For simplicity, allow multiple but log
        deal_id = str(self.next_deal_id)
        self.next_deal_id += 1

        deal = {
            "id": deal_id,
            "dealname": f"{classification.intent} - {lead.name} - {classification.priority}",
            "amount": classification.budget_mentioned,
            "currency": classification.budget_currency,
            "dealstage": DEAL_STAGE,
            "pipeline": DEAL_PIPELINE,
            "priority": classification.priority,
            "intent": classification.intent,
            "summary": classification.summary,
            "contact_id": contact["id"],
            "contact_email": contact["email"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hs_url": f"https://app.hubspot.com/contacts/123/deal/{deal_id}/ (mock)",
        }
        self.deals[deal_id] = deal
        logger.info(f"[MOCK] Created deal {deal_id} for contact {contact['id']}")
        return deal

    def get_all_contacts(self):
        return list(self.contacts.values())

    def get_all_deals(self):
        return list(self.deals.values())

# Global mock instance
mock_storage = MockCRMStorage()

# --- Real HubSpot client ---

class HubSpotClient:
    def __init__(self, api_key: str = HUBSPOT_API_KEY):
        self.api_key = api_key
        self.base_url = HUBSPOT_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def search_contact_by_email(self, email: str) -> Optional[dict]:
        """Search contact by email - deduplication"""
        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email
                }]
            }],
            "properties": ["email", "firstname", "lastname", "phone", "createdate", "lastmodifieddate"]
        }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if results:
                    logger.info(f"Found existing contact for {email}: {results[0]['id']}")
                    return results[0]
                return None
        except Exception as e:
            logger.error(f"HubSpot search failed for {email}: {e}")
            return None

    def create_contact(self, lead: ValidatedLead, classification: LeadClassification) -> Optional[dict]:
        url = f"{self.base_url}/crm/v3/objects/contacts"
        properties = {
            "email": lead.normalized_email,
            "firstname": lead.name.split()[0] if lead.name else "",
            "lastname": " ".join(lead.name.split()[1:]) if len(lead.name.split()) > 1 else "",
            "phone": lead.phone or "",
            # Custom properties - need to be created in HubSpot UI first, or use existing
            # For demo, we use standard + notes
        }
        # Add custom if you created them in HubSpot: lead_intent, etc.
        # For portfolio, we store summary in notes
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, headers=self.headers, json={"properties": properties})
                resp.raise_for_status()
                contact = resp.json()
                logger.info(f"Created HubSpot contact {contact['id']} for {lead.email}")
                return contact
        except Exception as e:
            logger.error(f"Failed to create contact: {e}")
            return None

    def update_contact(self, contact_id: str, lead: ValidatedLead, classification: LeadClassification) -> Optional[dict]:
        url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
        properties = {
            "phone": lead.phone or "",
            # You can update custom properties here
        }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.patch(url, headers=self.headers, json={"properties": properties})
                resp.raise_for_status()
                contact = resp.json()
                logger.info(f"Updated HubSpot contact {contact_id}")
                return contact
        except Exception as e:
            logger.error(f"Failed to update contact {contact_id}: {e}")
            return None

    def create_or_update_contact(self, lead: ValidatedLead, classification: LeadClassification) -> Optional[dict]:
        existing = self.search_contact_by_email(lead.normalized_email)
        if existing:
            # Update
            updated = self.update_contact(existing["id"], lead, classification)
            return updated or existing
        else:
            return self.create_contact(lead, classification)

    def create_deal(self, contact: dict, lead: ValidatedLead, classification: LeadClassification) -> Optional[dict]:
        if not classification.should_create_deal:
            logger.info(f"Skipping deal creation - should_create_deal=False")
            return None

        url = f"{self.base_url}/crm/v3/objects/deals"
        dealname = f"{classification.intent} - {lead.name} ({classification.priority})"
        properties = {
            "dealname": dealname,
            "dealstage": DEAL_STAGE,
            "pipeline": DEAL_PIPELINE,
            "amount": str(classification.budget_mentioned) if classification.budget_mentioned else "",
            "closedate": None,
            # Custom: priority, intent, summary -> create custom properties in HubSpot or use description
            "description": f"{classification.summary}\n\nOriginal message: {lead.message}\n\nReasoning: {classification.reasoning}"
        }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, headers=self.headers, json={"properties": properties})
                resp.raise_for_status()
                deal = resp.json()
                logger.info(f"Created HubSpot deal {deal['id']}")

                # Associate deal to contact
                self.associate_deal_to_contact(deal["id"], contact["id"])
                return deal
        except Exception as e:
            logger.error(f"Failed to create deal: {e}")
            return None

    def associate_deal_to_contact(self, deal_id: str, contact_id: str):
        """Associate deal to contact"""
        # v4 associations
        url = f"{self.base_url}/crm/v4/objects/deals/{deal_id}/associations/contacts/{contact_id}"
        payload = {
            "associationCategory": "HUBSPOT_DEFINED",
            "associationTypeId": 3  # deal to contact
        }
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.put(url, headers=self.headers, json=payload)
                # 201 or 200 is success, 409 if already associated
                if resp.status_code in [200, 201, 204, 409]:
                    logger.info(f"Associated deal {deal_id} to contact {contact_id}")
                else:
                    logger.warning(f"Association response: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Failed to associate deal to contact: {e}")

# --- Unified interface ---

def get_crm_client():
    if USE_MOCK_CRM:
        logger.info("Using Mock CRM (no HUBSPOT_API_KEY)")
        return mock_storage
    else:
        return HubSpotClient()

def process_lead_to_crm(lead: ValidatedLead, classification: LeadClassification) -> Dict[str, Any]:
    """
    Main function: deduplicate contact, create/update, then create deal if needed
    Returns dict with contact, deal, and status
    """
    client = get_crm_client()

    if isinstance(client, MockCRMStorage):
        contact = client.create_or_update_contact(lead, classification)
        deal = client.create_deal(contact, lead, classification)
        return {
            "contact": contact,
            "deal": deal,
            "is_new_contact": True,  # simplified
            "mock": True,
            "deal_created": deal is not None
        }
    else:
        # Real HubSpot
        contact = client.create_or_update_contact(lead, classification)
        if not contact:
            return {"error": "Failed to create/update contact", "contact": None, "deal": None}
        
        deal = client.create_deal(contact, lead, classification)
        return {
            "contact": contact,
            "deal": deal,
            "mock": False,
            "deal_created": deal is not None
        }

if __name__ == "__main__":
    # Test mock
    from .lead_intake import ValidatedLead
    from .classify import mock_classify

    lead = ValidatedLead(name="John Doe", email="john@example.com", message="Need pricing, budget 5000 EUR ASAP")
    cls = mock_classify(lead.name, lead.email, lead.message)
    result = process_lead_to_crm(lead, cls)
    print(result)

    # Test deduplication
    lead2 = ValidatedLead(name="John Doe", email="john@example.com", message="Second message, same email")
    cls2 = mock_classify(lead2.name, lead2.email, lead2.message)
    result2 = process_lead_to_crm(lead2, cls2)
    print("\nSecond lead same email (should update, not duplicate):")
    print(result2)
    print(f"Total contacts in mock: {len(mock_storage.get_all_contacts())}")  # should be 1
