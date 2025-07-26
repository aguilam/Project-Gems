from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
from groq import Groq
from fastapi.responses import Response

load_dotenv()

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")

groqClient = Groq(
    api_key=GROQ_API_KEY,
)


class LLMRequest(BaseModel):
    prompt: str
    model: str
    provider: list
    premium: bool
    systemPrompt: str


@app.post("/llm")
async def llm_query(request: LLMRequest):
    prodiver = request.provider
    if "cerebras" in prodiver and request.premium == True:
        return await query_cerebras(request)
    elif "groq" in prodiver:
        return await query_groq(request)
    elif  "mistral" in prodiver:
        return await query_mistral(request)
    elif  "openrouter" in prodiver:
        return await query_openrouter(request)
    elif  "cloudflare" in prodiver:
        return await query_cloudflare(request)


async def query_groq(request: LLMRequest):
    chat_completion = await groqClient.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": request.prompt,
            }
        ],
        model=request.model,
    )

    return {"text": chat_completion.choices[0]}


async def query_mistral(request: LLMRequest):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    payload = {
        "model": request.model,
        "messages": [{"role": "user", "content": request.prompt}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def query_huggingface(request: LLMRequest):
    url = f"https://api-inference.huggingface.co/models/{request.model}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {
        "inputs": request.prompt,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def query_openrouter(request: LLMRequest):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    payload = {
        "model": request.model,
        "messages": [{"role": "user", "content": request.prompt}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def query_cloudflare(request: LLMRequest):
    url = (
      f"https://api.cloudflare.com/client/v4/accounts/"
      f"5054130e5a7ddf582ed30bdae4809a82/ai/run/@{request.model}"
    )
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_KEY}"}
    payload = {"prompt": request.prompt}

    timeout = httpx.Timeout(
        connect=60.0,  # время на установку соединения
        read=120.0,    # время на чтение ответа
        write=60.0,    # время на отправку запроса
        pool=5.0       # время ожидания свободного соединения в пуле
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.ReadTimeout:
            raise HTTPException(504, detail="Upstream Read Timeout: модель не успела ответить за отведённое время")
        except httpx.RequestError as e:
            raise HTTPException(502, detail=f"Upstream Request Error: {e}")

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        raw_bytes = await resp.aread()
        media_type = resp.headers.get("content-type", "application/octet-stream")
        return Response(content=raw_bytes, media_type=media_type)


async def query_cerebras(request: LLMRequest):
    url = f"https://api.cerebras.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": request.model,
        "messages": [
            {"content": request.systemPrompt, "role": "system"},
            {"content": request.prompt, "role": "user"},
        ],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
