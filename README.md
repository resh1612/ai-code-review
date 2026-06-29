# AI Code Review

**Automated, multi-agent pull request reviews powered by LangGraph and Google Gemini — from webhook to GitHub comment in seconds.**

---

## How it works

When a pull request is opened or updated, the platform receives a signed GitHub webhook, queues an async review job, and orchestrates specialized AI agents in parallel. Findings are aggregated, posted back to the PR, and streamed live to the dashboard.

```
  GitHub PR (opened / synchronize)
           │
           ▼
  ┌────────────────────┐
  │  GitHub Webhook    │  HMAC-SHA256 verified
  └─────────┬──────────┘
            │
            ▼
  ┌────────────────────┐
  │      FastAPI       │  REST + WebSocket API
  └─────────┬──────────┘
            │
            ▼
  ┌────────────────────┐
  │      Celery        │  Background review tasks (Redis broker)
  └─────────┬──────────┘
            │
            ▼
  ┌────────────────────┐
  │     LangGraph      │  Planner → parallel agents → aggregator
  └─────────┬──────────┘
            │
     ┌──────┼──────┬──────────────┐
     ▼      ▼      ▼              │
 Code    Security  Test           │
 Quality  Agent   Agent           │
 Agent                           │
     └──────┬──────┴──────────────┘
            │
            ▼
  ┌────────────────────┐
  │  GitHub Comment    │  Markdown report on the PR
  └────────────────────┘
```

---

## Features

- **GitHub App integration** — Secure webhook handling with HMAC-SHA256 signature verification
- **Multi-agent analysis** — LangGraph orchestrates code quality, security, and test-coverage agents in parallel
- **Gemini-powered reviews** — LLM findings with structured JSON output, automatic retry on parse failures
- **Static security scanning** — Regex pre-checks for hardcoded secrets, SQL injection patterns, and `eval()` usage
- **AST-aware code quality** — tree-sitter function analysis flags complexity before LLM review
- **Live agent trace dashboard** — WebSocket streaming of agent status (`running` → `completed` / `failed`)
- **React dashboard** — Review list, detail view, findings table, and real-time trace timeline
- **Production-ready API** — Async SQLAlchemy + PostgreSQL, Alembic migrations, Docker Compose stack
- **CI/CD** — GitHub Actions pipeline with Postgres/Redis services, pytest, and Ruff linting

---

## Tech stack

| Category | Technology | Purpose |
|---|---|---|
| **API** | FastAPI | Webhook receiver, REST endpoints, WebSocket trace streaming |
| **Task queue** | Celery + Redis | Async review job processing |
| **Orchestration** | LangGraph | Multi-agent DAG with parallel fan-out / fan-in |
| **LLM** | Google Gemini (LangChain) | Code quality and security analysis |
| **Static analysis** | tree-sitter | Python AST extraction for complexity hints |
| **Database** | PostgreSQL + SQLAlchemy (async) | Review and findings persistence |
| **Migrations** | Alembic | Schema versioning |
| **GitHub** | PyGithub | App auth, PR comments, installation tokens |
| **Frontend** | React 19 + Vite + Tailwind CSS | Dashboard and live trace UI |
| **Data fetching** | TanStack Query + Axios | Cached API calls with auto-refresh |
| **Real-time** | WebSockets | Live agent trace updates |
| **Containerization** | Docker + Docker Compose | Local and production deployment |
| **CI** | GitHub Actions + pytest + Ruff | Automated test and lint on every PR |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- A [Google Gemini API key](https://ai.google.dev/)
- A [GitHub App](https://docs.github.com/en/apps/creating-github-apps) with webhook + PR permissions

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-code-review.git
cd ai-code-review
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_code_review
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your-gemini-api-key
GITHUB_APP_ID=your-app-id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

### 3. Start infrastructure

```bash
docker compose up -d postgres redis
```

### 4. Install backend dependencies and run migrations

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

Verify: [http://localhost:8000/health](http://localhost:8000/health) → `{"status":"ok"}`

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### 7. Run tests

```bash
pytest tests/ -v
```

### 8. Configure GitHub webhook

Point your GitHub App webhook to:

```
http://your-host/webhook
```

Events: **Pull requests** (`opened`, `synchronize`)

---

## Screenshots

> **Add your demo GIF here**

<!-- Replace with: ![Demo](./docs/demo.gif) -->

---

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository and create a feature branch (`git checkout -b feat/my-feature`)
2. **Install** dev dependencies and run tests locally (`pytest tests/ -v`)
3. **Lint** your changes (`pip install ruff && ruff check .`)
4. **Commit** with clear, descriptive messages
5. **Open a Pull Request** against `main` — CI will run tests and lint automatically

For larger changes, open an issue first to discuss the approach.

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
