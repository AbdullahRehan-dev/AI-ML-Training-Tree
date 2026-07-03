import json
from ai_service import qualify_lead, classify_ticket, draft_email, extract_data


def route_result(label: str, result: dict):
    print(f"\n--- {label} ---")
    print(json.dumps(result, indent=2))
    if result.get("needs_human_review"):
        print(f"⚠️  Flagged for human review (confidence: {result['confidence']})")


def get_multiline_input(prompt: str) -> str:
    """Lets the user paste/type multiple lines. Press Enter on an empty
    line to finish."""
    print(prompt + " (press Enter on an empty line when done):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def run_qualify_lead():
    text = get_multiline_input("Paste the lead info")
    if not text.strip():
        print("No input provided, skipping.")
        return
    try:
        result = qualify_lead(text)
        route_result("Lead Qualification", result)
    except Exception as err:
        print(f"Lead qualification failed after retries: {err}")


def run_classify_ticket():
    text = get_multiline_input("Paste the support ticket text")
    if not text.strip():
        print("No input provided, skipping.")
        return
    try:
        result = classify_ticket(text)
        route_result("Ticket Classification", result)
    except Exception as err:
        print(f"Ticket classification failed after retries: {err}")


def run_draft_email():
    recipient = input("Who is this email to (short description)? ")
    purpose = input("What's the purpose of the email? ")
    if not recipient.strip() or not purpose.strip():
        print("Recipient and purpose are required, skipping.")
        return
    try:
        result = draft_email(recipient=recipient, purpose=purpose)
        route_result("Email Draft", result)
    except Exception as err:
        print(f"Email draft failed after retries: {err}")


def run_extract_data():
    text = get_multiline_input("Paste the raw text to extract data from")
    if not text.strip():
        print("No input provided, skipping.")
        return
    try:
        result = extract_data(text)
        route_result("Data Extraction", result)
    except Exception as err:
        print(f"Data extraction failed after retries: {err}")


MENU = {
    "1": ("Qualify a lead", run_qualify_lead),
    "2": ("Classify a support ticket", run_classify_ticket),
    "3": ("Draft an email", run_draft_email),
    "4": ("Extract data from text", run_extract_data),
}


def main():
    while True:
        print("\nWhat would you like to do?")
        for key, (label, _) in MENU.items():
            print(f"  {key}. {label}")
        print("  q. Quit")

        choice = input("> ").strip().lower()

        if choice == "q":
            break
        elif choice in MENU:
            _, func = MENU[choice]
            func()
        else:
            print("Not a valid option, try again.")


if __name__ == "__main__":
    main()
