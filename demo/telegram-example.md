# Telegram Manager Notification Example

```
🔴 New Lead: pricing_request 💰
Priority: HIGH

👤 Anna Schmidt
📧 anna@berlin-startup.de
📞 +49 30 123456
📥 Source: web_form

💬 Message: Hi, we need WhatsApp automation for our beauty salon chain (5 locations). What's your pricing? We have budget 5000 EUR and need it ASAP this week...

🤖 Classification:
• Intent: pricing_request
• Summary: pricing_request from Anna Schmidt with budget 5000 EUR, urgency: asap
• Budget: 5000 EUR
• Urgency: asap
• Reasoning: Detected intent via keywords: pricing_request, spam=False, budget=found

✅ CRM Contact: 1001 - anna@berlin-startup.de
💼 Deal Created: 2001 - pricing_request - Anna Schmidt (high)
Amount: 5000 EUR
```

For spam:
```
🚫 Not creating deal - spam or not a lead, filtered out

👤 Crypto Promo
📧 promo@spam-crypto.biz
💬 Message: Buy followers cheap! ...

🤖 Classification:
• Intent: spam
• Summary: Spam detected...
• Budget: not mentioned (correctly null)

🚫 NOT creating deal - spam or not a lead, filtered out
```
