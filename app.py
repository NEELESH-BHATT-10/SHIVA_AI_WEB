import os
import re
import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

SYSTEM_PROMPT = """
You are SHIVA AI, a helpful AI assistant.

Your creator, owner, developer and founder is Neelesh Bhatt.

Whenever someone asks who created you, who owns you, who made you,
who developed you, who built you, or similar questions, answer:

Neelesh Bhatt.

Never name another person as your creator.
Be helpful, respectful and concise.
"""

# Detect questions about SHIVA AI's creator.
CREATOR_PATTERNS = [
    r"\bwho\s+(?:is|are)\s+your\s+(?:owner|creator|developer|founder|maker|boss)\b",
    r"\bwho\s+(?:made|created|built|developed|invented|designed)\s+you\b",
    r"\bwho\s+owns\s+you\b",
    r"\bwho\s+do\s+you\s+belong\s+to\b",
    r"\bwho\s+is\s+behind\s+you\b",
    r"\bwho\s+(?:made|created|built|developed)\s+shiva\s*ai\b",
    r"\bwho\s+is\s+your\s+human\b",
    r"\byour\s+(?:owner|creator|developer|founder)\b"
]


def is_creator_question(message):
    text = re.sub(r"\s+", " ", message.lower()).strip()

    return any(
        re.search(pattern, text)
        for pattern in CREATOR_PATTERNS
    )


# Website homepage
@app.route("/")
def home():
    return send_from_directory(".", "index.html")


# Website health check
@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "name": "SHIVA AI"
    })


# AI chat API
@app.route("/api/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    user_message = str(
        data.get("message", "")
    ).strip()

    if not user_message:
        return jsonify({
            "reply": "Please type a message first."
        }), 400

    # Always answer creator questions directly.
    if is_creator_question(user_message):
        return jsonify({
            "reply": "Neelesh Bhatt."
        })

    # Get API key securely from environment variables.
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return jsonify({
            "reply": "AI service is not configured. Please add OPENROUTER_API_KEY."
        }), 503

    try:

        response = requests.post(
            OPENROUTER_URL,

            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv(
                    "SITE_URL",
                    "https://example.com"
                ),
                "X-Title": "SHIVA AI"
            },

            json={
                "model": MODEL,

                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            },

            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        ai_reply = result["choices"][0]["message"]["content"]

        return jsonify({
            "reply": ai_reply
        })

    except requests.Timeout:

        return jsonify({
            "reply": "The AI service took too long. Please try again."
        }), 504

    except (
        requests.RequestException,
        KeyError,
        IndexError,
        ValueError
    ):

        app.logger.exception("OpenRouter API error")

        return jsonify({
            "reply": "Connection error. Please try again."
        }), 502


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
