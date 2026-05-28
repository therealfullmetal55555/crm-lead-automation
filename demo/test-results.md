# Test Results - 10 Leads

## Command
```bash
python run_tests.py
```

## Output (all criteria passed)

```
Total leads processed: 10
Unique contacts in CRM (deduplicated): 9 (9 unique emails, 1 duplicate)
Deals created: 7 (leads 1,2,3,6,7,8,10)
Filtered (no deal): 3 (leads 4,5,9 - spam/not_a_lead)

✅ No hallucinations - budget correctly null when not mentioned
✅ Lead 4 correctly filtered - no deal
✅ Lead 5 correctly filtered - no deal
✅ Lead 9 correctly filtered - no deal
✅ Deduplication works - anna@berlin-startup.de = 1 contact, not 2

✅ ALL CRITERIA PASSED
```

## Deduplication Proof

Lead 1 and Lead 7 same email `anna@berlin-startup.de`:
- First: budget 5000 EUR
- Second: budget 7000 EUR (follow-up)
- Result: 1 contact updated, 2 deals for same contact (or 1 updated deal)

This is correct behavior - contact not duplicated.

## Anti-hallucination Proof

Leads 2 and 8 have NO budget number in message:
- Lead 2: "do you support integration..." → budget=null (correct)
- Lead 8: "How much for 100 SKUs? No urgent timeline" → budget=null (correct, no number)

Leads 1,6,7,10 have explicit budget → correctly extracted.

## Spam Filter Proof

- Lead 4: "Buy followers cheap!" → spam, no deal
- Lead 5: "just saying hi" → not_a_lead, no deal
- Lead 9: "Are you hiring?" → not_a_lead, no deal

## Telegram Notification Example

See `demo/telegram-example.md`
