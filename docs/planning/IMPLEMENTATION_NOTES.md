# ChronoScholar — Implementation Notes

## Cognee-Specific

### Installation
```bash
pip install cognee
```
Cognee has optional extras. For this project:
```bash
pip install "cognee[weaviate]"   # if using Weaviate vector backend
# OR default (uses local LanceDB + SQLite) — recommended for hackathon
pip install cognee
```

### Initialisation Pattern
Cognee must be configured before any operations. Do this once in lifespan:

```python
import cognee

async def lifespan(app: FastAPI):
    # Configure Cognee
    await cognee.config.set_llm_config({
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "api_key": settings.groq_api_key,
    })
    await cognee.config.set_vector_db_config({
        "vector_db_provider": "lancedb",
        "vector_db_url": settings.cognee_vector_db_path,
    })
    # Initialise graph database
    await cognee.prune.prune_system(metadata=False)  # Only on first run
    app.state.cognee_service = CogneeService(settings=settings)
    yield
    # Cleanup on shutdown
    await cognee.prune.prune_system(metadata=False)
```

### Custom Ontology — CRITICAL
Cognee's default entity extraction uses its built-in ontology.
To use the custom ontology (Paper, Claim, Method, Dataset, Author):

```python
from pydantic import BaseModel, Field
from cognee.modules.graph.utils import get_graph_engine

class PaperNode(BaseModel):
    """Represents a research paper in the knowledge graph."""
    paper_id: str = Field(description="arXiv paper ID")
    title: str = Field(description="Paper title")
    published_date: str = Field(description="Publication date YYYY-MM")

class ClaimNode(BaseModel):
    """A scientific claim extracted from a paper."""
    text: str = Field(description="The claim statement")
    paper_id: str = Field(description="Source paper ID")

class MethodNode(BaseModel):
    """A method, algorithm, or technique described in a paper."""
    name: str = Field(description="Method name")
    description: str = Field(description="Brief description")

# Pass graph_model to cognify
await cognee.cognify(documents, graph_model=PaperNode)
```

### Batch Ingestion — CRITICAL
Never call cognify() on 100 documents in a single call.
Batch in groups of 10–20 to avoid timeout and memory issues:

```python
async def run_ingestion(papers: list[Paper], run_id: str):
    batch_size = 15
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        documents = [
            {"text": f"{p.title}\n\n{p.abstract}", "metadata": p.model_dump()}
            for p in batch
        ]
        await cognee.add(documents)
        await cognee.cognify()  # cognify after each batch
        # Update progress
        progress = int(((i + batch_size) / len(papers)) * 80)
        update_run_status(run_id, min(progress, 80), "Building knowledge graph...")
```

### Search Types
```python
from cognee.api.v1.search import SearchType

# Use these — do not use string literals
SearchType.GRAPH_COMPLETION   # Multi-hop, LLM-assisted, slowest, most accurate
SearchType.SEMANTIC           # Vector similarity, fast, no graph traversal
SearchType.SUMMARIES          # Summary-level retrieval

# Usage
results = await cognee.search(
    query_text=question,
    query_type=SearchType.GRAPH_COMPLETION,
)
```

### cognify() Duration
Expected durations on standard laptop (RTX 4070 or CPU):
- 10 papers: 30–90 seconds
- 20 papers: 60–180 seconds
- 50 papers: 3–8 minutes
- 100 papers: 8–20 minutes

Always run in BackgroundTasks. Never block an HTTP handler.

### Graph Inspection (debugging)
```python
# Get graph stats after cognify
from cognee.infrastructure.databases.graph import get_graph_engine
graph_engine = await get_graph_engine()
nodes = await graph_engine.get_nodes()
edges = await graph_engine.get_edges()
print(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
```

---

## FastAPI Patterns

### Lifespan (correct pattern)
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.cognee_service = await CogneeService.create(settings)
    app.state.contradiction_service = ContradictionService(
        llm_service=LLMService(settings=settings)
    )
    app.state.run_store = {}  # In-memory run status store
    yield
    # Shutdown — nothing needed for SQLite-backed Cognee

def create_app() -> FastAPI:
    app = FastAPI(
        title="ChronoScholar",
        description="Temporally-aware research memory agent",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(ingest_router, tags=["ingestion"])
    app.include_router(query_router, tags=["query"])
    app.include_router(contradiction_router, tags=["contradictions"])
    app.include_router(graph_router, tags=["graph"])
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    return app
```

### Dependency Injection (correct pattern)
```python
# In app/dependencies.py
from fastapi import Request
from app.services.cognee_service import CogneeService
from app.services.contradiction_service import ContradictionService

def get_cognee_service(request: Request) -> CogneeService:
    return request.app.state.cognee_service

def get_contradiction_service(request: Request) -> ContradictionService:
    return request.app.state.contradiction_service

def get_run_store(request: Request) -> dict:
    return request.app.state.run_store

# In router
from fastapi import Depends
from app.dependencies import get_cognee_service

@router.post("/ingest", status_code=202)
async def ingest(
    body: PaperIngestRequest,
    background_tasks: BackgroundTasks,
    cognee: CogneeService = Depends(get_cognee_service),
    run_store: dict = Depends(get_run_store),
):
    run_id = str(uuid4())
    run_store[run_id] = {"status": "pending", "progress_percent": 0}
    background_tasks.add_task(run_ingestion, run_id, body, cognee, run_store)
    return {"run_id": run_id, "status": "running", "message": "..."}
```

### Background Task Pattern
```python
async def run_ingestion(
    run_id: str,
    request: PaperIngestRequest,
    cognee_service: CogneeService,
    run_store: dict,
):
    try:
        run_store[run_id]["status"] = "running"
        papers = await arxiv_service.fetch(request.query, request.max_papers)
        run_store[run_id]["progress_percent"] = 30
        result = await cognee_service.run_ingestion(papers, run_id, run_store)
        run_store[run_id].update({
            "status": "complete",
            "progress_percent": 100,
            **result.model_dump(),
        })
    except Exception as e:
        logger.error(f"Ingestion failed for run {run_id}: {e}")
        run_store[run_id]["status"] = "failed"
        run_store[run_id]["message"] = str(e)
```

---

## LLM Fault Tolerance Pattern

Copy the exact pattern from FinSight. Do not rewrite from scratch.

```python
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

class LLMService:
    MAX_RETRIES = 3
    RATE_LIMIT_RETRIES = 3

    def complete(self, prompt: str, fallback: str = "") -> str:
        # Tier 1: Primary provider with exponential backoff
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call_primary(prompt)
            except RateLimitError:
                break  # Jump to Tier 2 immediately
            except (ConnectionError, TimeoutError) as e:
                if attempt < self.MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    logger.warning(f"Attempt {attempt+1} failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"Primary provider exhausted after {self.MAX_RETRIES} attempts")

        # Tier 2: Fallback provider on rate limit
        for attempt in range(self.RATE_LIMIT_RETRIES):
            try:
                return self._call_fallback(prompt)
            except RateLimitError:
                delay = 5 * (2 ** attempt)
                logger.warning(f"Fallback rate limited, waiting {delay}s")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Fallback provider failed: {e}")
                break

        # Tier 3: Deterministic fallback — zero network calls
        logger.warning("All LLM providers exhausted. Returning deterministic fallback.")
        return fallback
```

---

## arXiv API

```python
import arxiv
import time

class ArxivService:
    def __init__(self, request_delay: float = 3.0):
        self.request_delay = request_delay  # arXiv ToS requirement

    def fetch(self, query: str, max_results: int = 50,
              domain_tag: str | None = None) -> list[Paper]:
        if domain_tag:
            query = f"{query} AND cat:{domain_tag}"

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for result in search.results():
            papers.append(self._parse_result(result))
            time.sleep(self.request_delay)  # Rate limiting
            if len(papers) >= max_results:
                break
        return papers

    @staticmethod
    def _parse_result(result: arxiv.Result) -> Paper:
        # Extract clean ID from URL: "http://arxiv.org/abs/2504.19413v1" → "2504.19413"
        raw_id = result.entry_id.split("/abs/")[-1]
        clean_id = raw_id.split("v")[0]  # Remove version suffix
        return Paper(
            paper_id=clean_id,
            title=result.title,
            abstract=result.summary,
            published_date=result.published.strftime("%Y-%m"),
            authors=[str(a) for a in result.authors],
            categories=list(result.categories),
            arxiv_url=f"https://arxiv.org/abs/{clean_id}",
        )
```

---

## Contradiction Detection Prompt Engineering

The JSON must parse cleanly every time. Enforce this:

```python
SYSTEM_PROMPT = """You are a scientific claim analyser.
Analyse the relationship between two research paper abstracts.
Return ONLY valid JSON. No preamble. No markdown. No code blocks.
No text before or after the JSON object."""

def build_prompt(paper_a: Paper, paper_b: Paper) -> str:
    return f"""Paper A (ID: {paper_a.paper_id}, Published: {paper_a.published_date}):
Title: {paper_a.title}
Abstract: {paper_a.abstract}

Paper B (ID: {paper_b.paper_id}, Published: {paper_b.published_date}):
Title: {paper_b.title}
Abstract: {paper_b.abstract}

Return exactly this JSON:
{{
  "label": "contradicts" or "supports" or "extends" or "unrelated",
  "confidence": <float 0.0-1.0>,
  "claim_a": "<one sentence — central claim of Paper A>",
  "claim_b": "<one sentence — central claim of Paper B>",
  "explanation": "<two sentences explaining the label>"
}}"""
```

Parsing with fallback:
```python
import json
from app.schemas.contradiction import ContradictionPair

FALLBACK_RESULT = {
    "label": "unrelated",
    "confidence": 0.0,
    "claim_a": "Unable to extract — LLM unavailable",
    "claim_b": "Unable to extract — LLM unavailable",
    "explanation": "Contradiction detection unavailable. Manual review required.",
}

def parse_llm_response(response: str, paper_a: Paper,
                       paper_b: Paper) -> ContradictionPair:
    try:
        # Strip any accidental markdown fences
        clean = response.strip().strip("```json").strip("```").strip()
        data = json.loads(clean)
        return ContradictionPair(
            paper_id_a=paper_a.paper_id,
            paper_id_b=paper_b.paper_id,
            detection_method="llm",
            **data,
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"LLM response parse failed: {e}. Using fallback.")
        return ContradictionPair(
            paper_id_a=paper_a.paper_id,
            paper_id_b=paper_b.paper_id,
            detection_method="fallback",
            **FALLBACK_RESULT,
        )
```

---

## pyvis Graph Visualisation

```python
from pyvis.network import Network

def build_graph_html(entities: list, edges: list) -> str:
    net = Network(height="600px", width="100%", bgcolor="#1a1a2e", font_color="white")

    # Node colours by type
    TYPE_COLOURS = {
        "Paper": "#4CAF50",
        "Claim": "#2196F3",
        "Method": "#FF9800",
        "Dataset": "#9C27B0",
        "Author": "#607D8B",
    }

    for entity in entities:
        colour = TYPE_COLOURS.get(entity.get("type", ""), "#AAAAAA")
        net.add_node(
            entity["id"],
            label=entity["label"][:40],  # Truncate long labels
            color=colour,
            title=entity.get("description", ""),
        )

    CONTRADICTION_COLOUR = "#F44336"
    DEFAULT_EDGE_COLOUR = "#666666"

    for edge in edges:
        colour = CONTRADICTION_COLOUR if edge["type"] == "contradicts" else DEFAULT_EDGE_COLOUR
        net.add_edge(
            edge["source"],
            edge["target"],
            label=edge["type"],
            color=colour,
        )

    net.set_options("""
    {
      "physics": {"stabilization": {"iterations": 100}},
      "interaction": {"hover": true, "tooltipDelay": 100}
    }
    """)
    return net.generate_html()
```

---

## MLflow Integration

```python
import mlflow

def log_ingestion_run(
    run_id: str,
    papers_ingested: int,
    entities_created: int,
    edges_created: int,
    cognify_duration: float,
    contradiction_pairs: int,
    llm_provider: str,
    arxiv_query: str,
    cognee_version: str,
):
    with mlflow.start_run(run_name=f"ingest_{run_id[:8]}"):
        mlflow.log_params({
            "llm_provider": llm_provider,
            "arxiv_query": arxiv_query,
            "cognee_version": cognee_version,
        })
        mlflow.log_metrics({
            "papers_ingested": papers_ingested,
            "entities_created": entities_created,
            "edges_created": edges_created,
            "cognify_duration_seconds": cognify_duration,
            "contradiction_pairs_detected": contradiction_pairs,
        })
```

---

## Docker Multi-Stage Build

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv export --no-dev > requirements.txt
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY scripts/ ./scripts/
RUN mkdir -p data mlflow_tracking

ENV PYTHONPATH=/app
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
```

---

## Common Failure Modes and Fixes

| Failure | Cause | Fix |
|---|---|---|
| cognify() hangs indefinitely | Batch too large | Reduce to 10 papers per batch |
| cognify() produces no edges | Default ontology used | Pass custom graph_model parameter |
| arXiv returns 403 | Rate limit exceeded | Increase ARXIV_REQUEST_DELAY to 5.0 |
| LLM returns markdown-wrapped JSON | Missing system prompt instruction | Add "No markdown code blocks" to system prompt |
| pyvis HTML not rendering | Static files not mounted | Verify app.mount("/static", ...) in main.py |
| Tests fail with import error on cognee | cognee not installed | pip install cognee in test env |
| Background task silently fails | Exception swallowed | Wrap entire background task in try/except and update run_store status |
| /ready returns 503 always | graph_loaded flag not set | Set app.state.cognee_service.graph_loaded = True after first cognify() |
