import OpenAI from "openai";
import "dotenv/config";

const groq = new OpenAI({
  apiKey: process.env.GROQ_API_KEY,
  baseURL: "https://api.groq.com/openai/v1",
});

const MODEL = "llama-3.3-70b-versatile";

// Shared helper — every function below uses this
async function callGroq(systemPrompt, userPrompt, temperature = 0.3) {
  const response = await groq.chat.completions.create({
    model: MODEL,
    temperature,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
  });
  return response.choices[0].message.content;
}

// 1. Lead qualification
export async function qualifyLead(leadInfo) {
  const system = `You are a B2B sales assistant. Given raw lead info, score the lead
from 1-10 on purchase likelihood and give a one-sentence reason.
Respond ONLY in this exact format:
Score: <number>
Reason: <one sentence>`;
  return callGroq(system, leadInfo);
}

// 2. Support ticket classifier
export async function classifyTicket(ticketText) {
  const system = `You are a support ticket classifier. Classify the ticket into
exactly one category: Billing, Technical, Account, or General.
Also assign urgency: Low, Medium, or High.
Respond ONLY in this exact format:
Category: <category>
Urgency: <urgency>`;
  return callGroq(system, ticketText);
}

// 3. Email drafter
export async function draftEmail({ recipient, purpose, tone = "professional" }) {
  const system = `You are an email drafting assistant. Write a ${tone} email under
120 words. Include a subject line as the first line, formatted as "Subject: ..."`;
  const user = `Recipient: ${recipient}\nPurpose: ${purpose}`;
  return callGroq(system, user, 0.6);
}

// 4. Data extractor from raw text
export async function extractData(rawText) {
  const system = `Extract structured data from the text. Return ONLY valid JSON
with these keys: name, email, phone, company. Use null for any field not found.
Do not include markdown formatting or any explanation — JSON only.`;
  return callGroq(system, rawText, 0);
}