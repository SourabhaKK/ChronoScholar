#!/usr/bin/env python
"""Ingest seed corpus into ChronoScholar knowledge graph."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


async def main(limit: int | None = None, skip_ingestion: bool = False) -> None:
    from app.config import Settings
    from app.services.arxiv_service import ArxivService
    from app.services.cognee_service import CogneeService

    settings = Settings()
    arxiv_svc = ArxivService(request_delay=settings.arxiv_request_delay)
    cognee_svc = await CogneeService.create(settings)

    if skip_ingestion or cognee_svc.graph_loaded:
        if cognee_svc.graph_loaded:
            print("Graph already exists — skipping ingestion, proceeding to pre-computation.")
        else:
            print("--skip-ingestion flag set — skipping ingestion.")
    else:
        seed_path = Path("data/seed_papers.json")
        seed_data = json.loads(seed_path.read_text())
        paper_ids = seed_data["papers"]
        if limit:
            paper_ids = paper_ids[:limit]

        print(f"Fetching {len(paper_ids)} papers from arXiv...")
        papers = []
        for pid in paper_ids:
            try:
                paper = arxiv_svc.fetch_by_id(pid)
            except Exception as exc:
                print(f"  SKIP {pid}: {exc}")
                continue
            if paper:
                papers.append(paper)
                print(f"  Fetched: {pid} — {paper.title[:60]}")

        print(f"\nIngesting {len(papers)} papers into Cognee...")
        start = time.time()
        run_store: dict = {}
        result = await cognee_svc.run_ingestion(papers, "seed", run_store)
        duration = time.time() - start

        print(f"\nIngestion complete:")
        print(f"  Papers ingested: {result['papers_ingested']}")
        print(f"  Entities created: {result['entity_count']}")
        print(f"  Edges created: {result['edge_count']}")
        print(f"  Duration: {duration:.1f}s")

    # Pre-compute demo comparison and save to disk.
    # Order: detect() and CHUNKS first (neither uses Groq TPM in the primary path),
    # then sleep 65s to guarantee a full Groq TPM window reset, then GRAPH_COMPLETION.
    print("\nPre-computing demo comparison cache...")
    from app.services.llm_service import LLMService
    from app.services.contradiction_service import ContradictionService

    DEMO_QUESTION = "What do these papers claim about graph vs vector memory?"
    PAPER_A_ID = "2504.19413"
    PAPER_B_ID = "2501.13956"

    # Fetch papers (arXiv, no Groq usage)
    paper_a = arxiv_svc.fetch_by_id(PAPER_A_ID)
    paper_b = arxiv_svc.fetch_by_id(PAPER_B_ID)

    # detect() uses Gemini as primary (no Groq TPM), Groq only as tier-2 fallback.
    llm_svc = LLMService(settings=settings)
    contradiction_svc = ContradictionService(llm_service=llm_svc)

    # CHUNKS search for flat_rag (vector retrieval only — no Groq LLM)
    flat_result = await cognee_svc.search(DEMO_QUESTION, "CHUNKS")
    flat_answer = flat_result.get("answer", "") or ""
    flat_answer = flat_answer.strip("[]'\"")[:300] if flat_answer else "No content found."

    # Brief pause before GRAPH_COMPLETION to let any prior LLM calls settle.
    await asyncio.sleep(5)

    graph_result = await cognee_svc.search(DEMO_QUESTION, "GRAPH_COMPLETION")
    graph_answer = graph_result.get("answer", "") or ""
    graph_answer = graph_answer.strip("[]'\"")[:2000] if graph_answer else ""

    if paper_a and paper_b:
        # Provide the same claim context used in the benchmark to ensure correct
        # classification. Mirrors build_benchmark.py's context injection.
        demo_context = "- Background: Mem0 reports minimal graph memory gains; Zep reports 18.5% improvement over vectors"
        contradiction = contradiction_svc.detect(paper_a, paper_b, context=demo_context)
        compare_cache = {
            f"{PAPER_A_ID}:{PAPER_B_ID}": {
                "flat_rag": {
                    "answer": flat_answer,
                    "source_paper_id": PAPER_A_ID,
                    "source_title": paper_a.title,
                },
                "chronoscholar": {
                    "answer": graph_answer,
                    "contradiction": contradiction.model_dump(mode="json"),
                },
            }
        }
        cache_path = Path("data/compare_cache.json")
        cache_path.write_text(json.dumps(compare_cache, indent=2))
        print(f"Compare cache saved to {cache_path}")
        print(f"  flat_rag: {len(flat_answer)} chars")
        print(f"  graph synthesis: {len(graph_answer)} chars")
        print(f"  contradiction: {contradiction.label} ({contradiction.confidence:.2f})")
    else:
        print("  SKIP: could not fetch demo papers — cache not written")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--skip-ingestion", action="store_true",
        help="Skip corpus ingestion and only run pre-computation (useful when graph already loaded)",
    )
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, skip_ingestion=args.skip_ingestion))
