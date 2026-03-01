# Chef AI — LLM-Powered Cooking & Recipe Q&A

A full-stack AI cooking assistant built with **FastAPI + LangGraph** (backend) and **Next.js 16** (frontend). Ask it about recipes, cooking techniques, or ingredients — it'll research, check your available cookware, and give you a tailored response.

## Architecture

```
User ──► Next.js Chat UI ──► FastAPI ──► LangGraph Pipeline ──► GPT-4o-mini
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                        classify_query   research_agent   cookware_check
                              │               │               │
                              ▼               ▼               ▼
                        refuse_response  (web search)   generate_response
```

**LangGraph Flow (5 nodes):**
1. **classify_query** — Determines if the query is cooking-related (structured output, temp=0.0)
2. **research_agent** — Researches the query, optionally using web search (Tavily/DuckDuckGo)
3. **cookware_check** — Validates the recipe against the user's available cookware
4. **generate_response** — Synthesizes a final, formatted response
5. **refuse_response** — Polite refusal for off-topic queries (deterministic, no LLM call)

---

## Local Setup (Development)

### Prerequisites
- Python 3.12+
- Node.js 20+
- [bun](https://bun.sh) (or pnpm as alternative)
- OpenAI API key

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your OPENAI_API_KEY (required) and TAVILY_API_KEY (optional)

# Run
uvicorn main:app --reload --reload-exclude venv
```

Server runs at http://localhost:8000

### Frontend

```bash
cd frontend
bun install          # or: pnpm install
cp .env.example .env.local

bun run dev          # or: pnpm dev
```

App runs at http://localhost:3000

---

## Docker Setup

```bash
# Create backend/.env with your API keys first
docker-compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

---

## API Examples

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Cooking Query (sync)
```bash
curl -X POST http://localhost:8000/api/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "How do I make scrambled eggs?"}]}'
```

### Off-Topic Query (should be refused)
```bash
curl -X POST http://localhost:8000/api/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the capital of France?"}]}'
```

### With Debug Info
```bash
curl -X POST http://localhost:8000/api/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "How do I make pasta?"}], "debug": true}'
```

### Streaming (SSE)
```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "How do I make pasta?"}]}'
```

### Multi-turn Conversation
```bash
curl -X POST http://localhost:8000/api/chat/sync \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "How do I make scrambled eggs?"},
      {"role": "assistant", "content": "Here is a recipe for scrambled eggs..."},
      {"role": "user", "content": "Can I add cheese to that?"}
    ]
  }'
```

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for GPT-4o-mini |
| `TAVILY_API_KEY` | No | — | Tavily search API key (falls back to DuckDuckGo) |
| `MODEL_NAME` | No | `gpt-4o-mini` | LLM model name |
| `LOG_LEVEL` | No | `INFO` | Python logging level |

### Frontend (`frontend/.env.local`)
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Backend API URL |

---

## Hardcoded Cookware List

The system validates recipes against this cookware:
- Spatula, Frying Pan, Little Pot, Stovetop, Whisk, Knife, Ladle, Spoon

The LLM-based cookware check handles synonyms (e.g., "skillet" = "frying pan") and suggests substitutions when possible.

---

## Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| LLM Model | `gpt-4o-mini` | Fast, cheap, sufficient for cooking Q&A |
| Multi-node graph vs ReAct agent | 5 separate nodes | Visibility into each step, testability, meets spec requirement for node-based flow |
| Frontend SSE approach | Raw `fetch` + `ReadableStream` | Fewer dependencies, demonstrates understanding of streaming pattern. Aware of `@langchain/langgraph-sdk` and CopilotKit but chose simplicity |
| State management | Stateless backend (frontend sends full history) | Simpler, more scalable, no DB needed |
| Search tool | Tavily (primary) + DuckDuckGo (fallback) | Tavily has first-class LangChain integration; DDG needs no API key |
| `refuse_response` | Deterministic (no LLM call) | Saves latency and API cost; behavior is predictable |
| Separate `generate_response` node | Distinct from `research_agent` | Clean separation of concerns, spec compliance |
| Package manager | bun | Spec recommends it; fast install and dev server |

---

## AWS Deployment Plan

### Compute: ECS Fargate
- **Why Fargate over Lambda**: Persistent connections needed for SSE streaming; Lambda's timeout is too short for long-running recipe generation.
- **Why not EKS**: Overkill for two services. ECS is simpler to manage and sufficient at this scale.
- Both services run as ECS services behind an ALB.

### Architecture
```
Internet ──► ALB (path-based routing)
                ├── /api/* ──► ECS Backend Service (Fargate)
                └── /* ──► ECS Frontend Service (Fargate)
```

### Secret Management
- **AWS Secrets Manager** for API keys (OPENAI_API_KEY, TAVILY_API_KEY)
- Referenced as ECS task definition secrets — injected as env vars at runtime
- Rotation policies configured for key cycling

### Networking
- VPC with public and private subnets
- ALB in public subnet, ECS tasks in private subnet
- Security groups restrict backend to ALB-only traffic

### Scaling
- ECS auto-scaling on CPU/memory metrics (target tracking policy)
- ALB distributes traffic across task replicas
- Min 1, max 10 tasks per service

### Observability
- **CloudWatch Logs** with structured JSON logging (production improvement over current plain-text)
- **CloudWatch Container Insights** for CPU/memory/network metrics
- **AWS X-Ray** for distributed tracing across frontend → backend → LLM calls
- Alarms on error rate, latency P99, and LLM API failures

---

## Auth & Security Plan

### API Authentication
- **JWT tokens** via Auth0 or AWS Cognito
- FastAPI middleware validates JWT on every request
- Tokens include user ID, expiry, and rate limit tier

### CORS
- Production: Restrict to known frontend origin only (e.g., `https://chef-ai.example.com`)
- No wildcard origins

### Rate Limiting
- **Token bucket per user** via Redis (or API Gateway throttling)
- Separate limits for streaming vs sync endpoints
- Anonymous users get lower limits

### Input Validation
- Pydantic models validate all request bodies
- Max message length limit (e.g., 10,000 chars)
- Max conversation history length (e.g., 50 messages)

### Prompt Injection Mitigation
- Classification node acts as first line of defense (off-topic queries refused)
- System prompts instruct model to stay in cooking domain
- Production: Add dedicated guardrail layer (e.g., Anthropic's constitutional AI or custom classifier)

### Key Security
- API keys in environment variables, never in code
- Secrets Manager with automatic rotation
- Backend-only access to LLM keys (frontend never sees them)

---

## ELT Integration Plan (Bonus)

### Goal
Track which recipes users are making to give stakeholders a dashboard of cooking trends.

### Extract
- When users confirm a recipe (e.g., "I'll make this!"), log a structured event to **Amazon SQS** (or Kafka for higher throughput):
  ```json
  {
    "user_id": "abc123",
    "recipe_name": "Scrambled Eggs",
    "cuisine": "American",
    "cookware_used": ["Frying Pan", "Spatula"],
    "timestamp": "2024-01-15T10:30:00Z"
  }
  ```

### Load
- SQS → **AWS Lambda** consumer → **Amazon Redshift** (or Snowflake/BigQuery)
- Raw events land in a `raw_recipe_events` table
- Alternatively: Firehose → S3 → Redshift Spectrum for cost-effective querying

### Transform
- **dbt** models to aggregate:
  - Recipes by cuisine type (daily/weekly)
  - Most popular ingredients
  - Cookware usage frequency
  - Time-of-day cooking patterns
  - Recipe complexity distribution

### Serve
- **Metabase** or **Looker** dashboard connected to Redshift
- Key metrics: top 10 recipes this week, ingredient trends, cookware gaps
- Stakeholders get a "What are people cooking?" view at a glance

---

## Edge Cases & Future Work

| Edge Case | Current Behavior | Future Fix |
|-----------|-----------------|------------|
| Multi-step recipes with unavailable cookware | Suggests substitutions via LLM | Could break recipe into sub-steps and flag each |
| Ambiguous ingredient names ("tomato sauce" vs "strained tomatoes") | LLM handles with best guess | Ask clarifying questions before proceeding |
| Non-English queries | LLM handles common languages reasonably | Detect language, add unit conversion (metric/imperial) |
| Long conversations hitting context limits | Sends full history each request | Implement conversation summarization or sliding window |
| Tool failures (search outages) | Logs error, continues without search results | Retry with exponential backoff, circuit breaker pattern |
| Prompt injection attempts | Classification node filters off-topic | Dedicated guardrail layer, input sanitization |
| Specialized techniques (sous vide, fermentation) | Handled by LLM knowledge + search | Flag as advanced, note specialized equipment needs |
| Concurrent requests | Stateless, each request independent | Add rate limiting, request queuing |

---

## Project Structure

```
.
├── backend/
│   ├── main.py                 # FastAPI entry point, CORS, routes
│   ├── config.py               # Env vars, cookware list, model config
│   ├── graphs/
│   │   └── cooking_graph.py    # LangGraph definition and wiring
│   ├── nodes/
│   │   ├── classify.py         # Query classification (structured output)
│   │   ├── research.py         # Research agent with tool binding
│   │   ├── cookware.py         # Cookware feasibility check
│   │   ├── generate.py         # Final response synthesis
│   │   └── refuse.py           # Off-topic refusal (deterministic)
│   ├── tools/
│   │   └── search.py           # Tavily/DuckDuckGo search tool
│   ├── prompts/                # Versioned prompt templates
│   ├── schemas/                # Pydantic request/response/state models
│   ├── requirements.txt
│   ├── Dockerfile
│   └── ruff.toml
├── frontend/
│   ├── app/                    # Next.js App Router pages
│   ├── components/chat/        # Chat UI components
│   ├── hooks/useChat.ts        # Custom hook with useReducer
│   ├── lib/
│   │   ├── api.ts              # Fetch functions (sync + streaming)
│   │   └── types.ts            # Zod schemas + TypeScript types
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── Makefile
├── DESIGN_DECISIONS.md
├── SPEC.md
└── README.md
```

---

## AI Tooling Used

- **Claude Code (Opus 4.6)** — Used for scaffolding, implementation, and documentation. All code was generated with AI assistance and reviewed for correctness.
- **GPT-4o-mini** — Runtime LLM for the cooking assistant (classification, research, cookware check, response generation).
- **Tavily** — Web search tool integrated via LangChain for recipe research.

---

## Timeboxing Notes

Built in phases:
1. **Backend scaffolding** — Config, schemas, prompts, bare FastAPI server
2. **LangGraph core** — All 5 nodes, graph wiring, sync + streaming endpoints
3. **Frontend** — Next.js 16 with shadcn/ui chat interface, SSE streaming
4. **Docker + docs** — Dockerfiles, docker-compose, this README

### Trade-offs Made
- **No unit tests** — Prioritized working E2E over test coverage. Would add pytest for graph nodes and Jest for frontend hooks.
- **No CI/CD pipeline** — Would add GitHub Actions with lint, test, build stages.
- **Plain-text logging** — Production would use structured JSON logging with request IDs.
- **No conversation persistence** — Stateless by design; would add Redis or PostgreSQL for production.
