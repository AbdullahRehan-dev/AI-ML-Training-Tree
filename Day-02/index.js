import { qualifyLead, classifyTicket, draftEmail, extractData } from "./AIService.js";

// Simulates routing a low-confidence result somewhere a human would see it.
// In a real system this might push to a queue, a Slack channel, a review dashboard, etc.
function routeResult(label, result) {
  console.log(`\n--- ${label} ---`);
  console.log(JSON.stringify(result, null, 2));
  if (result.needsHumanReview) {
    console.log(`⚠️  Flagged for human review (confidence: ${result.confidence})`);
  }
}

async function main() {
  try {
    const lead = await qualifyLead(
      "Company: Acme Corp, 500 employees, downloaded our pricing PDF twice, replied to our cold email asking about enterprise plans."
    );
    routeResult("Lead Qualification", lead);
  } catch (err) {
    console.error("Lead qualification failed after retries:", err.message);
  }

  try {
    const ticket = await classifyTicket(
      "I was charged twice for my subscription this month and need a refund ASAP."
    );
    routeResult("Ticket Classification", ticket);
  } catch (err) {
    console.error("Ticket classification failed after retries:", err.message);
  }

  try {
    const email = await draftEmail({
      recipient: "a client who missed a scheduled demo call",
      purpose: "politely follow up and offer to reschedule",
    });
    routeResult("Email Draft", email);
  } catch (err) {
    console.error("Email draft failed after retries:", err.message);
  }

  try {
    const data = await extractData(
      "Hi, this is John Smith from TechCorp. You can reach me at john@techcorp.com or 555-0192."
    );
    routeResult("Data Extraction", data);
  } catch (err) {
    console.error("Data extraction failed after retries:", err.message);
  }
}

main();
