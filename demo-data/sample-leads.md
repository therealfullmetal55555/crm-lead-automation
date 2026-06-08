# Sample Leads — 10 synthetic leads for testing

This file documents 10 test leads covering all edge cases required by brief.

| ID | Name | Email | Intent | Priority | Budget | Should Create Deal | Notes |
|----|------|-------|--------|----------|--------|-------------------|-------|
| 1 | Anna Schmidt | anna@berlin-startup.de | pricing_request | high | 5000 EUR | ✅ Yes | High-intent, ASAP, German market |
| 2 | Mark Johnson | mark@clinic-uk.co.uk | product_question | medium | null (correct) | ✅ Yes | No budget mentioned - anti-hallucination test |
| 3 | Sophie Laurent | sophie@salon-paris.fr | complaint | high | null | ✅ Yes | Complaint = high priority |
| 4 | Crypto Promo | promo@spam-crypto.biz | spam | low | null | ❌ No | SPAM filter test #1 |
| 5 | Test User | test@test.com | not_a_lead | low | null | ❌ No | Generic hi - filter test #2 |
| 6 | David Kim | david@agency-ny.com | partnership | medium | 10000 USD | ✅ Yes | Partnership with budget |
| 7 | Anna Schmidt (dup) | anna@berlin-startup.de | pricing_request | high | 7000 EUR | ✅ Yes | DUPLICATE - same email as #1, should update not duplicate |
| 8 | Elena Petrova | elena@ecom-store.ru | pricing_request | medium | null (correct) | ✅ Yes | No explicit budget number - must be null |
| 9 | James Wilson | james@saas-startup.io | not_a_lead | low | null | ❌ No | Job application - filter test #3 |
| 10 | Linda Müller | linda@wellness-berlin.de | pricing_request | medium | 3000 EUR | ✅ Yes | Budget + next_month urgency |

## Key tests:

- **Anti-hallucination:** Leads 2 and 8 have NO budget mentioned → budget_mentioned must be null, not invented. Same for urgency.
- **Spam filter:** Leads 4, 5, 9 must have should_create_deal=false and no deal created in HubSpot.
- **Deduplication:** Lead 7 same email as Lead 1 → should update existing contact, not create duplicate. Total contacts should be 7 unique emails for 10 leads, not 10.
- **Priority:** Lead 1 ASAP + budget = high, Lead 3 complaint = high.

## Expected results after running all 10:

- Contacts in CRM: 7 unique (deduped)
- Deals created: 6 (leads 1,2,3,6,8,10) + lead 7 updates deal for lead 1? Or creates second deal for same contact? Implementation: contact updated, new deal created for same contact is allowed (follow-up). For stricter dedup, we could update deal. Current mock: creates new deal for same contact but contact count stays 1.
- Filtered (no deal): 3 leads (4,5,9)
- Budget correctly null for 2,8,3,4,5,9
- Telegram alerts: 6 deal alerts + 3 filtered logs

See `sample-leads.json` for machine-readable version with expected values.
