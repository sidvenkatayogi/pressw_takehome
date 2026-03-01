# Design Decisions — LLM-Powered Cooking & Recipe Q&A Application

> **Purpose**: This document contains all finalized design decisions for the intern technical assessment. Use it as the authoritative reference when implementing. Do not deviate from these decisions without explicit instruction.

---

## Project Overview

Building a monorepo containing:
- **Backend**: Python FastAPI + LangChain + LangGraph — an AI-powered cooking chatbot
- **Frontend**: Next.js 16+ (App Router) + TypeScript + Tailwind CSS + shadcn/ui — a chat interface

**Hard constraints from the spec:**
- All LLM calls must go through LangChain (no direct OpenAI SDK usage)
- LangGraph must be used for the agent flow
- FastAPI for the API layer
- Streaming responses to the frontend
- Hardcoded cookware list for validation
- 3-hour timebox

---

## 1. LLM & Model Configuration

### Model
- **Primary model**: `gpt-5-mini` via LangChain's `ChatOpenAI`
- **Reason**: Fast, cheap, sufficient quality for cooking Q&A. Keeps streaming latency low during development.
- **Configuration**: Model name set via `MODEL_NAME` env var (default `gpt-5-mini`) so it's swappable without code changes.
- **Temperature**: 0.7 for recipe generation (creative), 0.0 for classification (deterministic).

### LangChain Integration
- Use `langchain-openai` package for `ChatOpenAI`
- Use `langgraph` package for the graph
- Use `langchain-community` for tool integrations
- **Never import `openai` directly** — all LLM calls through LangChain abstractions

---

## 2. LangGraph Architecture

### Graph Topology

```
START
  │
  ▼
classify_query ──(off-topic)──► refuse_response ──► END
  │
  (cooking-related)
  │
  ▼
research_agent ──(tools: web search)
  │
  ▼
cookware_check
  │
  ▼
generate_response ──► END
```

### Node Specifications

#### Node: `classify_query`
- **Purpose**: Determine if the user's query is cooking/recipe related or off-topic.
- **Implementation**: Single LLM call with structured output.
- **Output schema**:
  ```python
  class ClassificationResult(BaseModel):
      is_cooking_related: bool
      category: str  # "general_cooking", "recipe_request", "ingredient_query", "off_topic"
      reasoning: str  # Brief explanation for debug logging
  ```
- **Prompt**: Focused system prompt that classifies queries. Temperature 0.0 for determinism.
- **Edge logic**: Deterministic branch — if `is_cooking_related` is False, route to `refuse_response`. Otherwise route to `research_agent`.

#### Node: `research_agent`
- **Purpose**: Answer the cooking query, optionally using web search if the LLM decides it needs external info.
- **Implementation**: LLM with bound tools. The LLM decides whether to call tools or answer directly. This is the ONLY node with tool access.
- **Tools available**: `TavilySearchResults` (or `DuckDuckGoSearchRun` as fallback)
- **Behavior**: This node may loop (call tool → get result → decide if more info needed → call again or proceed). Use LangGraph's built-in tool node pattern for this.
- **Output**: The cooking answer/recipe content, plus metadata about which tools were invoked.

#### Node: `cookware_check`
- **Purpose**: Validate whether the user can actually cook the suggested recipe with the hardcoded cookware list.
- **Implementation**: LLM call that receives the recipe from the previous node and the cookware list, then reasons about feasibility.
- **Cookware list** (hardcoded constant):
  ```python
  AVAILABLE_COOKWARE = [
      "Spatula", "Frying Pan", "Little Pot", "Stovetop",
      "Whisk", "Knife", "Ladle", "Spoon"
  ]
  ```
- **Output**: Whether cookware is sufficient, what's missing (if anything), and suggested substitutions.
- **Why LLM-based, not keyword matching**: Handles synonyms ("skillet" = "frying pan"), implicit requirements, and can suggest workarounds (e.g., "you don't have a baking sheet, but you could use your frying pan for this").

#### Node: `generate_response`
- **Purpose**: Compose the final user-facing response from the research and cookware check results.
- **Implementation**: LLM call that synthesizes everything into a clean, formatted answer.
- **IMPORTANT**: This MUST be a distinct node in the graph, not the tail end of `research_agent`. The spec rewards visible node-based flow design.
- **Output**: Final formatted response with recipe steps, tips, cookware notes, and any caveats.

#### Node: `refuse_response`
- **Purpose**: Generate a brief, polite refusal for off-topic queries.
- **Implementation**: Can be a simple LLM call or even a deterministic template. Keep it short.
- **Output**: A friendly message like "I'm a cooking assistant and can only help with food-related questions. Try asking me about recipes, cooking techniques, or ingredients!"

### Graph State Schema
```python
class GraphState(TypedDict):
    messages: list  # Full conversation history
    classification: ClassificationResult | None
    research_result: str | None
    tools_used: list[str]
    cookware_check_result: CookwareCheckResult | None
    final_response: str | None
    debug_info: list[str]  # Log of node transitions and decisions
```

### Edge Definitions
- `START → classify_query`: Always (entry point)
- `classify_query → refuse_response`: Conditional — when `is_cooking_related == False`
- `classify_query → research_agent`: Conditional — when `is_cooking_related == True`
- `research_agent → cookware_check`: Always (after research completes)
- `cookware_check → generate_response`: Always
- `generate_response → END`: Always
- `refuse_response → END`: Always

---

## 3. Tools

### Web Search Tool
- **Primary**: `TavilySearchResults` from `langchain-community`
  - Requires `TAVILY_API_KEY` env var
  - First-class LangChain integration, minimal setup
  - Free tier available
- **Fallback**: `DuckDuckGoSearchRun` (zero-config, no API key needed)
  - Use this if Tavily key is not provided
  - Document in README that Tavily is preferred for production
- **Tool binding**: Only bound to the `research_agent` node. No other node gets tool access.

### Cookware Checker
- This is NOT a LangGraph tool — it's a dedicated graph node that uses an LLM call internally.
- The cookware list is injected into the prompt as a constant.

---

## 4. Backend — FastAPI

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | Main streaming endpoint (SSE) |
| `POST` | `/api/chat/sync` | Non-streaming endpoint (for curl testing) |
| `GET` | `/api/health` | Health check |

### Request Schema
```python
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    debug: bool = False  # When true, include reasoning chain in response
```

### Response Schema (sync endpoint)
```python
class ChatResponse(BaseModel):
    answer: str
    query_type: str  # "general_cooking", "recipe_request", "ingredient_query", "off_topic"
    tools_used: list[str] = []
    cookware_sufficient: bool | None = None
    missing_cookware: list[str] = []
    debug: DebugInfo | None = None  # Only populated when debug=True

class DebugInfo(BaseModel):
    classification_reasoning: str
    nodes_visited: list[str]
    tool_calls: list[dict]
    cookware_analysis: str | None = None
```

### Streaming (SSE endpoint)
- Use FastAPI's `StreamingResponse` with `media_type="text/event-stream"`
- Use LangGraph's `.astream_events()` to get events as graph executes
- Emit structured SSE events:
  ```
  data: {"type": "node_start", "node": "classify_query"}
  data: {"type": "node_end", "node": "classify_query", "result": "cooking_related"}
  data: {"type": "token", "content": "Here's a great recipe..."}
  data: {"type": "tool_call", "tool": "tavily_search", "query": "..."}
  data: {"type": "done", "metadata": {...}}
  ```
- This naturally satisfies the "view reasoning chain" requirement.

### State Management
- **Stateless backend**. The frontend sends the full message history with each request.
- No session storage, no database.
- Reason: Simpler, more scalable, and appropriate for the scope.

### Error Handling
- Try/except at each graph node. If a tool fails, continue without tool results rather than crashing.
- If LLM times out, return a friendly error message.
- Log actual errors server-side with full context.
- Don't build retry logic — document it as a future improvement.

### Logging
- Use Python's `logging` module with a custom format: `[{timestamp}] [{request_id}] [{node_name}] {message}`
- Log at each node entry/exit, tool invocations, and errors.
- No structured JSON logging — document that as a production improvement.

### CORS
- Enable CORS for `http://localhost:3000` (frontend dev server) in development.
- Use `CORSMiddleware` from FastAPI.

### Code Formatting
- **Use Ruff** for formatting and linting. Set it up early in the project.
- Add `ruff.toml` or `[tool.ruff]` in `pyproject.toml`.
- Configure: line length 88, Python 3.12 target.

---

## 5. Frontend — Next.js

### Stack
- Next.js 16+ with App Router
- TypeScript in strict mode
- Tailwind CSS for styling
- shadcn/ui components: `Button`, `Input`, `Card`, `ScrollArea`

### Architecture Decision: Raw fetch + SSE over libraries
- **NOT using** `@langchain/langgraph-sdk` or AG-UI/CopilotKit
- **Using** raw `fetch` with `ReadableStream` for SSE consumption
- **Reason**: Fewer dependencies, demonstrates understanding of the streaming pattern, simpler to debug. Document this choice in README and mention awareness of those libraries.

### Implementation Strategy (IMPORTANT — read this)
1. **Build sync endpoint integration FIRST**. Get the full E2E working with the non-streaming `/api/chat/sync` endpoint.
2. **Layer streaming on top**. Once sync works, switch the frontend to use `/api/chat` SSE endpoint.
3. This is the fallback strategy if streaming SSE parsing hits snags within the timebox.

### Component Structure
```
frontend/
├── app/
│   ├── layout.tsx          # Root layout with fonts/metadata
│   ├── page.tsx            # Main page, renders ChatContainer
│   └── globals.css         # Tailwind imports
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx    # Main wrapper, uses useChat hook
│   │   ├── MessageBubble.tsx    # Single message display
│   │   ├── ChatInput.tsx        # Input field + send button
│   │   └── LoadingIndicator.tsx # Typing dots or spinner
│   └── ui/                      # shadcn/ui components (auto-generated)
├── hooks/
│   └── useChat.ts               # Custom hook: streaming fetch, state management
├── lib/
│   ├── api.ts                   # API client functions
│   └── types.ts                 # TypeScript types + Zod schemas
└── ...config files
```

### State Management
- `useReducer` in the `useChat` custom hook
- Message type:
  ```typescript
  type Message = {
    id: string;
    role: "user" | "assistant";
    content: string;
    metadata?: {
      queryType: string;
      toolsUsed: string[];
      cookwareSufficient?: boolean;
      missingCookware?: string[];
    };
    isStreaming?: boolean;
  };
  ```

### `useChat` Hook API
```typescript
function useChat(): {
  messages: Message[];
  sendMessage: (content: string) => Promise<void>;
  isLoading: boolean;
  error: string | null;
}
```
- Handles both sync and streaming modes
- Dispatches state updates via reducer
- ~40-60 lines of code

### Styling
- Tailwind + shadcn/ui
- Color scheme: Neutral/slate palette with warm orange accent (cooking theme)
- Layout: Centered chat container, max-width ~768px, full height
- Mobile responsive (Tailwind breakpoints)
- shadcn components used:
  - `Button` — send button
  - `Input` — chat text input
  - `Card` — message bubbles
  - `ScrollArea` — scrollable message list

### Message Rendering
- Use `react-markdown` for rendering assistant messages (recipes come through with numbered lists, headers, etc.)
- Differentiate message styles by role (user = right-aligned, assistant = left-aligned)
- No special "recipe card" UI — markdown rendering handles formatting well enough within timebox

### API Response Validation
- Use `zod` to validate API responses on the frontend
- Define schemas in `lib/types.ts` alongside TypeScript types
- This satisfies the "strong typing for request/response schemas" requirement

---

## 6. Project Structure

```
.
├── backend/
│   ├── main.py                    # FastAPI entry point, CORS, routes
│   ├── graphs/
│   │   ├── __init__.py
│   │   └── cooking_graph.py       # LangGraph definition, all nodes, edges
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── classify.py            # classify_query node
│   │   ├── research.py            # research_agent node
│   │   ├── cookware.py            # cookware_check node
│   │   ├── generate.py            # generate_response node
│   │   └── refuse.py              # refuse_response node
│   ├── tools/
│   │   ├── __init__.py
│   │   └── search.py              # Tavily/DuckDuckGo search tool setup
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── classify.py            # Classification prompt
│   │   ├── research.py            # Research agent prompt
│   │   ├── cookware.py            # Cookware check prompt
│   │   └── generate.py            # Response generation prompt
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── requests.py            # Pydantic request models
│   │   ├── responses.py           # Pydantic response models
│   │   └── graph_state.py         # LangGraph state schema
│   ├── config.py                  # Settings, env vars, constants (cookware list)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── ruff.toml
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── LoadingIndicator.tsx
│   │   └── ui/                    # shadcn components
│   ├── hooks/
│   │   └── useChat.ts
│   ├── lib/
│   │   ├── api.ts
│   │   └── types.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml
├── Makefile
├── README.md
└── .editorconfig
```

---

## 7. Docker & DevOps

### Backend Dockerfile
- Base image: `python:3.12-slim`
- Single stage (no build step needed for Python)
- Install deps from `requirements.txt`
- Run with `uvicorn main:app --host 0.0.0.0 --port 8000`

### Frontend Dockerfile
- Multi-stage build:
  - Stage 1: `node:20-alpine` — install deps + build
  - Stage 2: `node:20-alpine` — run Next.js standalone output
- Uses Next.js standalone output mode for smaller image

### docker-compose.yml
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      backend:
        condition: service_healthy
```

### Environment Variables

**Backend** (`.env.example`):
```
OPENAI_API_KEY=your-openai-api-key-here
TAVILY_API_KEY=your-tavily-api-key-here  # Optional, falls back to DuckDuckGo
MODEL_NAME=gpt-5-mini
LOG_LEVEL=INFO
```

**Frontend** (`.env.example`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Makefile Targets
```makefile
dev-backend     # cd backend && uvicorn main:app --reload
dev-frontend    # cd frontend && bun run dev (or pnpm)
docker-up       # docker-compose up --build
docker-down     # docker-compose down
lint-backend    # cd backend && ruff check . && ruff format --check .
lint-frontend   # cd frontend && bun run lint
```

---

## 8. Build Order & Time Allocation

| Time | Task | Priority |
|------|------|----------|
| 0:00–0:10 | Scaffold monorepo structure, init projects, Ruff config, initial git commit | Critical |
| 0:10–0:25 | Backend schemas, config, constants, prompts | Critical |
| 0:25–0:55 | LangGraph: all 5 nodes + graph wiring + state | Critical |
| 0:55–1:10 | FastAPI: sync endpoint working E2E with graph | Critical |
| 1:10–1:25 | FastAPI: SSE streaming endpoint | High |
| 1:25–1:40 | Frontend: project setup, shadcn init, component shells | Critical |
| 1:40–2:10 | Frontend: useChat hook, API client, full chat UI working with sync endpoint | Critical |
| 2:10–2:25 | Frontend: switch to streaming SSE consumption | High |
| 2:25–2:40 | Docker: both Dockerfiles + compose + test | Medium |
| 2:40–2:50 | Polish: error states, loading indicators, edge cases | Medium |
| 2:50–3:00 | README: setup, curl examples, deployment/auth/ELT docs | Critical |

**Fallback plan**: If SSE streaming hits snags, keep the sync endpoint integration. A working non-streaming app scores higher than a broken streaming app.

---

## 9. README Sections to Write

These are **documentation-only** sections required by the spec. Write them at the end.

### AWS Deployment Plan
- **Compute**: ECS Fargate for both services (serverless containers, no EC2 management)
- **Why Fargate over Lambda**: Persistent connections needed for SSE streaming; Lambda's 30s timeout is too short
- **Secrets**: AWS Secrets Manager for API keys, referenced as ECS task definition secrets
- **Networking**: ALB in front of ECS, with path-based routing (`/api/*` → backend, `/*` → frontend)
- **Scaling**: ECS auto-scaling on CPU/memory metrics, ALB distributes traffic
- **Observability**: CloudWatch Logs with structured JSON logging, CloudWatch Container Insights for metrics, X-Ray for distributed tracing

### Auth & Security Plan
- **API auth**: JWT tokens via Auth0 or AWS Cognito, validated in FastAPI middleware
- **CORS**: Restrict to known frontend origins in production
- **Rate limiting**: Token bucket per user via Redis or API Gateway throttling
- **Input validation**: Pydantic models on all endpoints, max message length limit
- **Prompt injection mitigation**: System prompts instruct model to stay in-scope; classification node acts as first line of defense
- **Key security**: API keys in environment variables (never in code), rotated via Secrets Manager

### ELT Integration Plan (Bonus)
- **Extract**: Log recipe selections to a message queue (SQS or Kafka) when users confirm recipes
- **Load**: Ingest into a data warehouse (Redshift, BigQuery, or Snowflake)
- **Transform**: dbt models to aggregate recipes by cuisine, ingredient frequency, cookware usage, time-of-day patterns
- **Serve**: Dashboard in Metabase/Looker showing what people are cooking at a glance

### Edge Cases to Document
- Multi-step recipes requiring unavailable cookware → suggest substitutions (partially handled by cookware_check node)
- Ambiguous ingredient names ("tomato sauce" vs "strained tomatoes") → ask for clarification
- Non-English queries or metric/imperial conversions → future: detect language and convert units
- Long conversations and context window limits → future: implement conversation summarization or sliding window
- Tool failures (search outages, rate limits) → future: retry with exponential backoff, circuit breaker pattern
- Prompt injection attempts → classification node helps, but dedicated guardrails needed for production
- Recipes requiring specialized techniques (sous vide, fermentation) → flag as advanced, note equipment gaps

### Design Decisions Section for README
- Why `gpt-5-mini` over `gpt-4o` (speed/cost for this use case)
- Why multi-node graph over single ReAct agent (visibility, control, testability)
- Why raw fetch+SSE over `@langchain/langgraph-sdk` / CopilotKit (fewer deps, demonstrates understanding)
- Why stateless backend (simplicity, scalability)
- Why Tavily over other search tools (LangChain integration quality)
- Why separate `generate_response` node (clean separation, spec compliance)

---

## 10. Python Dependencies

```
# requirements.txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-community>=0.3.0
langgraph>=0.2.0
tavily-python>=0.5.0
pydantic>=2.0.0
python-dotenv>=1.0.0
sse-starlette>=2.0.0
```

## 11. Key Implementation Notes

### Prompts
- Store each prompt as a string constant in its own file under `prompts/`
- Add a version comment at the top of each (e.g., `# v1.0 — initial classification prompt`)
- This counts as "prompt versioning" for bonus points

### Ruff Configuration
```toml
# ruff.toml
target-version = "py312"
line-length = 88

[lint]
select = ["E", "F", "I", "N", "W"]

[format]
quote-style = "double"
```
Set this up in the first 10 minutes. Run `ruff format .` before every commit.

### Frontend Package Manager
- Use `bun` as primary (spec mentions `bun run dev`)
- Document `pnpm` as alternative in README

### Type Safety
- Frontend: Zod schemas in `lib/types.ts` that mirror the Pydantic response models
- `z.infer<typeof schema>` for TypeScript types derived from Zod
- Validate every API response through Zod before using the data