# ChronoScholar — API Contracts

All request and response bodies are JSON.
All responses are Pydantic v2 validated — no raw dicts, no raw strings.
All timestamps are ISO 8601 format.
All paper IDs are clean arXiv format: "XXXX.XXXXX" — no "arxiv:" prefix, no URL.

---

## Health & Readiness

### GET /health
No request body.

Response 200:
```json
{
  "status": "ok",
  "timestamp": "2026-06-29T10:23:45.123Z"
}
```

### GET /ready
No request body.

Response 200 (graph loaded and ready):
```json
{
  "ready": true,
  "graph_loaded": true,
  "paper_count": 47,
  "entity_count": 312,
  "edge_count": 891
}
```

Response 503 (graph still initialising):
```json
{
  "ready": false,
  "graph_loaded": false,
  "paper_count": 0,
  "entity_count": 0,
  "edge_count": 0
}
```

---

## Ingestion

### POST /ingest
Request:
```json
{
  "query": "agent memory knowledge graph",
  "max_papers": 50,
  "domain_tag": "cs.AI"
}
```
Field constraints:
- query: non-empty string, max 200 chars
- max_papers: integer, 1–100, default 50
- domain_tag: optional, must be valid arXiv category if provided

Response 202 (accepted, running in background):
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "message": "Ingestion started. Poll /ingest/status/{run_id} for progress."
}
```

Response 422 (validation error — standard FastAPI format):
```json
{
  "detail": [
    {
      "loc": ["body", "max_papers"],
      "msg": "Input should be less than or equal to 100",
      "type": "less_than_equal"
    }
  ]
}
```

### GET /ingest/status/{run_id}
No request body.

Response 200:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress_percent": 72,
  "papers_fetched": 36,
  "papers_total": 50,
  "message": "Building knowledge graph...",
  "started_at": "2026-06-29T10:23:45.123Z",
  "completed_at": null
}
```

Status values: "pending" | "running" | "complete" | "failed"

Response 200 (complete):
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "complete",
  "progress_percent": 100,
  "papers_fetched": 47,
  "papers_total": 50,
  "entities_created": 312,
  "edges_created": 891,
  "contradiction_pairs_detected": 14,
  "cognify_duration_seconds": 183.4,
  "message": "Ingestion complete.",
  "started_at": "2026-06-29T10:23:45.123Z",
  "completed_at": "2026-06-29T10:26:48.901Z"
}
```

Response 404 (run_id not found):
```json
{
  "detail": "Run ID not found."
}
```

---

## Query

### POST /query
Request:
```json
{
  "question": "What is the current consensus on graph vs vector memory?",
  "search_mode": "GRAPH_COMPLETION",
  "max_results": 5
}
```
Field constraints:
- question: non-empty string, max 500 chars
- search_mode: "GRAPH_COMPLETION" | "SEMANTIC" | "HYBRID", default "GRAPH_COMPLETION"
- max_results: integer, 1–20, default 5

Response 200:
```json
{
  "answer": "Based on papers in the knowledge graph, the consensus is...",
  "sources": [
    {
      "paper_id": "2504.19413",
      "title": "Mem0: Building production-ready AI agents",
      "published_date": "2025-04",
      "relevance_score": 0.91,
      "excerpt": "Selective memory achieves 66.9% accuracy..."
    },
    {
      "paper_id": "2501.13956",
      "title": "Zep: A temporal knowledge graph architecture",
      "published_date": "2025-01",
      "relevance_score": 0.88,
      "excerpt": "Our temporal graph achieves 18.5% improvement..."
    }
  ],
  "search_mode_used": "GRAPH_COMPLETION",
  "latency_ms": 1243,
  "graph_ready": true
}
```

Response 503 (graph not yet loaded):
```json
{
  "detail": "Knowledge graph not ready. Ingest papers first."
}
```

---

## Contradiction Detection

### POST /detect
Request:
```json
{
  "paper_id_a": "2504.19413",
  "paper_id_b": "2501.13956"
}
```
Field constraints:
- paper_id_a: non-empty string, arXiv ID format
- paper_id_b: non-empty string, arXiv ID format, must differ from paper_id_a

Response 200:
```json
{
  "pair_id": "7f3c9a1e-8b2d-4e5f-a6c7-d8e9f0a1b2c3",
  "paper_id_a": "2504.19413",
  "paper_id_b": "2501.13956",
  "label": "contradicts",
  "confidence": 0.87,
  "claim_a": "Graph memory adds minimal value over vector memory on LoCoMo benchmark",
  "claim_b": "Temporal knowledge graph achieves 18.5% improvement over vector approaches",
  "explanation": "Paper A minimises the value of graph memory, reporting only marginal gains. Paper B demonstrates substantial improvements from graph-based temporal memory on overlapping evaluation tasks.",
  "detection_method": "llm",
  "detected_at": "2026-06-29T10:27:15.443Z"
}
```

label values: "contradicts" | "supports" | "extends" | "unrelated"
detection_method values: "llm" | "fallback"

Response 404 (paper ID not found in arXiv):
```json
{
  "detail": "Paper 0000.00000 not found on arXiv."
}
```

Response 422 (same paper ID submitted twice):
```json
{
  "detail": "paper_id_a and paper_id_b must be different."
}
```

### GET /contradictions
Query parameters:
- min_confidence: float 0.0–1.0, default 0.7
- label: optional filter, one of "contradicts" | "supports" | "extends" | "unrelated"
- limit: integer 1–100, default 20
- offset: integer >= 0, default 0

Response 200:
```json
{
  "total": 14,
  "returned": 14,
  "offset": 0,
  "contradictions": [
    {
      "pair_id": "...",
      "paper_id_a": "2504.19413",
      "paper_id_b": "2501.13956",
      "label": "contradicts",
      "confidence": 0.87,
      "claim_a": "...",
      "claim_b": "...",
      "explanation": "...",
      "detection_method": "llm",
      "detected_at": "2026-06-29T10:27:15.443Z"
    }
  ]
}
```

---

## Graph

### GET /graph/visualise
No request body.
Response: text/html — pyvis-generated force-directed graph
Response 503 if graph not loaded.

### GET /graph/stats
No request body.

Response 200:
```json
{
  "paper_count": 47,
  "entity_count": 312,
  "edge_count": 891,
  "node_types": {
    "Paper": 47,
    "Claim": 198,
    "Method": 43,
    "Dataset": 24
  },
  "edge_types": {
    "contradicts": 14,
    "supports": 67,
    "extends": 112,
    "invalidates": 8,
    "replicates": 23,
    "authored_by": 667
  }
}
```

---

## Error Response Format (all errors)

All non-2xx responses use this structure:
```json
{
  "detail": "Human-readable error message."
}
```

For validation errors, FastAPI's standard 422 format is used (list of field errors).
