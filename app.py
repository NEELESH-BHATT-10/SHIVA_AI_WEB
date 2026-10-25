import os
import secrets

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="SHIVA AI")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.2")
ACCESS_CODE = os.getenv("SHIVA_ACCESS_CODE", "")

# Simple in-memory rate limit for this single-process starter.
_requests = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("index.html", "r", encoding="utf-8") as file:
            return file.read()
    except OSError:
        raise HTTPException(500, "Could not find index.html in the project folder.")


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    # Basic rate limit: 20 requests per minute per client.
    now = __import__("time").time()
    recent = [t for t in _requests.get(client_ip, []) if now - t < 60]

    if len(recent) >= 20:
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    recent.append(now)
    _requests[client_ip] = recent

    if ACCESS_CODE:
        supplied = request.headers.get("x-shiva-access-code", "")
        if not secrets.compare_digest(supplied, ACCESS_CODE):
            raise HTTPException(401, "Invalid access code.")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{OLLAMA_URL.rstrip('/')}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are SHIVA, a helpful personal AI assistant. "
                                "Respond clearly and concisely in English."
                            ),
                        },
                        {"role": "user", "content": body.message},
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        answer = data.get("message", {}).get("content", "")
        if not answer:
            raise HTTPException(502, "Ollama returned an empty response.")

        return {"reply": answer}

    except HTTPException:
        raise
    except httpx.HTTPError:
        raise HTTPException(
            502,
            "Could not connect to Ollama. Check that Ollama is running and the model is installed.",
        )

