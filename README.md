# SocraticAI 🧠

> **Bilingual (EN/VI) AI-powered debate training platform.**
> Train critical thinking by sparring with an AI opponent using the Socratic method and Steelmanning technique.

---

## Features

| Feature | Tech |
|---|---|
| Real-time streaming debate | WebSocket + LangGraph streaming |
| Logical fallacy detection | Configured complex AI model |
| Long-session claim memory | Qdrant vector search |
| Post-session rubric grading | Configured complex AI model |
| Bilingual (EN + VI) | `paraphrase-multilingual-mpnet-base-v2` |
| Session state & checkpointing | Redis + LangGraph checkpointer |
| Practice history & weekly score trend | Browser-local session index + Redis (90-day retention) |

---

## Tech Stack

```
frontend/   Next.js 15 (App Router) · TypeScript · Tailwind CSS · Framer Motion · shadcn/ui
backend/    Python 3.12 · FastAPI · LangGraph · OpenAI / Gemini APIs · uv
infra/      Qdrant (Docker) · Redis (Docker) · docker-compose
```

---

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose v2
- Node.js 22+ (for local frontend dev)
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) (for local backend dev)

### 2. Clone & configure

```bash
git clone <repo-url>
cd socratic-ai

cp .env.example .env
# Edit .env and set OPENAI_API_KEY=<your-openai-api-key>
# Keep the key in .env; never put it in a Dockerfile or commit it.
```

### 3. Start infrastructure (Qdrant + Redis)

```bash
docker compose up qdrant redis -d
```

### 4. Start the backend (local, hot-reload)

```bash
cd backend
uv sync                          # installs all deps into .venv
uv run uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 5. Start the frontend (local, Turbopack)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 6. Or run everything with Docker Compose

```bash
docker compose up --build
```

---

## Project Structure

```
socratic-ai/
├── frontend/
│   ├── app/
│   │   ├── layout.tsx               # Root layout, fonts, metadata
│   │   ├── page.tsx                 # Landing page
│   │   ├── globals.css              # Tailwind + shadcn/ui tokens
│   │   └── debate/[sessionId]/
│   │       └── page.tsx             # Live debate arena page
│   ├── components/
│   │   ├── debate/
│   │   │   └── DebateArena.tsx      # Main streaming debate UI
│   │   └── ui/                      # shadcn/ui components (add via CLI)
│   ├── lib/
│   │   ├── api.ts                   # Typed REST client
│   │   └── websocket.ts             # Typed WebSocket client
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── tsconfig.json
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory + lifespan
│   │   ├── config.py                # pydantic-settings + AI provider selection
│   │   ├── models/
│   │   │   ├── session.py           # Session domain models
│   │   │   └── debate.py            # Turn, fallacy, WS message models
│   │   ├── graph/
│   │   │   ├── state.py             # LangGraph DebateState schema
│   │   │   ├── nodes.py             # retrieve_memory, detect_fallacies, etc.
│   │   │   └── graph.py             # Graph assembly + compilation
│   │   ├── services/
│   │   │   ├── debate_service.py    # Orchestrates one debate turn
│   │   │   └── session_service.py  # Session lifecycle (create/get/end)
│   │   ├── repositories/
│   │   │   ├── vector_store.py      # Qdrant async wrapper
│   │   │   └── session_store.py     # Redis session cache
│   │   ├── routers/
│   │   │   ├── sessions.py          # REST: /session/*
│   │   │   └── debate_ws.py         # WS: /ws/debate/{session_id}
│   │   ├── prompts/
│   │   │   ├── debate.py            # Bilingual Socratic prompts
│   │   │   └── fallacy.py           # Fallacy detection prompts (→ JSON)
│   │   └── utils/
│   │       ├── logging.py           # structlog helpers
│   │       └── embeddings.py        # sentence-transformers wrapper
│   ├── tests/
│   │   ├── conftest.py              # Fixtures, async test client
│   │   └── test_health.py           # Smoke tests
│   ├── pyproject.toml               # uv project config
│   ├── .python-version              # 3.12
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Reference

The `/history` page shows sessions recorded in the current browser and their weekly
rubric-score trend. Session IDs stay in browser storage; full session data remains in
Redis for 90 days by default (`REDIS_SESSION_TTL_SECONDS` can override this value).
There is no account-based cross-device history.

### REST

| Method | Path | Description |
|---|---|---|
| `POST` | `/session/create` | Create a new debate session |
| `GET` | `/session/{id}` | Get session metadata |
| `POST` | `/session/history` | Load compact summaries for browser-recorded session IDs |
| `POST` | `/session/{id}/end` | End session + trigger grading |
| `GET` | `/health` | Liveness probe |

### WebSocket

**Connect:** `ws://localhost:8000/ws/debate/{session_id}`

**Client → Server:**
```json
{ "type": "user_turn", "session_id": "...", "payload": { "content": "...", "language": "en" } }
{ "type": "ping",      "session_id": "...", "payload": {} }
```

**Server → Client:**
```json
{ "type": "ai_turn_chunk",    "payload": { "chunk": "...", "turn_id": 0 } }
{ "type": "ai_turn_done",     "payload": { "turn": { ... } } }
{ "type": "fallacy_detected", "payload": { "turn_id": 0, "fallacies": [...] } }
{ "type": "session_ended",    "payload": { "reason": "max_turns_reached" } }
{ "type": "error",            "payload": { "error": "..." } }
{ "type": "pong",             "payload": {} }
```

---

## AI Provider & Model Usage

| Task | OpenAI default | Gemini override |
|---|---|---|
| Debate responses, memory extraction | `OPENAI_FAST_MODEL` (`gpt-4.1-mini`) | `GEMINI_FAST_MODEL` |
| Fallacy detection, session grading | `OPENAI_COMPLEX_MODEL` (`gpt-4.1`) | `GEMINI_COMPLEX_MODEL` |

Configure with `AI_PROVIDER=openai` and `OPENAI_API_KEY`. Set
`AI_PROVIDER=gemini` and `GOOGLE_API_KEY` to use Gemini instead. API keys are read
only by the backend from environment variables / `.env`; never add them to the
Dockerfile, frontend environment, or source control. Docker Compose passes `.env`
only to the backend service.

---

## Development

### Backend linting & type checking

```bash
cd backend
uv run ruff check app/        # lint
uv run ruff format app/       # format
uv run mypy app/              # type check
uv run pytest                 # tests
```

### Add shadcn/ui components

```bash
cd frontend
npx shadcn@latest init        # first time only — generates components.json
npx shadcn@latest add button dialog scroll-area select toast tooltip
```

### Generate uv lockfile

```bash
cd backend
uv lock                        # generates/updates uv.lock — commit this file
```

---

## Demo Sharing (ngrok / Cloudflare Tunnel)

```bash
# ngrok
ngrok http 3000

# Cloudflare Tunnel (requires cloudflared installed)
cloudflared tunnel --url http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` to your tunnel URL before sharing.

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Required:

| Variable | Description |
|---|---|
| `AI_PROVIDER` | `openai` or `gemini` (auto-selects OpenAI when its key is available if omitted) |
| `OPENAI_API_KEY` | OpenAI API key; keep it server-side in `.env` or a secrets manager |
| `OPENAI_FAST_MODEL` | OpenAI model for debate responses and claim extraction |
| `OPENAI_COMPLEX_MODEL` | OpenAI model for fallacy detection and grading |
| `GOOGLE_API_KEY` | Optional Google AI Studio key when using `AI_PROVIDER=gemini` |
| `QDRANT_URL` | Qdrant REST endpoint (default: `http://localhost:6333`) |
| `REDIS_URL` | Redis URL (default: `redis://localhost:6379`) |
| `NEXT_PUBLIC_API_URL` | Backend URL visible to the browser |

---

## Roadmap

- [ ] Wire Qdrant + Redis in LangGraph nodes (Phase 2)
- [ ] Streaming token delivery via `astream_events`
- [ ] Vietnamese UI copy & language toggle
- [ ] Grade report UI with animated score cards
- [ ] Shareable session replay links
- [ ] PWA support for mobile debate practice

---

## License

MIT — see `LICENSE`.
