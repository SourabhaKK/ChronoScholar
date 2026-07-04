#!/usr/bin/env python
"""Pre-warm /compare cache for known demo pairs before presentation."""
import asyncio
import httpx

DEMO_PAIRS = [
    {
        "paper_id_a": "2504.19413",
        "paper_id_b": "2501.13956",
        "question": "What do these papers claim about graph vs vector memory?"
    },
    {
        "paper_id_a": "2504.19413",
        "paper_id_b": "2505.24478",
        "question": "What do these papers claim about RAG accuracy?"
    },
]

BASE_URL = "http://localhost:8000"


async def prewarm():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Verify server is ready
        r = await client.get(f"{BASE_URL}/ready")
        if not r.json().get("ready"):
            print("ERROR: server not ready — ingest papers first")
            return

        for pair in DEMO_PAIRS:
            print(f"Pre-warming: {pair['paper_id_a']} vs {pair['paper_id_b']}...")
            r = await client.post(f"{BASE_URL}/compare", json=pair)
            if r.status_code == 200:
                data = r.json()
                flat_len = len(data.get("flat_rag", {}).get("answer", ""))
                cs_len = len(data.get("chronoscholar", {}).get("answer", ""))
                label = data.get("chronoscholar", {}).get(
                    "contradiction", {}).get("label", "unknown")
                print(f"  flat_rag: {flat_len} chars")
                print(f"  chronoscholar: {cs_len} chars")
                print(f"  contradiction label: {label}")
                print(f"  CACHED")
            else:
                print(f"  ERROR: {r.status_code} — {r.text[:200]}")


if __name__ == "__main__":
    asyncio.run(prewarm())
