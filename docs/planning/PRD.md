# ChronoScholar — Product Requirements Document

## Problem Statement

AI agents that reason over scientific literature suffer from two failures:

1. **Stateless retrieval**: Every query starts from scratch. The agent has no
   memory of what it has read before or what it concluded.

2. **Belief staleness**: When new papers contradict stored claims, the agent
   has no mechanism to detect or surface those contradictions. It continues
   returning outdated answers with full confidence.

Standard RAG addresses (1) partially. No existing tool addresses (2) at all.
ChronoScholar addresses both by combining Cognee's persistent graph-vector
memory with a contradiction detection layer.

## User Stories

### Core (must ship for hackathon — July 5 deadline)

**US-1: Paper Ingestion**
As a researcher, I can enter an arXiv search query and max paper count,
and ChronoScholar will ingest those papers into its knowledge graph.
I can see ingestion progress without the UI freezing.

**US-2: Knowledge Graph Visualisation**
As a researcher, after ingestion completes, I can view a force-directed
graph of the entities and relationships extracted from the papers.
I can see node types (Paper, Claim, Method, Dataset) visually distinguished.

**US-3: Multi-Hop Query**
As a researcher, I can ask a natural language question and receive a
grounded answer that cites specific papers from the knowledge graph,
not from parametric LLM knowledge.

**US-4: Contradiction Dashboard**
As a researcher, I can see a dashboard listing all detected contradictions
between papers in the graph, with confidence scores and explanations.
I can filter by minimum confidence threshold.

**US-5: On-Demand Contradiction Detection**
As a researcher, I can submit two arXiv paper IDs and immediately see
whether they contradict each other, with a structured explanation.

### Evaluation (build during hackathon — needed for research paper)

**US-6: Reproducible Corpus Seeding**
As a developer, I can run `python scripts/seed_corpus.py` to ingest a
predefined list of papers reproducibly. The same papers, same order,
same result every time.

**US-7: Benchmark Dataset Generation**
As a researcher, I can run `python scripts/build_benchmark.py` to generate
a JSON file of paper pairs with ground truth contradiction labels.

**US-8: MLflow Experiment Tracking**
As a developer, every ingestion run automatically logs to MLflow:
paper count, entity count, edge count, cognify duration, contradiction
pairs detected, LLM provider used.

### Out of Scope (do not build — post-hackathon only)

- User authentication or multi-user isolation
- Full PDF text ingestion (abstracts only for hackathon)
- Real-time streaming updates via WebSocket
- Any database other than SQLite
- Email or notification alerts
- Paper recommendation engine
- Browser extension

## Acceptance Criteria

### Contradiction Detection
- Precision >= 0.70 on the 20-pair manually labelled benchmark dataset
- Returns result in < 5 seconds per pair on standard laptop hardware
- Never returns an empty explanation, claim_a, or claim_b field
- Gracefully degrades to fallback when LLM is unavailable
- detection_method field correctly reports "llm" or "fallback"

### Knowledge Graph
- Entities extracted for 100% of successfully ingested papers
- Minimum 3 distinct edge types present after ingesting 20+ papers
- Graph visualisation renders in < 2 seconds
- Graph remains queryable while new ingestion runs in background

### API
- GET /health returns 200 with no graph loaded
- GET /ready returns 200 only when Cognee graph is initialised
- GET /ready returns 503 when graph is still loading
- All routes return structured Pydantic responses — never raw strings
- p99 latency < 3 seconds for POST /query on a 50-paper corpus
- POST /ingest returns immediately with run_id (does not block)
- Background ingestion does not crash the server on arXiv API failure

### Testing
- Minimum 30 pytest cases, all passing
- All tests run with zero network calls and zero real API keys
- CI pipeline passes: ruff lint → mypy typecheck → pytest → docker build
- Test coverage >= 70% on app/ directory

### Frontend
- Single HTML file — no build step, no CDN dependencies beyond vis-network
- Ingest form with query input, max_papers slider, domain_tag dropdown
- Real-time progress polling (GET /ingest/status) every 3 seconds
- Contradiction dashboard loads on page load
- Query interface with search_mode selector (GRAPH_COMPLETION / SEMANTIC)
- Mobile-responsive layout

### Docker
- docker build completes without errors
- docker-compose up starts the full stack
- All environment variables configurable via docker-compose.yml

## Demo Flow (3 minutes — rehearsed)

**0:00–0:30 — Problem**
"AI agents forget. Worse, they believe outdated things. I ingested 50 papers
on AI memory systems. Watch what happens when a new paper arrives that
contradicts what the agent already believes."

**0:30–1:30 — Live Ingest + Graph**
- Paste query: "agent memory knowledge graph temporal"
- Set max_papers: 20
- Hit ingest, show progress bar
- Show knowledge graph appear: nodes labelled Paper/Claim/Method,
  edges labelled contradicts/supports/extends

**1:30–2:30 — Contradiction Detection**
- Navigate to Contradiction Dashboard
- Show known contradiction pair: Mem0 (2504.19413) vs Zep (2501.13956)
- Highlight: label="contradicts", confidence=0.87, two-sentence explanation
- This is the moment — judges remember one thing. Make it this.

**2:30–3:00 — Multi-Hop Query**
- Ask: "What is the current consensus on graph vs vector memory for AI agents?"
- Show GRAPH_COMPLETION response with paper citations
- Contrast: "Flat RAG would give you one paper. Graph memory gives you
  the relationship between all of them."
