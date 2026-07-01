import OpenAI from "openai";
import "dotenv/config";

const groq = new OpenAI({
  apiKey: process.env.GROQ_API_KEY,
  baseURL: "https://api.groq.com/openai/v1",
});

async function main() {
  try {
    const response = await groq.chat.completions.create({
      model: "llama-3.3-70b-versatile",
      messages: [
        { role: "user", content: "Say hello and tell me one interesting fact about the moon." }
      ],
    });
    console.log("SUCCESS:");
    console.log(response.choices[0].message.content);
  } catch (err) {
    console.error("ERROR CAUGHT:");
    console.error(err);
  }
}

main();