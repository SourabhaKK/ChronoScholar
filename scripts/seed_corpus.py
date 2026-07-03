#!/usr/bin/env python
"""Ingest seed corpus into ChronoScholar knowledge graph."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


async def main(limit: int | None = None) -> None:
    from app.config import Settings
    from app.services.arxiv_service import ArxivService
    from app.services.cognee_service import CogneeService

    settings = Settings()
    arxiv_svc = ArxivService(request_delay=settings.arxiv_request_delay)
    cognee_svc = await CogneeService.create(settings)

    seed_path = Path("data/seed_papers.json")
    seed_data = json.loads(seed_path.read_text())
    paper_ids = seed_data["papers"]
    if limit:
        paper_ids = paper_ids[:limit]

    print(f"Fetching {len(paper_ids)} papers from arXiv...")
    papers = []
    for pid in paper_ids:
        paper = arxiv_svc.fetch_by_id(pid)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit))
