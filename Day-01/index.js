import { qualifyLead, classifyTicket, draftEmail, extractData } from "./AIService.js";

async function main() {
  console.log("--- Lead Qualification ---");
  console.log(await qualifyLead(
    "Company: Acme Corp, 500 employees, downloaded our pricing PDF twice, replied to our cold email asking about enterprise plans."
  ));

  console.log("\n--- Ticket Classification ---");
  console.log(await classifyTicket(
    "I was charged twice for my subscription this month and need a refund ASAP."
  ));

  console.log("\n--- Email Draft ---");
  console.log(await draftEmail({
    recipient: "a client who missed a scheduled demo call",
    purpose: "politely follow up and offer to reschedule",
  }));

  console.log("\n--- Data Extraction ---");
  console.log(await extractData(
    "Hi, this is John Smith from TechCorp. You can reach me at john@techcorp.com or 555-0192."
  ));
}

main();
