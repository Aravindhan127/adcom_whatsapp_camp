import os
from typing import Dict, Any

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Lazy-init client so missing key doesn't crash the backend at startup
_client = None

def _get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            return None
        from groq import Groq
        _client = Groq(api_key=GROQ_API_KEY)
    return _client

def chat_with_knowledge(query: str, context: str = "") -> Dict[str, Any]:
    """
    RAG-style chat with Groq. Incorporates guardrails found in latest branch.
    Falls back gracefully if GROQ_API_KEY is not set.
    """
    client = _get_client()
    if not client:
        return {
            "response": "Thank you for your response! Our team will get back to you shortly.",
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0, "estimated_cost_inr": 0}
        }

    system_prompt = f"""
    You are the Adcom Enterprise AI Assistant. Your task is to provide polite, concise acknowledgments when a user interacts with our WhatsApp templates.

    CONTEXT FROM KNOWLEDGE BASE:
    \"\"\"{context}\"\"\"
    
    RULES:
    1. If the user clicks a button, acknowledge their choice warmly and professionally.
    2. Keep responses to EXACTLY ONE SENTENCE. This is for WhatsApp.
    3. Do NOT provide technical details or internal instructions.
    4. Use a helpful and respectful tone.
    5. If context is provided, align the response with our business identity (Adcom).
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            model="compound-beta",   # ✅ Correct Groq model name (was "groq/compound")
            temperature=0.4,
            max_tokens=600
        )
        
        response = chat_completion.choices[0].message.content
        usage = chat_completion.usage
        
        return {
            "response": response,
            "token_usage": {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "estimated_cost_usd": (usage.prompt_tokens * 0.05 + usage.completion_tokens * 0.10) / 1000000,
                "estimated_cost_inr": (usage.prompt_tokens * 0.05 + usage.completion_tokens * 0.10) / 1000000 * 84.0
            }
        }
    except Exception as e:
        print(f"AI ERROR: {e}")
        return {
            "response": "Thank you for your response! Our team will get back to you shortly.",
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0, "estimated_cost_inr": 0}
        }
