## Project Gems
Full-stack LLM platform monorepository.

The repository includes:
 - **FastAPI backend** processes files and sends requests to LLM providers
 - **NestJS server** the main server of the application and the layer of work with the database. Responds to users, chats, messages, and model context formation
 - **Aiogram Telegram Bot**  for user interaction with the platform via Telegram

### Main functions

#### Multimodal input
The system accepts as input:

- text
- images
- audio
- files: txt, pdf, docx, html, xlsx and others

The files are processed by python service and placed in llm context

#### Shortcuts
This is a easy system for adding information to prompt by /command construct

The user can create their own shortcuts by asking:

- command
- prompt text
- preferred model for the request

#### Tools
The model can use tools based on need. Avaible tools:
- web search
- WolframAlpha search
- reading, adding, and deleting data from memory about user
- Python code execution

The tools are called by the model when necessary

#### System prompt
Each user can enter individual system prompt for model, or choose already prepared one

#### Text and image generation
The platform supports models for generating text and images

The type of model is determined through tags, which can also be used to identify a premium model or one with a reasoning function

#### Chats
Chats - give separate context for each conversation
The user can create new conversations, delete them, and switch between existing ones from Telegram bot buttons or commands

#### Reasoning display
For models with reasoning, the Telegram bot can display part of the reasoning chain when clicking on a special button

#### Subscriptions and quotas
The models are divided into free and premium models

Usage is calculated using quantitative query quotas. For example, a subscription can provide per day:

- 35 regular requests
- 4 premium requests

#### Multiple LLM providers
The platform supports working with several LLM providers at the same time:

1. Groq
2. Mistral
3. Hugging Face
4. Cloudflare
5. Cerebras

This allows to distribute requests between providers depending on the speed, and expand pool of models

#### Analytics and monitoring
For analytics, applications can be used integrated into each service:
 - Sentry
 - PostHog
