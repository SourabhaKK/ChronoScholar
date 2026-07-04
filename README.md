# ChronoScholar

> Temporally-aware research memory agent — detects when stored
> scientific beliefs are contradicted by incoming literature,
> using Cognee's hybrid graph-vector memory layer.

---

## The Problem

AI agents using standard RAG have no mechanism to detect when
stored beliefs become outdated or contradicted. An agent that
ingests Paper A in January and Paper B in March — where B
refutes A's central claim — will return answers from both papers
with equal confidence indefinitely. This is not a retrieval
problem. Flat RAG cannot fix it. It requires persistent memory
with explicit contradiction awareness.

ChronoScholar addresses this by building a typed knowledge graph
from scientific papers, running dedicated contradiction detection
across stored belief pairs, and synthesizing cross-paper context
using Cognee's GRAPH_COMPLETION search mode.

---

## Demo

![Demo](docs/demo.gif)

Three capabilities demonstrated:
- Knowledge graph built from 10 arXiv papers: 118 entities,
  203 edges, 6 typed edge types
- Contradiction detection: F1=1.000 on 10-pair pilot benchmark
  (Precision=1.000, Recall=1.000, n=4 positive, n=6 negative)
- Split-screen comparison: single-paper RAG vs cross-paper
  graph synthesis on the same query

---

## How It Works

Four components:

**1. Cognee Knowledge Graph**
Ingests arXiv paper abstracts via a custom ontology:
- Node types: Paper, Claim, Method, Dataset, Author
- Edge types: contradicts, supports, extends, invalidates,
  replicates, authored_by
- Built using cognee.add() + cognee.cognify(graph_model=custom_model)
- Stored in LanceDB (vectors) + LadybugDB (graph topology)

**2. GRAPH_COMPLETION Search**
Multi-hop synthesis across 118 nodes and 203 edges.
Answers cross-paper questions by traversing the knowledge graph
and synthesizing context — not by retrieving a single chunk.
Uses GPT-4o-mini for Cognee's internal entity extraction and
synthesis calls.

**3. Contradiction Detection**
Gemini 2.5 Flash classifies paper pairs as:
contradicts / supports / extends / unrelated.
Structured output with confidence score and two-sentence
explanation citing specific claims from each paper.
Benchmark (pilot): Precision=1.000, Recall=1.000, F1=1.000
(n=10 pairs, directional result — sample size insufficient
for confidence interval estimation).

**4. Persistent Memory**
Knowledge graph survives server restarts.
Contradiction pairs pre-loaded from predictions.json on startup.
Compare results pre-computed and cached from compare_cache.json.

---

## Architecture

```
arXiv API
    │
    ▼
ArxivService.fetch() ──► CogneeService.cognify() ──► Knowledge Graph
                              │                    (118 nodes, 203 edges)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
            GRAPH_COMPLETION        ContradictionService
            (GPT-4o-mini,           (Gemini 2.5 Flash,
             cross-paper             F1=1.000, n=10)
             synthesis)
                    │                    │
                    └─────────┬──────────┘
                              ▼
                      FastAPI + HTML UI
              /ingest /query /detect /compare /graph
```

---

## Results

| Metric | Value |
|---|---|
| Papers ingested | 10 |
| Knowledge graph entities | 118 |
| Knowledge graph edges | 203 |
| Edge types | 6 |
| Cognify duration | 63.3s |
| Contradiction Precision | 1.000 |
| Contradiction Recall | 1.000 |
| Contradiction F1 | 1.000 |
| Benchmark pairs (pilot) | 10 |
| True positives | 4 |
| False positives | 0 |
| False negatives | 0 |

> **Statistical caveat:** Benchmark is a pilot evaluation (n=10,
> 4 positive examples). Results are directional only. Sample size
> is insufficient for statistically robust performance claims.

---

## LLM Architecture

Three providers with distinct roles to eliminate TPM contention:

| Role | Provider | Reason |
|---|---|---|
| Application LLM (detect, query grounding) | Gemini 2.5 Flash | Scientific NLI accuracy, 1M TPM free tier |
| Cognee internal (entity extraction, synthesis) | GPT-4o-mini | Reliable structured output, sufficient context |
| Tier-2 fallback | Groq llama-3.1-8b-instant | Low latency, free tier resilience |

Cognee's internal LLM and the application LLM use separate API
keys to prevent shared rate limit pool contention.

---

## Quick Start

```bash
git clone https://github.com/SourabhaKK/ChronoScholar
cd ChronoScholar
cp .env.example .env
# Edit .env: add GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY
python scripts/seed_corpus.py
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

---

## Docker

```bash
docker-compose up
# Open http://localhost:8000
```

Note: run `python scripts/seed_corpus.py` before starting the
container to populate the knowledge graph in data/.
The docker-compose.yml mounts ./data as a volume so the graph
persists across container restarts.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| GEMINI_API_KEY | Yes | Gemini 2.5 Flash — application LLM |
| OPENAI_API_KEY | Yes | GPT-4o-mini — Cognee internal LLM |
| LLM_API_KEY | Yes | Same as OPENAI_API_KEY (Cognee reads this) |
| LLM_MODEL | Yes | openai/gpt-4o-mini (LiteLLM prefix format) |
| GROQ_API_KEY | Yes | Groq — tier-2 LLM fallback |
| APP_LLM_PROVIDER | Yes | gemini |
| COGNEE_SKIP_CONNECTION_TEST | Yes | true — prevents startup hang |
| ENABLE_BACKEND_ACCESS_CONTROL | Yes | false — single-user demo posture |
| LLM_FAST_MODE | Dev only | true — reduces retry backoff for development |
| ARXIV_REQUEST_DELAY | No | 3.0 — seconds between arXiv requests (ToS) |
| COGNEE_BATCH_SIZE | No | 2 — papers per cognify() call (Groq TPM limit) |

---

## Running Tests

```bash
pytest tests/ -v
# 60 tests across 8 components — all passing
# CI: ruff lint → mypy typecheck → pytest → docker build
```

---

## Cognee Integration

ChronoScholar uses Cognee's V1 API throughout:

**Ingestion:** `cognee.add(text)` followed by
`cognee.cognify(graph_model=custom_model)` where `custom_model`
is a Pydantic BaseModel defining the 5 node types and 6 edge types.
Documents are batched in groups of 2 to stay within Groq's 6K TPM
free-tier limit during entity extraction.

**Search:** Two modes used explicitly:
- `SearchType.GRAPH_COMPLETION` — multi-hop synthesis for the
  /query endpoint and the chronoscholar panel in /compare
- `SearchType.CHUNKS` — single-chunk retrieval for the flat_rag
  panel in /compare, simulating single-paper RAG behavior

**Auth posture:** `ENABLE_BACKEND_ACCESS_CONTROL=false` required.
Default multi-tenant mode writes cognify() output to a
UUID-scoped LadybugDB file while get_graph_data() reads the
global file — different databases, producing empty graph results.
Single-user posture eliminates this divergence.

**Configuration:** Cognee 1.2.2 reads all LLM config from
environment variables via LiteLLM. Model names require LiteLLM
provider prefixes: `openai/gpt-4o-mini`, not `gpt-4o-mini`.

---

## Development

Built with strict TDD — Red→Green→Refactor commit discipline
visible in git history. 8 components implemented in dependency
order: Config → Schemas → LLMService → ArxivService → prompts →
ContradictionService → CogneeService → API Routes.

60 tests across 8 test files. All external calls mocked —
Cognee, arXiv, Groq, Gemini, MLflow. Tests run with zero
network calls and zero real API keys.

Upstream API breaks encountered and resolved during development:
- arxiv 4.0.0: Search.results() removed
- Cognee 1.2.2: set_llm_config() API changed to env-var-only
- Cognee 1.2.2: get_nodes()/get_edges() replaced by get_graph_data()
- Cognee 1.2.2: multi-tenant auth posture requires explicit opt-out

---

## License

MIT
