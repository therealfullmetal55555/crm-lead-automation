"""
Manager notifications via Telegram
"""
import logging
from typing import Optional, Dict, Any
import httpx

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .lead_intake import ValidatedLead
from .classify import LeadClassification

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else ""

    def format_lead_message(self, lead: ValidatedLead, classification: LeadClassification, crm_result: Dict[str, Any]) -> str:
        contact = crm_result.get("contact", {})
        deal = crm_result.get("deal")
        is_mock = crm_result.get("mock", False)

        # Priority emoji
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(classification.priority, "⚪")
        intent_emoji = {
            "pricing_request": "💰",
            "product_question": "❓",
            "complaint": "⚠️",
            "spam": "🚫",
            "not_a_lead": "👻",
            "partnership": "🤝",
            "other": "📩"
        }.get(classification.intent, "📩")

        lines = []
        lines.append(f"{priority_emoji} *New Lead: {classification.intent}* {intent_emoji}")
        lines.append(f"Priority: *{classification.priority.upper()}*")
        lines.append("")
        lines.append(f"👤 *{lead.name}*")
        lines.append(f"📧 `{lead.email}`")
        if lead.phone:
            lines.append(f"📞 `{lead.phone}`")
        lines.append(f"📥 Source: {lead.source}")
        lines.append("")
        lines.append(f"💬 Message: _{lead.message[:300]}{'...' if len(lead.message) > 300 else ''}_")
        lines.append("")
        lines.append(f"🤖 *Classification:*")
        lines.append(f"• Intent: {classification.intent}")
        lines.append(f"• Summary: {classification.summary}")
        if classification.budget_mentioned:
            lines.append(f"• Budget: {classification.budget_mentioned} {classification.budget_currency or ''}")
        else:
            lines.append(f"• Budget: not mentioned (correctly null)")
        if classification.urgency:
            lines.append(f"• Urgency: {classification.urgency}")
        lines.append(f"• Reasoning: {classification.reasoning}")
        lines.append("")

        if classification.is_spam or not classification.should_create_deal:
            lines.append("🚫 *NOT creating deal* - spam or not a lead, filtered out")
            return "\n".join(lines)

        # CRM info
        if contact:
            lines.append(f"✅ *CRM Contact:* {contact.get('id')} - {contact.get('email')}")
            if is_mock:
                lines.append(f"_(mock CRM)_")
            else:
                # Real HubSpot link format: https://app.hubspot.com/contacts/{portalId}/contact/{contactId}
                lines.append(f"Link: https://app.hubspot.com/contacts/.../contact/{contact.get('id')}/")

        if deal:
            lines.append(f"💼 *Deal Created:* {deal.get('id')} - {deal.get('dealname') or deal.get('properties', {}).get('dealname')}")
            if deal.get('amount'):
                lines.append(f"Amount: {deal.get('amount')} {deal.get('currency') or ''}")
            if not is_mock:
                lines.append(f"Deal link: https://app.hubspot.com/contacts/.../deal/{deal.get('id')}/")
            else:
                lines.append(f"Mock deal URL: {deal.get('hs_url', 'mock')}")
        else:
            if classification.should_create_deal:
                lines.append("⚠️ Deal was supposed to be created but failed")
            else:
                lines.append("No deal - filtered")

        lines.append("")
        lines.append(f"_Lead ID: {lead.lead_id}_")

        return "\n".join(lines)

    def send_message_sync(self, text: str, parse_mode: str = "Markdown") -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured - mock send")
            print(f"\n[MOCK TELEGRAM to {self.chat_id or 'manager'}]\n{text}\n")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    logger.info(f"Telegram notification sent to {self.chat_id}")
                    return True
                else:
                    logger.error(f"Telegram API error: {data}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False

    def notify_new_lead(self, lead: ValidatedLead, classification: LeadClassification, crm_result: Dict[str, Any]) -> bool:
        message = self.format_lead_message(lead, classification, crm_result)
        return self.send_message_sync(message)

class MockNotifier:
    def notify_new_lead(self, lead, classification, crm_result):
        print("\n=== MOCK MANAGER NOTIFICATION ===")
        notifier = TelegramNotifier()
        msg = notifier.format_lead_message(lead, classification, crm_result)
        print(msg)
        print("=== END NOTIFICATION ===\n")
        return True

def get_notifier():
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        return TelegramNotifier()
    else:
        return MockNotifier()
