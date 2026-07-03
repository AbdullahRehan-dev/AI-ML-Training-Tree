import OpenAI from "openai";
import "dotenv/config";

const groq = new OpenAI({
  apiKey: process.env.GROQ_API_KEY,
  baseURL: "https://api.groq.com/openai/v1",
});

const MODEL = "llama-3.3-70b-versatile";
const MAX_RETRIES = 3;
const CONFIDENCE_THRESHOLD = 0.7; // below this -> flagged for human review

/**
 * Strips common LLM wrapping artifacts (markdown code fences) from a JSON string.
 * Models often wrap JSON in ```json ... ``` even when told not to.
 */
function cleanJsonString(raw) {
  return raw
    .trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/```\s*$/i, "")
    .trim();
}

/**
 * Validates that `obj` has all `requiredKeys` and that confidence (if present)
 * is a number between 0 and 1. Returns an error string, or null if valid.
 */
function validateShape(obj, requiredKeys) {
  if (typeof obj !== "object" || obj === null || Array.isArray(obj)) {
    return "Response is not a JSON object";
  }
  for (const key of requiredKeys) {
    if (!(key in obj)) {
      return `Missing required key: "${key}"`;
    }
  }
  if ("confidence" in obj) {
    const c = obj.confidence;
    if (typeof c !== "number" || Number.isNaN(c) || c < 0 || c > 1) {
      return `"confidence" must be a number between 0 and 1, got: ${JSON.stringify(c)}`;
    }
  }
  return null;
}

/**
 * Core helper: calls Groq, parses + validates the JSON response, and retries
 * up to MAX_RETRIES times on network errors, malformed JSON, or schema
 * validation failures. Adds `needsHumanReview` based on model-reported
 * confidence before returning.
 *
 * Throws only after all retries are exhausted — callers should wrap calls
 * in try/catch and decide how to handle a hard failure (e.g. queue for
 * manual processing, alert, etc).
 */
async function callGroqJSON({ systemPrompt, userPrompt, requiredKeys, temperature = 0.3 }) {
  let lastError;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await groq.chat.completions.create({
        model: MODEL,
        temperature,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
      });

      const raw = response.choices[0].message.content;
      const cleaned = cleanJsonString(raw);

      let parsed;
      try {
        parsed = JSON.parse(cleaned);
      } catch (parseErr) {
        throw new Error(
          `JSON parse failed: ${parseErr.message}. Raw output: ${raw.slice(0, 200)}`
        );
      }

      const validationError = validateShape(parsed, requiredKeys);
      if (validationError) {
        throw new Error(`Schema validation failed: ${validationError}`);
      }

      // Defensive default in case the model omits confidence despite instructions
      if (typeof parsed.confidence !== "number") {
        parsed.confidence = 0.5;
      }

      parsed.needsHumanReview = parsed.confidence < CONFIDENCE_THRESHOLD;
      parsed._meta = { attempts: attempt };

      return parsed;
    } catch (err) {
      lastError = err;
      console.warn(`[callGroqJSON] Attempt ${attempt}/${MAX_RETRIES} failed: ${err.message}`);
      if (attempt < MAX_RETRIES) {
        const backoffMs = 500 * 2 ** (attempt - 1); // 500ms, 1000ms, 2000ms
        await new Promise((resolve) => setTimeout(resolve, backoffMs));
      }
    }
  }

  // All retries exhausted — fail loudly rather than silently returning garbage
  throw new Error(
    `callGroqJSON failed after ${MAX_RETRIES} attempts. Last error: ${lastError.message}`
  );
}

// 1. Lead qualification
export async function qualifyLead(leadInfo) {
  const system = `You are a B2B sales assistant. Given raw lead info, score the lead
from 1-10 on purchase likelihood and give a one-sentence reason.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "score": <integer 1-10>,
  "reason": "<one sentence>",
  "confidence": <number 0-1, how confident you are in this score>
}`;
  return callGroqJSON({
    systemPrompt: system,
    userPrompt: leadInfo,
    requiredKeys: ["score", "reason", "confidence"],
  });
}

// 2. Support ticket classifier
export async function classifyTicket(ticketText) {
  const system = `You are a support ticket classifier. Classify the ticket into
exactly one category: Billing, Technical, Account, or General.
Also assign urgency: Low, Medium, or High.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "category": "<Billing|Technical|Account|General>",
  "urgency": "<Low|Medium|High>",
  "confidence": <number 0-1, how confident you are in this classification>
}`;
  return callGroqJSON({
    systemPrompt: system,
    userPrompt: ticketText,
    requiredKeys: ["category", "urgency", "confidence"],
  });
}

// 3. Email drafter
export async function draftEmail({ recipient, purpose, tone = "professional" }) {
  const system = `You are an email drafting assistant. Write a ${tone} email under
120 words.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "subject": "<subject line>",
  "body": "<email body, under 120 words>",
  "confidence": <number 0-1, how confident you are this email fits the purpose well>
}`;
  const user = `Recipient: ${recipient}\nPurpose: ${purpose}`;
  return callGroqJSON({
    systemPrompt: system,
    userPrompt: user,
    requiredKeys: ["subject", "body", "confidence"],
    temperature: 0.6,
  });
}

// 4. Data extractor from raw text
export async function extractData(rawText) {
  const system = `Extract structured data from the text.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "name": <string or null>,
  "email": <string or null>,
  "phone": <string or null>,
  "company": <string or null>,
  "confidence": <number 0-1, how confident you are in the extracted fields>
}
Use null for any field not found in the text.`;
  return callGroqJSON({
    systemPrompt: system,
    userPrompt: rawText,
    requiredKeys: ["name", "email", "phone", "company", "confidence"],
    temperature: 0,
  });
}
