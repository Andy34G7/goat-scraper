import { createOpenAI } from '@ai-sdk/openai';
import { createAnthropic } from '@ai-sdk/anthropic';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { createOllama } from 'ollama-ai-provider';
import { streamText, convertToModelMessages } from 'ai';

export const maxDuration = 60; // Allow longer responses

export async function POST(req: Request) {
    try {
        const { messages, provider, apiKey, context } = await req.json();

        if (!provider || !apiKey) {
            return new Response(JSON.stringify({ error: "Missing provider or API key" }), { status: 400 });
        }

        let model: any;

        // Initialize the correct provider client with the provided API key
        if (provider === "openai") {
            const openai = createOpenAI({ apiKey });
            model = openai('gpt-4o');
        } else if (provider === "anthropic") {
            const anthropic = createAnthropic({ apiKey });
            model = anthropic('claude-3-5-sonnet-latest');
        } else if (provider === "google") {
            const google = createGoogleGenerativeAI({ apiKey });
            model = google('gemini-2.5-flash');
        } else if (provider === "ollama") {
            const ollama = createOllama({ baseURL: apiKey || "http://localhost:11434/api" });
            model = ollama('llama3.1');
        } else {
            return new Response(JSON.stringify({ error: "Invalid provider" }), { status: 400 });
        }

        // Call the LLM
        const result = streamText({
            model,
            messages: await convertToModelMessages(messages),
            system: `You are an AI Study Assistant embedded in a document reader application (similar to NotebookLM).
Your goal is to help the user understand the documents they are reading.
If the user provides document context in their messages (e.g. text extracted from a PDF), you must base your answers primarily on that context.
Be concise, helpful, and educational.` + (context ? `\n\nDocument Context:\n${context}` : "")
        });

        return result.toUIMessageStreamResponse();
    } catch (error: any) {
        console.error("Chat API Error:", error);
        return new Response(JSON.stringify({ error: error.message || "An error occurred during chat generation" }), { status: 500 });
    }
}
