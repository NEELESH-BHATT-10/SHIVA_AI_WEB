 import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="SHIVA AI")

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "openrouter/free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

_requests = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@app.get("/", response_class=HTMLResponse)
async def home():
    path = Path(__file__).parent / "index.html"
    if not path.exists():
        raise HTTPException(status_code=500, detail="index.html not found")
    return path.read_text(encoding="utf-8")


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY is missing from Render environment variables."
        )

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _requests.get(client_ip, []) if now - t < 60]

    if len(recent) >= 10:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute."
        )

    recent.append(now)
    _requests[client_ip] = recent

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                    "X-Title": "SHIVA AI",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are SHIVA AI, a helpful assistant. "
                                "Respond clearly, respectfully, and concisely."
                            ),
                        },
                        {"role": "user", "content": body.message},
                    ],
                },
            )

        if response.is_error:
            print("OpenRouter error:", response.status_code, response.text[:1000])
            raise HTTPException(
                status_code=502,
                detail=f"OpenRouter request failed (HTTP {response.status_code}). Check the server logs and model availability."
            )

        data = response.json()
        answer = data["choices"][0]["message"]["content"]

        if not answer:
            raise HTTPException(status_code=502, detail="The AI returned an empty response.")

        return {"reply": answer}

    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        raise HTTPException(
            status_code=502,
            detail="Could not get a response from OpenRouter. Check Render logs and free-model availability."
        )

