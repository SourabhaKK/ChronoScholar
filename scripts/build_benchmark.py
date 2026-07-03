#!/usr/bin/env python
"""Run contradiction detection against ground truth benchmark pairs."""
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


async def main() -> None:
    from app.config import Settings
    from app.services.arxiv_service import ArxivService
    from app.services.contradiction_service import ContradictionService
    from app.services.llm_service import LLMService

    settings = Settings()
    arxiv_svc = ArxivService(request_delay=0.5)
    llm_svc = LLMService(settings=settings)
    contradiction_svc = ContradictionService(llm_service=llm_svc)

    pairs = json.loads(Path("data/benchmark_pairs.json").read_text())
    predictions = []
    tp = fp = fn = tn = 0

    for pair in pairs:
        paper_a = arxiv_svc.fetch_by_id(pair["paper_id_a"])
        paper_b = arxiv_svc.fetch_by_id(pair["paper_id_b"])
        if not paper_a or not paper_b:
            print(f"SKIP {pair['pair_id']}: paper not found on arXiv")
            continue

        result = contradiction_svc.detect(paper_a, paper_b)
        predicted = result.label
        actual = pair["ground_truth_label"]

        is_contradiction_pred = predicted == "contradicts"
        is_contradiction_actual = actual == "contradicts"

        if is_contradiction_pred and is_contradiction_actual:
            tp += 1
        elif is_contradiction_pred and not is_contradiction_actual:
            fp += 1
        elif not is_contradiction_pred and is_contradiction_actual:
            fn += 1
        else:
            tn += 1

        predictions.append({
            **pair,
            "predicted_label": predicted,
            "predicted_confidence": result.confidence,
            "detection_method": result.detection_method,
        })
        print(
            f"Pair {pair['pair_id']}: actual={actual}, predicted={predicted}, "
            f"conf={result.confidence:.2f}, method={result.detection_method}"
        )

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print(f"\nContradiction Detection Performance (n={len(predictions)} pairs):")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1:        {f1:.3f}")
    print(f"  TP={tp} FP={fp} FN={fn} TN={tn}")

    Path("data/predictions.json").write_text(json.dumps(predictions, indent=2))
    print(f"\nPredictions saved to data/predictions.json")


if __name__ == "__main__":
    asyncio.run(main())
