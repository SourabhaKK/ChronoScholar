# ChronoScholar — Architecture

## System Overview

ChronoScholar is a temporally-aware research memory agent. It ingests arXiv
papers, builds a Cognee knowledge graph with typed relationships, and detects
when stored scientific beliefs are contradicted by incoming literature.

```
arXiv API
    │
    ▼
ArxivService ──────► CogneeService ──────► Cognee Knowledge Graph
    │                    │                  (Entities + Typed Edges)
    │                    │
    ▼                    ▼
FastAPI                SearchType.GRAPH_COMPLETION
(/ingest)              (/query, /contradictions)
    │
    ▼
ContradictionService ◄── LLMService (Groq / Gemini / Fallback)
    │
    ▼
ContradictionPair (Pydantic schema)
    │
    ▼
FastAPI (/detect, /contradictions)
    │
    ▼
HTML/JS Frontend (index.html + graph.html)
```

## Directory Structure

```
ChronoScholar/
│
├── CLAUDE.md                    # Master Claude Code instructions
├── ARCHITECTURE.md              # This file
├── PRD.md                       # Product requirements
├── API_CONTRACTS.md             # Exact API request/response schemas
├── TESTING_STRATEGY.md          # TDD approach and test specifications
├── IMPLEMENTATION_NOTES.md      # Cognee gotchas, patterns, constraints
├── PROMPTS.md                   # All LLM prompts defined upfront
├── BENCHMARK.md                 # Ground truth dataset specification
├── SESSIONS.md                  # Claude Code session-by-session build plan
├── .env.example                 # All environment variables (no real values)
│
├── pyproject.toml               # Dependencies and tool configuration
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # Local dev orchestration
│
├── .github/
│   └── workflows/
│       └── ci.yml               # lint → typecheck → test → docker build
│
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, router registration
│   ├── config.py                # pydantic-settings Settings class
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cognee_service.py    # All Cognee operations (add, cognify, search)
│   │   ├── arxiv_service.py     # arXiv paper fetching and ID parsing
│   │   ├── llm_service.py       # Provider-agnostic LLM with fault tolerance
│   │   └── contradiction_service.py  # Contradiction detection logic
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── ingest.py            # POST /ingest, GET /ingest/status/{run_id}
│   │   ├── query.py             # POST /query
│   │   ├── contradictions.py    # GET /contradictions, POST /detect
│   │   └── graph.py             # GET /graph/visualise
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── paper.py             # Paper, PaperIngestRequest, IngestResponse
│   │   ├── query.py             # QueryRequest, QueryResponse, SourceCitation
│   │   └── contradiction.py     # ContradictionPair, ContradictionResponse
│   │
│   └── static/
│       ├── index.html           # Single-page UI (ingest + query + dashboard)
│       └── graph.html           # pyvis graph render target (generated)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # All shared fixtures — nowhere else
│   ├── test_config.py           # Config loading and validation
│   ├── test_llm_service.py      # LLM fault tolerance and provider switching
│   ├── test_arxiv_service.py    # arXiv fetching, ID parsing, rate limiting
│   ├── test_cognee_service.py   # Cognee operations with mocked cognee calls
│   ├── test_contradiction_service.py  # Core contradiction detection logic
│   └── test_api_routes.py       # All route contract tests
│
├── scripts/
│   ├── seed_corpus.py           # Reproducible ingestion of known paper set
│   └── build_benchmark.py       # Generate contradiction pair ground truth
│
└── mlflow_tracking/             # MLflow SQLite artifacts (gitignored)
    └── .gitkeep
```

## Component Responsibilities

### app/main.py
- Creates FastAPI app with title, description, version
- Lifespan context manager: initialises CogneeService on startup, closes on shutdown
- Registers all routers with prefixes
- Mounts /static directory
- Adds CORS middleware for local dev

### app/config.py
- Single Settings class using pydantic-settings
- Reads all values from environment variables
- Validates llm_provider is one of: groq, gemini, ollama, fallback
- Validates contradiction_confidence_threshold is between 0.0 and 1.0
- Single instance created at import time, injected via FastAPI Depends

### app/services/cognee_service.py
- Owns ALL calls to cognee.add(), cognee.cognify(), cognee.search()
- Initialised once in lifespan, injected via FastAPI dependency
- run_ingestion(papers: list[Paper]) → IngestResult (runs as background task)
- search(question: str, mode: SearchType) → list[SearchResult]
- get_graph_html() → str (pyvis render)
- get_stats() → GraphStats (entity count, edge count, paper count)
- Never called directly from routers — always through dependency injection

### app/services/arxiv_service.py
- fetch(query: str, max_results: int, domain_tag: str | None) → list[Paper]
- fetch_by_id(paper_id: str) → Paper | None
- Enforces ARXIV_REQUEST_DELAY between requests
- Strips full URL from paper IDs, returns clean "XXXX.XXXXX" format
- Maps arxiv.Result to Paper Pydantic schema

### app/services/llm_service.py
- complete(prompt: str, fallback: str = "") → str
- Single method, provider-agnostic
- Tier 1: Groq with exponential backoff (3 attempts, 2^n second delays)
- Tier 2: Gemini on RateLimitError, with 5*2^n second delays
- Tier 3: Returns fallback string, zero network calls
- Primary provider determined by LLM_PROVIDER env var
- All retry logic lives here — nowhere else in the codebase

### app/services/contradiction_service.py
- detect(paper_a: Paper, paper_b: Paper) → ContradictionPair
- Uses LLMService.complete() with the prompt defined in PROMPTS.md
- Parses LLM JSON response into ContradictionPair schema
- Falls back to detection_method="fallback" on any parse failure
- detect_batch(papers: list[Paper]) → list[ContradictionPair]
  (runs all n*(n-1)/2 pairs for a corpus)

### app/routers/ingest.py
- POST /ingest: validates request, launches background task, returns run_id
- GET /ingest/status/{run_id}: returns current progress from in-memory store
- Logs IngestResult metrics to MLflow on completion

### app/routers/query.py
- POST /query: calls CogneeService.search(), formats QueryResponse
- Prefixes user question with grounding instruction from PROMPTS.md

### app/routers/contradictions.py
- GET /contradictions: returns paginated list from in-memory contradiction store
- POST /detect: fetches two papers by ID, runs ContradictionService.detect()

### app/routers/graph.py
- GET /graph/visualise: returns pyvis-generated HTML
- GET /graph/stats: returns entity/edge/paper counts

## Data Flow: Ingestion

```
POST /ingest (query, max_results)
    │
    ├── Validate request (Pydantic)
    ├── Generate run_id (uuid4)
    ├── Store run_id → {"status": "running", "progress": 0} in memory
    ├── Launch BackgroundTask: run_ingestion(run_id, query, max_results)
    └── Return {"run_id": ..., "status": "running"} immediately

BackgroundTask: run_ingestion
    │
    ├── ArxivService.fetch(query, max_results) → list[Paper]
    ├── Update progress: {"status": "running", "progress": 30}
    ├── CogneeService.add(papers) → adds to Cognee document store
    ├── Update progress: {"status": "running", "progress": 60}
    ├── CogneeService.cognify() → builds knowledge graph
    ├── Update progress: {"status": "running", "progress": 90}
    ├── ContradictionService.detect_batch(papers) → contradiction pairs
    ├── MLflow.log_metrics(entities, edges, papers, duration)
    └── Update progress: {"status": "complete", "progress": 100}
```

## Data Flow: Contradiction Detection

```
POST /detect (paper_id_a, paper_id_b)
    │
    ├── ArxivService.fetch_by_id(paper_id_a) → Paper A
    ├── ArxivService.fetch_by_id(paper_id_b) → Paper B
    └── ContradictionService.detect(paper_a, paper_b)
            │
            ├── Build prompt (from PROMPTS.md)
            ├── LLMService.complete(prompt, fallback=FALLBACK_JSON)
            ├── Parse JSON response → ContradictionPair
            └── Return ContradictionPair
```

## Dependency Injection Pattern

```python
# Correct pattern — use this everywhere
def get_cognee_service(request: Request) -> CogneeService:
    return request.app.state.cognee_service

def get_contradiction_service(request: Request) -> ContradictionService:
    return request.app.state.contradiction_service

@router.post("/ingest")
async def ingest(
    body: PaperIngestRequest,
    background_tasks: BackgroundTasks,
    cognee: CogneeService = Depends(get_cognee_service),
):
    ...
```
