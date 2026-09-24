# ChronoScholar — Claude Code Working Instructions

## Project Goal
Build a temporally-aware research memory agent that detects when stored
scientific beliefs are contradicted by incoming literature, using Cognee's
hybrid graph-vector memory layer.

## Hackathon Context
- Event: WeMakeDevs x Cognee "The Hangover Part AI" hackathon
- Hackathon brief received: June 26, 2026
- Hackathon runs: June 29 – July 5, 2026
- Judging criteria (in order of weight):
    1. Depth of Cognee memory lifecycle API usage
    2. UX polish and intuitiveness
    3. Clarity of demo, README, and submission
- Hard submission deadline: July 5, 2026

## What This System Does
1. Ingests arXiv papers via the arxiv Python library
2. Builds a knowledge graph using Cognee with a custom ontology
3. Detects contradictions between stored claims and new papers
4. Answers multi-hop queries using GRAPH_COMPLETION search mode
5. Exposes everything via FastAPI with a minimal HTML/JS frontend
6. Logs every ingestion run to MLflow for experiment tracking

## Technology Stack (DO NOT deviate without asking)
- Memory layer: Cognee (cognee Python package)
- API: FastAPI + Pydantic v2
- LLM provider: Groq (primary), Gemini (fallback), deterministic fallback (no network)
- Containerisation: Docker multi-stage build
- CI/CD: GitHub Actions
- Testing: pytest with TDD approach — tests written before implementation
- Experiment tracking: MLflow (SQLite-backed)
- Frontend: Vanilla HTML/JS served by FastAPI (NO React, NO Node, NO npm)
- Graph visualisation: pyvis (generates static HTML)
- Python package manager: uv or pip (no poetry)

## Architecture Constraints (ENFORCE THESE)
- All Cognee operations go through a single CogneeService wrapper class
- FastAPI lifespan pattern for model/graph loading — NOT startup/shutdown events
- Pydantic v2 for ALL request/response schemas — no raw dicts at API boundary
- Three-tier fault tolerance on ALL LLM calls:
    Tier 1: Primary provider (Groq) with exponential backoff (3 attempts, 2^n seconds)
    Tier 2: On rate limit (429), switch to Gemini with backoff (5 * 2^n seconds)
    Tier 3: Deterministic fallback — valid output, zero network calls
- Provider switching via single LLM_PROVIDER environment variable — no code changes
- Background tasks for cognify() — never block the HTTP request thread
- All logging via Python logging module — no print() statements anywhere
- No bare except clauses — always catch specific exceptions

## Custom Cognee Ontology (CRITICAL — do not use Cognee defaults)
Node types: Paper, Claim, Method, Dataset, Author
Edge types: contradicts, supports, extends, invalidates, replicates, authored_by

## File Structure
See ARCHITECTURE.md for the complete directory tree.
Do not create files outside the structure defined there without asking.

## Environment Variables
See .env.example — never hardcode keys or paths.

## TDD Approach
See TESTING_STRATEGY.md — tests are written before implementation.
The session order in SESSIONS.md must be followed.
No implementation file is created until its corresponding test file is written.

## What Claude Code Must NEVER Do
- Add LangChain or LlamaIndex as dependencies
- Create any React component or npm/yarn/pnpm build step
- Create Jupyter notebooks in the production codebase
- Use print() for logging
- Use bare except clauses
- Hardcode API keys, URLs, or file paths
- Deviate from the directory structure in ARCHITECTURE.md
- Create files not specified in ARCHITECTURE.md without asking
- Skip writing tests before implementation
- Use cognee.add() with raw strings for batch ingestion — use document path
- Call cognee.cognify() synchronously in an HTTP request handler
- Import from langchain, llama_index, or haystack

## Commit Protocol (MANDATORY)
Every TDD cycle produces exactly 2-3 commits: RED then GREEN then REFACTOR.
Never combine RED and GREEN into one commit.
Always run the full test suite before each commit and include the pass/fail
count in the commit message body if it differs from the subject line count.
Commit messages follow: type(scope): STATE — description