# ChronoScholar — Claude Code Session Plan

## How to Use This File

Each session has:
- A precise goal (one testable output)
- The exact opening prompt to give Claude Code
- Files created in that session
- The acceptance test (how you know the session succeeded)

Never start a session without reading the opening prompt.
Never combine two sessions into one — the discipline matters.

---

## Pre-Hackathon Sessions (June 26–28)

### Session P1 — Project Scaffold
**Goal**: Complete directory structure with empty files. No implementation logic.
**When**: June 26, after reading the hackathon brief.

**Opening prompt**:
```
Read CLAUDE.md, ARCHITECTURE.md, and API_CONTRACTS.md before writing any code.

Create the complete project scaffold defined in ARCHITECTURE.md:
- All directories
- All __init__.py files
- pyproject.toml with all dependencies listed in the stack
- .env.example with all variables from IMPLEMENTATION_NOTES.md
- Empty app/main.py with the create_app() function signature only
- Empty service files with class definitions and method signatures only
  (no method bodies — just `pass` or `...`)
- Empty router files with route decorator stubs only
- Empty schema files with class names only
- Empty test files with the test function names from TESTING_STRATEGY.md
  as `def test_xxx(): pass` stubs

Do NOT implement any logic. Do NOT import anything not yet installed.
The goal is structure only.
```

**Files created**: All files in the directory tree (empty/stub)

**Acceptance test**: `find . -name "*.py" | head -30` shows correct structure.
`python -c "from app.main import create_app"` does not raise ImportError.

---

### Session P2 — Config and Schemas
**Goal**: Working config class and all Pydantic schemas. Tests passing.
**When**: June 26 afternoon.

**Opening prompt**:
```
Read CLAUDE.md, API_CONTRACTS.md, and TESTING_STRATEGY.md.

Current state: scaffold exists, all files empty.

Task 1: Implement app/config.py
- pydantic-settings Settings class
- All variables from .env.example
- llm_provider must validate against {"groq", "gemini", "ollama", "fallback"}
- contradiction_confidence_threshold must be between 0.0 and 1.0
- Tests are in tests/test_config.py — implement config until all 6 tests pass

Task 2: Implement all Pydantic v2 schemas in app/schemas/
- paper.py: Paper, PaperIngestRequest, IngestResponse, IngestStatusResponse
- query.py: QueryRequest, QueryResponse, SourceCitation
- contradiction.py: ContradictionPair, ContradictionResponse, DetectRequest

All schemas must exactly match the field names and types in API_CONTRACTS.md.
No extra fields. No missing fields.

Run tests after each schema file. All 6 config tests must be green before
moving to schemas.
```

**Files modified**: app/config.py, all app/schemas/ files, tests/test_config.py

**Acceptance test**: `pytest tests/test_config.py -v` — all 6 pass.
`python -c "from app.schemas.contradiction import ContradictionPair"` — no error.

---

### Session P3 — LLMService with TDD
**Goal**: LLMService fully implemented, all 7 LLM tests passing.
**When**: June 26 evening / June 27 morning.

**Opening prompt**:
```
Read CLAUDE.md, IMPLEMENTATION_NOTES.md (LLM Fault Tolerance section),
and TESTING_STRATEGY.md (test_llm_service.py section).

Current state: Config and schemas pass. LLMService is an empty class.

TDD cycle:
1. The test stubs in tests/test_llm_service.py exist but all pass trivially.
   First, fill in the test bodies from the specifications in TESTING_STRATEGY.md.
   Run them — they should now FAIL (RED).
2. Implement app/services/llm_service.py with the three-tier fault tolerance
   pattern from IMPLEMENTATION_NOTES.md until all tests pass (GREEN).
3. Refactor if needed without breaking tests.

Constraints:
- Groq client: use groq Python package
- Gemini client: use google-generativeai Python package
- All retry delays use time.sleep() — mockable in tests
- Primary provider determined by settings.llm_provider
- complete() is a synchronous method (not async)
- No bare except clauses
```

**Files modified**: app/services/llm_service.py, tests/test_llm_service.py

**Acceptance test**: `pytest tests/test_llm_service.py -v` — all 7 pass with
zero network calls (verified by block_network fixture not raising).

---

### Session P4 — ArxivService with TDD
**Goal**: ArxivService implemented, all 7 arXiv tests passing.
**When**: June 27.

**Opening prompt**:
```
Read CLAUDE.md and TESTING_STRATEGY.md (test_arxiv_service.py section).

Current state: LLMService tests pass. ArxivService is empty.

TDD cycle:
1. Fill in test bodies in tests/test_arxiv_service.py from TESTING_STRATEGY.md.
   Run — confirm RED.
2. Implement app/services/arxiv_service.py from IMPLEMENTATION_NOTES.md
   (arXiv API section) until GREEN.

The _parse_result static method is the critical piece:
- Input: arxiv.Result object
- Output: Paper schema
- Must extract clean ID "XXXX.XXXXX" from URL "http://arxiv.org/abs/XXXXvN"
- Must strip version suffix (v1, v2 etc.)

The fetch() method must:
- Accept query, max_results, optional domain_tag
- Apply domain_tag as "cat:cs.AI" appended to query
- Call time.sleep(self.request_delay) between results
- Return list[Paper], never raise on empty results
```

**Files modified**: app/services/arxiv_service.py, tests/test_arxiv_service.py

**Acceptance test**: `pytest tests/test_arxiv_service.py -v` — all 7 pass.

---

### Session P5 — ContradictionService with TDD
**Goal**: ContradictionService implemented, all 9 contradiction tests passing.
**When**: June 27–28.

**Opening prompt**:
```
Read CLAUDE.md, PROMPTS.md, IMPLEMENTATION_NOTES.md (contradiction section),
and TESTING_STRATEGY.md (test_contradiction_service.py section).

Current state: LLMService and ArxivService pass. ContradictionService is empty.

TDD cycle:
1. Fill in all 9 test bodies from TESTING_STRATEGY.md. Run — confirm RED.
2. Implement app/services/contradiction_service.py:
   - detect(paper_a: Paper, paper_b: Paper) → ContradictionPair
   - detect_batch(papers: list[Paper]) → list[ContradictionPair]
   - Prompt must use the template from PROMPTS.md (import from app/prompts.py)
   - JSON parsing must use parse_llm_response from IMPLEMENTATION_NOTES.md
   - Never raise — always return a valid ContradictionPair (fallback if needed)

Also implement app/prompts.py with all prompt strings from PROMPTS.md.
Prompts are imported here — never defined inline in services.
```

**Files modified**: app/services/contradiction_service.py, app/prompts.py,
tests/test_contradiction_service.py

**Acceptance test**: `pytest tests/test_contradiction_service.py -v` — all 9 pass.

---

## Hackathon Sessions (June 29 – July 5)

### Session H1 — CogneeService (Day 1: June 29)
**Goal**: CogneeService wrapper with mocked tests passing. Real Cognee wired up.
**When**: June 29 morning.

**Opening prompt**:
```
Read CLAUDE.md, ARCHITECTURE.md (CogneeService section),
and IMPLEMENTATION_NOTES.md (Cognee-Specific section in full).

Current state: ContradictionService passes. CogneeService is empty.

Task:
1. Write tests/test_cognee_service.py — mock ALL cognee calls
   Test: initialise() sets graph_loaded to True after cognify
   Test: run_ingestion() calls add() then cognify() for each batch of 15
   Test: search() calls cognee.search() with correct SearchType
   Test: get_stats() returns dict with paper_count, entity_count, edge_count
   Test: run_ingestion() updates run_store progress during execution
   Run — confirm RED.

2. Implement app/services/cognee_service.py:
   - Async methods (cognee is async)
   - Custom ontology from IMPLEMENTATION_NOTES.md
   - Batch size 15 for cognify()
   - graph_loaded flag set after first successful cognify()
   - run_ingestion() updates run_store dict during processing

Run: pytest tests/test_cognee_service.py -v — all pass.
Then do a real smoke test: python scripts/seed_corpus.py --limit 3
(ingest 3 papers for real to verify Cognee integration works end-to-end)
```

**Files modified**: app/services/cognee_service.py, tests/test_cognee_service.py

**Acceptance test**: All unit tests pass. `python scripts/seed_corpus.py --limit 3`
completes without error and prints entity count > 0.

---

### Session H2 — FastAPI Routes (Day 1–2: June 29–30)
**Goal**: All routes implemented, all API route tests passing.
**When**: June 29 afternoon.

**Opening prompt**:
```
Read CLAUDE.md, API_CONTRACTS.md, ARCHITECTURE.md (dependency injection section),
and TESTING_STRATEGY.md (test_api_routes.py section).

Current state: All services pass unit tests. Routers are stubs.

Task:
1. Implement app/main.py with create_app(), lifespan, router registration,
   static file mounting, and CORS middleware.
   Use the dependency injection pattern from ARCHITECTURE.md exactly.

2. Implement all routers:
   - app/routers/ingest.py: POST /ingest (202, background task),
     GET /ingest/status/{run_id}
   - app/routers/query.py: POST /query with QUERY_GROUNDING_PREFIX from prompts
   - app/routers/contradictions.py: POST /detect, GET /contradictions
   - app/routers/graph.py: GET /graph/visualise, GET /graph/stats

3. Fill in and run all tests in tests/test_api_routes.py.
   All 13 route tests must pass.

4. Verify: uvicorn app.main:create_app --factory --reload
   GET http://localhost:8000/health returns {"status": "ok", ...}
```

**Files modified**: app/main.py, app/dependencies.py (new), all router files,
tests/test_api_routes.py

**Acceptance test**: `pytest tests/test_api_routes.py -v` — all 13 pass.
Manual: health endpoint returns 200.

---

### Session H3 — Real Ingestion + Benchmark (Day 2: June 30)
**Goal**: Full pipeline working end-to-end on real papers. 20-pair benchmark run.
**When**: June 30.

**Opening prompt**:
```
Read CLAUDE.md, BENCHMARK.md, and scripts/seed_corpus.py (which you implemented).

Current state: All tests pass. Routes work. Real Cognee not yet tested at scale.

Task 1: Run full ingestion on seed corpus
python scripts/seed_corpus.py
This should ingest all papers in data/seed_papers.json.
Fix any runtime errors. Log entity count and edge count after completion.
Target: > 100 entities, > 50 edges after ingesting seed papers.

Task 2: Implement scripts/build_benchmark.py
- Load data/benchmark_pairs.json (the 20 ground truth pairs)
- For each pair, call ContradictionService.detect()
- Save predictions to data/predictions.json
- Print precision/recall/F1 on "contradicts" label to stdout

Task 3: Run the benchmark and record results
python scripts/build_benchmark.py
Record the precision, recall, F1 numbers — these go in the README.
If precision < 0.60, the contradiction prompt needs tuning (see PROMPTS.md).
```

**Acceptance test**: `python scripts/build_benchmark.py` completes and prints
metrics. Precision >= 0.60 (target 0.70+).

---

### Session H4 — Frontend (Day 3–4: July 1–2)
**Goal**: Working HTML/JS frontend served by FastAPI.
**When**: July 1.

**Opening prompt**:
```
Read CLAUDE.md (frontend constraints), PRD.md (US-1 through US-5),
and API_CONTRACTS.md (all response schemas).

Current state: All backend routes work. app/static/index.html is empty.

Build app/static/index.html — single file, no build step, no npm.
Allowed external CDN: vis-network from cdnjs for graph (if needed beyond pyvis).

Three sections in one scrollable page:

Section 1 — Ingest Panel:
- Text input for arXiv query
- Number input for max_papers (1-100, default 20)
- Optional text input for domain_tag
- Submit button → POST /ingest → store run_id
- Progress bar that polls GET /ingest/status/{run_id} every 3 seconds
- On complete: show entity_count, edge_count, papers_ingested
- "View Graph" button → opens /graph/visualise in new tab

Section 2 — Contradiction Dashboard:
- Loads on page load: GET /contradictions?min_confidence=0.7&limit=20
- Table: paper_id_a | paper_id_b | label | confidence | explanation
- Filter slider for min_confidence (0.0–1.0)
- Label badge coloured by type:
  contradicts=red, supports=green, extends=blue, unrelated=grey
- Manual detection form: two paper ID inputs → POST /detect → show result inline

Section 3 — Query Interface:
- Textarea for question
- Radio buttons for search_mode (GRAPH_COMPLETION / SEMANTIC)
- Submit → POST /query → display answer + source cards
- Each source card shows: paper_id, title, published_date, excerpt

Design constraints:
- Dark theme (#1a1a2e background, white text) matching pyvis graph colours
- No external CSS frameworks — vanilla CSS only
- Mobile-responsive (single column on narrow screens)
- All fetch() calls must handle errors and display user-friendly messages
```

**Acceptance test**: Manual walkthrough of all 3 sections works end-to-end.
No JS console errors on load. Mobile layout looks acceptable.

---

### Session H5 — Docker + CI/CD (Day 4–5: July 2–3)
**Goal**: Docker container builds and runs. GitHub Actions CI passes.
**When**: July 2.

**Opening prompt**:
```
Read CLAUDE.md (Docker section) and IMPLEMENTATION_NOTES.md (Docker section).

Current state: Everything works locally. No Docker or CI yet.

Task 1: Implement Dockerfile
- Multi-stage build (builder + runtime) from IMPLEMENTATION_NOTES.md
- Stage 1: install dependencies only
- Stage 2: copy app/ and scripts/ only (no test files in image)
- CMD starts uvicorn with factory pattern

Task 2: Implement docker-compose.yml
- Single service: chronoscholar
- All environment variables from .env.example as compose env vars
- Volume mount: ./data:/app/data (persist Cognee graph between restarts)
- Volume mount: ./mlflow_tracking:/app/mlflow_tracking
- Port: 8000:8000

Task 3: Implement .github/workflows/ci.yml
- Trigger on push and pull_request
- Steps: checkout → python 3.11 → pip install uv → uv sync
  → ruff check → mypy → pytest (exclude benchmark) → docker build

Verify:
docker build -t chronoscholar . && docker run -p 8000:8000 chronoscholar
curl http://localhost:8000/health
```

**Acceptance test**: `docker build -t chronoscholar .` exits 0.
`docker run -p 8000:8000 chronoscholar` → health check passes.

---

### Session H6 — README + Polish (Day 5–6: July 3–4)
**Goal**: Production-ready README. Demo rehearsed. All loose ends fixed.
**When**: July 3.

**Opening prompt**:
```
Read CLAUDE.md, PRD.md (Demo Flow section), and BENCHMARK.md (metrics section).

Current state: Full system working in Docker. CI passing.

Task: Write README.md

Sections (in order):
1. Title + one-line description + badges (CI status, Python version, Docker)
2. Demo GIF placeholder (note: record with Loom and add after)
3. Problem Statement (2 paragraphs from PRD.md)
4. Architecture Diagram (ASCII or mermaid)
5. Cognee Integration (describe how .add(), .cognify(), .search() are used
   with custom ontology — this is what judges read first)
6. Quantified Results:
   - Contradiction detection: Precision X.XX, Recall X.XX, F1 X.XX (n=20 pairs)
   - Graph-RAG vs flat-RAG accuracy on 5 multi-hop test questions
   - p50/p99 latency for /query endpoint
7. Quick Start (docker-compose up, seed corpus, open browser)
8. Environment Variables table (from .env.example)
9. Running Tests
10. Project Structure (from ARCHITECTURE.md)
11. Research Paper (brief mention of SciMem benchmark, link to arXiv when published)

Constraints:
- No bullet points where prose works better
- Every quantified claim must match actual benchmark output
- Judges read the README before running the code — make it count
```

**Acceptance test**: README renders correctly on GitHub. All quantified claims
match data/predictions.json output.

---

### Session H7 — Buffer + Submission (Day 7: July 5)
**Goal**: Submit before deadline with one hour to spare.
**When**: July 5 morning.

**DO NOT add new features on this day.**

Checklist:
- [ ] All 30+ pytest cases pass
- [ ] CI pipeline green on GitHub
- [ ] Docker build passes
- [ ] README complete with quantified results
- [ ] Demo video recorded (3 minutes, Loom)
- [ ] data/benchmark_pairs.json committed
- [ ] .env.example complete and accurate
- [ ] No API keys in any committed file
- [ ] Submission form filled out with GitHub repo URL and demo video link

**If anything is broken**: Fix the minimum to make it work. Do not refactor.
**If everything works**: Record the demo video. Do not add features.
