from fastapi import FastAPI, HTTPException, File
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
from groq import Groq
from fastapi.responses import JSONResponse
import base64
import textract
import tempfile
from io import BytesIO
from openpyxl import load_workbook
from pdfminer.pdfpage import PDFPage
from pdfminer.high_level import extract_text_to_fp
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
import io
import json
from typing import Literal, List

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

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class LLMRequest(BaseModel):
    prompt: List[ChatMessage]
    model: str
    provider: list
    premium: bool
    systemPrompt: str


class OcrRequest(BaseModel):
    imageBase64: str


class FileRequest(BaseModel):
    buffer: str
    name: str
    mime: str


@app.post("/llm")
async def llm_query(request: LLMRequest):
    prodiver = request.provider
    if "cerebras" in prodiver and request.premium == True:
        return await query_cerebras(request)
    elif "groq" in prodiver:
        return await query_groq(request)
    elif "mistral" in prodiver:
        return await query_mistral(request)
    elif "openrouter" in prodiver:
        return await query_openrouter(request)
    elif "cloudflare" in prodiver:
        return await query_cloudflare(request)


@app.post("/ocr")
async def ocr_query(req: OcrRequest):
    imageBase64 = req.imageBase64
    chat_completion = groqClient.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Что на этом изображении? Опиши подробно"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{imageBase64}",
                        },
                    },
                ],
            }
        ],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
    )
    return chat_completion.choices[0].message.content


@app.post("/files")
async def files_recognize(req: FileRequest):
    data = base64.b64decode(req.buffer)
    mediaType = ""
    ext = req.name.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        rsrcmgr = PDFResourceManager()
        laparams = LAParams()
        retstr = io.StringIO()
        device = TextConverter(rsrcmgr, retstr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        fp = BytesIO(data)
        fp.seek(0)

        total_text = ""
        mediaType = "pdf"
        for page in PDFPage.get_pages(fp, check_extractable=False):
            interpreter.process_page(page)
            page_text = retstr.getvalue()
            retstr.truncate(0)
            retstr.seek(0)

            remaining = 3000 - len(total_text)
            total_text += page_text[:remaining]
            if len(total_text) >= 3000:
                break

            device.close()
            retstr.close()
            fp.close()
            return total_text
    elif ext in ("xls", "xlsx"):
        wb = load_workbook(filename=BytesIO(data), read_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"=== Sheet: {ws.title} ===")
            for row in ws.iter_rows(values_only=True):
                line = "\t".join("" if c is None else str(c) for c in row)
                parts.append(line)
        text = "\n".join(parts)
        mediaType = "table"
    elif ext in ("mp3", "wav", "ogg", "m4a"):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as f:
                result = groqClient.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio." + ext, f.read(), f"audio/{ext}"),
                    response_format="text",
                    prompt="Дословно напиши, точную расшифровку текста на том языке на котором аудио записано, и ничего не более, если ты не нашёл слов в аудио файле, то опиши  что за звуки там.",
                )
            mediaType = "audio"
            text = json.dumps(result, indent=2, ensure_ascii=False)
        except Exception(e):
            raise HTTPException(status_code=500, detail=e)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    else:
        ext = req.name.rsplit(".", 1)[-1].lower()
        suffix = f".{ext}" if ext else ""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            raw = textract.process(tmp_path)
            text = raw.decode("utf-8", errors="ignore")

        except Exception as e:
            return {"error": "Processing failed", "detail": str(e)}

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    return {"text": text, "type": mediaType}


async def query_groq(request: LLMRequest):
    chat_completion = groqClient.chat.completions.create(
        messages=[
            {"content": request.systemPrompt, "role": "system"},
            {"content": request.prompt, "role": "user"},
        ],
        model=request.model,
    )
    return JSONResponse(
        content={
            "type": "text",
            "content": chat_completion.choices[0].message.content,
        }
    )


async def query_mistral(request: LLMRequest):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    payload = {
        "model": request.model,
        "messages": [m.dict() for m in request.prompt],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        return JSONResponse(
            content={
                "type": "text",
                "content": data["choices"][0]["message"]["content"],
            }
        )


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
        "messages": [
            {"content": request.systemPrompt, "role": "system"},
            {"content": request.prompt, "role": "user"},
        ],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        response = resp.json()
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        JSONResponse(
            content={
                "type": "text",
                "content": response["choices"][0]["message"]["content"],
            }
        )


async def query_cloudflare(request: LLMRequest):
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"5054130e5a7ddf582ed30bdae4809a82/ai/run/@{request.model}"
    )
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_KEY}"}
    payload = {"prompt": request.prompt}

    timeout = httpx.Timeout(
        connect=60.0,
        read=120.0,
        write=60.0,
        pool=5.0,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.ReadTimeout:
            raise HTTPException(
                504,
                detail="Upstream Read Timeout: модель не успела ответить за отведённое время",
            )
        except httpx.RequestError as e:
            raise HTTPException(502, detail=f"Upstream Request Error: {e}")

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        raw_bytes = await resp.aread()

        encoded = base64.b64encode(raw_bytes).decode("ascii")
        return JSONResponse(content={"type": "image", "content": encoded})


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
        response = resp.json()
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return JSONResponse(
            content={
                "type": "text",
                "content": response["choices"][0]["message"]["content"],
            }
        )
