# FastAPI LLM Backend

## Описание

Этот сервис предоставляет единый API для отправки запросов к различным LLM-провайдерам: Groq, Mistral, Hugging Face, OpenRouter.

## Установка

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Создайте файл `.env` и добавьте ваши API-ключи:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   MISTRAL_API_KEY=your_mistral_api_key_here
   HUGGINGFACE_API_KEY=your_huggingface_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

## Запуск

```bash
uvicorn main:app --reload
```

## Пример запроса

POST `/llm/`
```json
{
  "prompt": "Привет, расскажи анекдот!",
  "provider": "groq",
  "model": "llama2-70b-4096"
}
```

Провайдеры: `groq`, `mistral`, `huggingface`, `openrouter` 