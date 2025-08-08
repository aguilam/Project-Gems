from fastapi import FastAPI, HTTPException, File, Request
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
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
import io
import json
from typing import Literal, List
import openai
from cerebras.cloud.sdk import Cerebras
from mem0 import AsyncMemoryClient
import contextvars

load_dotenv()

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "")

client = Cerebras(
    api_key=os.environ.get("CEREBRAS_API_KEY"),
)


mem_client = AsyncMemoryClient()


groqClient = Groq(
    api_key=GROQ_API_KEY,
)
providers = {
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": os.environ.get("CEREBRAS_API_KEY"),
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.environ.get("GROQ_API_KEY"),
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.environ.get("OPENROUTER_API_KEY"),
    },
}


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "function"]
    content: str


class LLMRequest(BaseModel):
    prompt: List[ChatMessage]
    model: str
    provider: list
    premium: bool
    is_agent: bool = False 


class OcrRequest(BaseModel):
    imageBase64: str


class FileRequest(BaseModel):
    buffer: str
    name: str
    mime: str

current_user_id = contextvars.ContextVar("current_user_id", default=None)

@app.middleware("http")
async def set_user_context(request: Request, call_next):
    uid = request.headers.get("X-User-Id")  
    token = current_user_id.set(uid)
    try:
        return await call_next(request)
    finally:
        current_user_id.reset(token)
@app.post("/llm")
async def llm_query(request: LLMRequest):
    prodiver = request.provider
    if "mistral" in prodiver:
        return await query_mistral(request)
    elif "cloudflare" in prodiver:
        return await query_cloudflare(request)
    else:
        return await providerRouting(request)


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
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

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


async def providerRouting(request: LLMRequest):
    provider = providers[request.provider[0]]
    openai_client = openai.OpenAI(
        base_url=provider["base_url"],
        api_key=provider["api_key"],
    )
    if(request.is_agent == True):
        full_messages = await tool_agent_call(request.prompt)
    else:
        full_messages = [m.dict() for m in request.prompt]
    completion = openai_client.chat.completions.create(
        model=request.model, messages=full_messages
    )
    return JSONResponse(
        content={
            "type": "text",
            "content": completion.choices[0].message.content,
        }
    )

async def add_memory(memory: str, user_id: str | None = None):
    uid = user_id or current_user_id.get()
    if not uid:
        raise HTTPException(status_code=401, detail="user_id is missing")
    message = {"role": "user", "content": memory}
    await mem_client.add(message, user_id=uid, async_mode=True)

async def search_memory(query: str, user_id: str | None = None):
    uid = user_id or current_user_id.get()
    if not uid:
        raise HTTPException(status_code=401, detail="user_id is missing")
    return await mem_client.search(query, user_id=uid)
tools = [
    {
        "type": "function",
        "function": {
            "name": "add_memory",
            "description": "Позволяет добавить воспоминание о пользователе",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory": {
                        "type": "string",
                        "description": "Строка с текстом которое сохраниться в воспоминание. Используй тогда тогда когда об этом попросит пользователь или очень потребуется, например очень важная деталь о пользователе",
                    }
                },
                "required": ["memory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Позволяет совершить поиск по воспоминаниям о пользователе. Используй тогда тогда когда об этом попросит пользователь или очень потребуется",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Строка с текстом по которому будет проведён поиск.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ocr_tool",
            "description": "Распознаёт изображение Base64 и возвращает текст",
            "parameters": {
                "type": "object",
                "properties": {"image_b64": {"type": "string"}},
                "required": ["image_b64"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "files_tool",
            "description": "Извлекает текст из файла (pdf, xlsx, прочие)",
            "parameters": {
                "type": "object",
                "properties": {
                    "buffer": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["buffer", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Даёт доступ к поиску в интернете",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Строка с поисковым запросом",
                    },
                    "freshness": {
                        "type": "string",
                        "enum": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                        "description": "Диапазон времени",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "science_search",
            "description": r"""
                Используй этот инструмент тогда когда тебе нужны тяжелые вычисления в математики, физике или  химии, или ответы на очень тяжелые вопросы из тех же сфер, вот памятка по работе.- WolframAlpha understands natural language queries about entities in chemistry, physics, geography, history, art, astronomy, and more.
                - WolframAlpha performs mathematical calculations, date and unit conversions, formula solving, etc.`
                - Convert inputs to simplified keyword queries whenever possible (e.g. convert "how many people live in France" to "France population").
                - Send queries in English only; translate non-English queries before sending, then respond in the original language.
                - Display image URLs with Markdown syntax: ![URL]
                - ALWAYS use this exponent notation: `6*10^14`, NEVER `6e14`.
                - ALWAYS use {"input": query} structure for queries to Wolfram endpoints; `query` must ONLY be a single-line string.
                - ALWAYS use proper Markdown formatting for all math, scientific, and chemical formulas, symbols, etc.:  '$$\n[expression]\n$$' for standalone cases and '\( [expression] \)' when inline.
                - Never mention your knowledge cutoff date; Wolfram may return more recent data.
                - Use ONLY single-letter variable names, with or without integer subscript (e.g., n, n1, n_1).
                - Use named physical constants (e.g., 'speed of light') without numerical substitution.
                - Include a space between compound units (e.g., "Ω m" for "ohm*meter").
                - To solve for a variable in an equation with units, consider solving a corresponding equation without units; exclude counting units (e.g., books), include genuine units (e.g., kg).
                - If data for multiple properties is needed, make separate calls for each property.
                - If a WolframAlpha result is not relevant to the query:
                -- If Wolfram provides multiple 'Assumptions' for a query, choose the more relevant one(s) without explaining the initial result. If you are unsure, ask the user to choose.
                -- Re-send the exact same 'input' with NO modifications, and add the 'assumption' parameter, formatted as a list, with the relevant values.
                -- ONLY simplify or rephrase the initial query if a more relevant 'Assumption' or other input suggestions are not provided.
                -- Do not explain each step unless user input is needed. Proceed directly to making a better API call based on the available assumptions.
                """,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Строка с запросом для api",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


async def web_search(query: str, freshness: str = "noLimit"):
    url = "https://api.langsearch.com/v1/web-search"

    payload = json.dumps(
        {"query": query, "freshness": freshness, "summary": True, "count": 10}
    )
    headers = {
        "Authorization": "Bearer sk-0ac743b6fb314baeab92b68c31f01d40",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()["data"]


async def science_search(query: str):
    url = f"https://api.wolframalpha.com/v2/query?appid=TV3TVAVWAR&input={query}&output=JSON"
    timeout = httpx.Timeout(connect=60.0, read=120.0, write=60.0, pool=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        text = resp.text
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=text)
        try:
            return resp.json()
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail=f"Invalid JSON from Wolfram: {text[:200]}..."
            )

available_functions = {
    "ocr_tool": ocr_query,
    "files_tool": files_recognize,
    "web_search": web_search,
    "science_search": science_search,
    "add_memory": add_memory,
    "search_memory": search_memory,
}


async def tool_agent_call(start_messages: ChatMessage):
    messages: List[dict] = [m.dict() for m in start_messages]

    while True:
        resp = client.chat.completions.create(
            model="qwen-3-32b",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            print("Assistant:", msg.content)
            break

        messages.append(msg.model_dump())

        call = msg.tool_calls[0]
        fname = call.function.name

        if fname not in available_functions:
            raise ValueError(f"Unknown tool requested: {fname!r}")

        args_dict = json.loads(call.function.arguments)
        output = await available_functions[fname](**args_dict)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "name": fname,
                "content": json.dumps(output),
            }
        )
    return messages
