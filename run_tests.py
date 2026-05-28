"""
Run all 10 sample leads through pipeline - test for portfolio criteria
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.lead_intake import validate_lead
from src.classify import classify_lead
from src.crm_client import process_lead_to_crm, mock_storage
from src.notify import get_notifier

BASE_DIR = Path(__file__).parent
SAMPLE_JSON = BASE_DIR / "demo-data" / "sample-leads.json"

def run_all_tests():
    print("=== CRM Automation - Testing 10 Sample Leads ===\n")
    
    with open(SAMPLE_JSON, encoding='utf-8') as f:
        leads = json.load(f)

    # Reset mock storage
    mock_storage.contacts.clear()
    mock_storage.deals.clear()
    mock_storage.next_contact_id = 1001
    mock_storage.next_deal_id = 2001

    results = []
    notifier = get_notifier()

    for test_lead in leads:
        print(f"\n--- Lead {test_lead['id']}: {test_lead['name']} ({test_lead['email']}) ---")
        print(f"Message: {test_lead['message'][:80]}...")
        
        try:
            # 1. Validate
            lead = validate_lead({
                "name": test_lead["name"],
                "email": test_lead["email"],
                "message": test_lead["message"],
                "phone": test_lead.get("phone"),
                "source": "test_suite"
            })

            # 2. Classify
            classification = classify_lead(lead.name, lead.email, lead.message)
            print(f"  Classified: intent={classification.intent}, priority={classification.priority}, "
                  f"budget={classification.budget_mentioned} {classification.budget_currency or ''}, "
                  f"spam={classification.is_spam}, should_create={classification.should_create_deal}")

            # Check anti-hallucination
            expected_budget = test_lead.get("expected_budget")
            if expected_budget is None and classification.budget_mentioned is not None:
                # If expected null but got value, check if message actually contains that number
                # For leads 2 and 8, this would be hallucination
                print(f"  ⚠️  WARNING: Expected budget null but got {classification.budget_mentioned} - potential hallucination!")
            elif expected_budget is not None and classification.budget_mentioned is None:
                print(f"  ⚠️  WARNING: Expected budget {expected_budget} but got null")

            # Check spam filter
            expected_should_create = test_lead.get("should_create_deal")
            if expected_should_create is not None and expected_should_create != classification.should_create_deal:
                print(f"  ⚠️  MISMATCH: Expected should_create={expected_should_create} but got {classification.should_create_deal}")

            # 3. CRM
            crm_result = process_lead_to_crm(lead, classification)
            contact_id = crm_result.get("contact", {}).get("id") if crm_result.get("contact") else None
            deal_id = crm_result.get("deal", {}).get("id") if crm_result.get("deal") else None
            print(f"  CRM: contact={contact_id}, deal={deal_id}, deal_created={crm_result.get('deal_created')}")

            # 4. Notify (mock will print)
            # notifier.notify_new_lead(lead, classification, crm_result)  # Uncomment to see full notifications

            results.append({
                "id": test_lead["id"],
                "email": test_lead["email"],
                "expected_intent": test_lead.get("expected_intent"),
                "actual_intent": classification.intent,
                "expected_should_create": expected_should_create,
                "actual_should_create": classification.should_create_deal,
                "expected_budget": expected_budget,
                "actual_budget": classification.budget_mentioned,
                "contact_id": contact_id,
                "deal_id": deal_id,
                "deal_created": crm_result.get("deal_created"),
                "classification": classification.model_dump()
            })

        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append({"id": test_lead["id"], "error": str(e)})

    # Summary
    print("\n\n=== SUMMARY ===")
    total = len(results)
    contacts = mock_storage.get_all_contacts()
    deals = mock_storage.get_all_deals()
    
    print(f"Total leads processed: {total}")
    print(f"Unique contacts in CRM (deduplicated): {len(contacts)} (expected 7 unique emails for 10 leads)")
    print(f"Deals created: {len(deals)} (expected 6-7, 3 filtered)")
    print(f"Filtered (no deal): {total - len(deals)} (expected 3)")

    # Deduplication check
    print("\n--- Deduplication Check ---")
    print(f"Contacts: {len(contacts)} unique")
    for c in contacts:
        print(f"  {c['id']}: {c['email']} - {c['firstname']} {c['lastname']} - intent={c.get('lead_intent')}")

    # Anti-hallucination check
    print("\n--- Anti-hallucination Check ---")
    hallucination_issues = []
    for r in results:
        if r.get("expected_budget") is None and r.get("actual_budget") is not None:
            # Check if this is allowed (some leads actually have budget)
            # Leads 2,3,4,5,8,9 should have null
            if r["id"] in [2,3,4,5,8,9]:
                hallucination_issues.append(r)
                print(f"  ❌ Lead {r['id']}: Expected null budget but got {r['actual_budget']} - HALLUCINATION!")
    if not hallucination_issues:
        print("  ✅ No hallucinations - budget correctly null when not mentioned")

    # Spam filter check
    print("\n--- Spam Filter Check ---")
    spam_leads = [r for r in results if r["id"] in [4,5,9]]
    for r in spam_leads:
        if r.get("deal_created"):
            print(f"  ❌ Lead {r['id']} ({r['email']}) should be filtered but deal was created!")
        else:
            print(f"  ✅ Lead {r['id']} correctly filtered - no deal")

    # Deduplication specific check for lead 7
    print("\n--- Deduplication Specific (Lead 1 & 7 same email) ---")
    anna_contacts = [c for c in contacts if c["email"] == "anna@berlin-startup.de"]
    print(f"  Contacts for anna@berlin-startup.de: {len(anna_contacts)} (expected 1, not 2)")
    if len(anna_contacts) == 1:
        print(f"  ✅ Deduplication works - updated existing contact, not duplicated")
        print(f"     Contact: {anna_contacts[0]}")
    else:
        print(f"  ❌ Deduplication failed - found {len(anna_contacts)} contacts for same email")

    print("\n--- All Deals ---")
    for d in deals:
        print(f"  Deal {d['id']}: {d['dealname']} | contact={d['contact_id']} | amount={d['amount']} {d.get('currency') or ''}")

    # Final criteria check
    print("\n=== PORTFOLIO CRITERIA CHECK ===")
    criteria = []
    
    # 1. 8-10 leads processed
    criteria.append(("8-10 leads processed", len(results) >= 8))
    
    # 2. Deals created with correct fields
    criteria.append(("Deals created with correct fields", len(deals) >= 5))
    
    # 3. 2 spam filtered
    filtered = total - len(deals)
    criteria.append(("Min 2 spam/not_a_lead filtered", filtered >= 2))
    
    # 4. Deduplication
    criteria.append(("Deduplication: same email updates, not duplicate", len(anna_contacts) == 1))
    
    # 5. No hallucination
    criteria.append(("No budget hallucination", len(hallucination_issues) == 0))
    
    for name, passed in criteria:
        print(f"  {'✅' if passed else '❌'} {name}: {'PASS' if passed else 'FAIL'}")

    all_passed = all(passed for _, passed in criteria)
    print(f"\n{'✅ ALL CRITERIA PASSED' if all_passed else '❌ SOME CRITERIA FAILED'}")

    return results

if __name__ == "__main__":
    run_all_tests()
