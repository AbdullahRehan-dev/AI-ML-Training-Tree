import json
from ai_service import qualify_lead, classify_ticket, draft_email, extract_data


def route_result(label: str, result: dict):
    print(f"\n--- {label} ---")
    print(json.dumps(result, indent=2))
    if result.get("needs_human_review"):
        print(f"⚠️  Flagged for human review (confidence: {result['confidence']})")


def main():
    try:
        lead = qualify_lead(
            "Company: Acme Corp, 500 employees, downloaded our pricing PDF twice, "
            "replied to our cold email asking about enterprise plans."
        )
        route_result("Lead Qualification", lead)
    except Exception as err:
        print(f"Lead qualification failed after retries: {err}")

    try:
        ticket = classify_ticket(
            "I was charged twice for my subscription this month and need a refund ASAP."
        )
        route_result("Ticket Classification", ticket)
    except Exception as err:
        print(f"Ticket classification failed after retries: {err}")

    try:
        email = draft_email(
            recipient="a client who missed a scheduled demo call",
            purpose="politely follow up and offer to reschedule",
        )
        route_result("Email Draft", email)
    except Exception as err:
        print(f"Email draft failed after retries: {err}")

    try:
        data = extract_data(
            "Hi, this is John Smith from TechCorp. You can reach me at "
            "john@techcorp.com or 555-0192."
        )
        route_result("Data Extraction", data)
    except Exception as err:
        print(f"Data extraction failed after retries: {err}")


if __name__ == "__main__":
    main()
