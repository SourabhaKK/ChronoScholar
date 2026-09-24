# ChronoScholar — SciMem Benchmark Specification

## Purpose

SciMem is a benchmark dataset for evaluating temporal belief revision in
AI agent memory systems. It tests whether a memory architecture can detect
when stored scientific claims are contradicted by incoming literature.

Two phases:
- Phase 1 (hackathon): 20 manually annotated paper pairs — used to report
  Precision/Recall in README and demo
- Phase 2 (research paper): 500+ pairs across 3 domains — publishable benchmark

## Schema

One JSON object per pair:

```json
{
  "pair_id": "uuid4 string",
  "paper_id_a": "XXXX.XXXXX",
  "paper_id_b": "XXXX.XXXXX",
  "title_a": "full title",
  "title_b": "full title",
  "date_a": "YYYY-MM",
  "date_b": "YYYY-MM",
  "ground_truth_label": "contradicts | supports | extends | unrelated",
  "contradiction_type": "direct | indirect | temporal_obsolescence | null",
  "claim_a": "one sentence central claim of paper A",
  "claim_b": "one sentence central claim of paper B",
  "annotation_confidence": "high | medium | low",
  "annotation_notes": "free text explaining the annotation decision",
  "domain": "agent_memory | graph_rag | temporal_reasoning"
}
```

## Contradiction Types

**direct**: Paper B explicitly contradicts a specific numerical or categorical
claim in Paper A. The contradiction is stated or immediately implied.
Example: Paper A reports 60% accuracy for graph-RAG; Paper B reports 92.5%
for the same task type.

**indirect**: Paper B's results imply Paper A's approach is inferior, but
neither paper directly references the other.
Example: Paper A proposes method X for temporal queries; Paper B proposes
method Y and shows superior results on the same benchmark without citing A.

**temporal_obsolescence**: Paper A's claim was accurate at publication but
has been superseded by Paper B's newer evidence. The claim was not wrong
when made — it is outdated.
Example: Paper A (2023) claims BERT is state-of-the-art for classification;
Paper B (2025) shows a newer model substantially outperforms BERT.

## Seed Pairs (Phase 1 — 20 pairs, annotate before hackathon starts)

### Domain: agent_memory

**Pair 001**
- A: 2504.19413 (Mem0, Apr 2025)
  Claim: "Graph memory adds minimal value over vector memory on LoCoMo benchmark"
- B: 2501.13956 (Zep/Graphiti, Jan 2025)
  Claim: "Temporal knowledge graph achieves 18.5% improvement over vector approaches on LongMemEval"
- Label: contradicts
- Type: direct
- Confidence: high
- Notes: Both papers evaluate graph vs vector memory. Mem0 minimises graph value;
  Zep demonstrates substantial gains. Different benchmarks (LoCoMo vs LongMemEval)
  but same research question. Direct contradiction on the core claim.

**Pair 002**
- A: 2504.19413 (Mem0, Apr 2025)
  Claim: "Selective memory with vector retrieval is sufficient for production AI agents"
- B: 2505.24478 (Cognee, May 2025)
  Claim: "Graph-RAG achieves 92.5% accuracy vs 60% for flat RAG on multi-hop queries"
- Label: contradicts
- Type: indirect
- Confidence: high
- Notes: Mem0 advocates vector-only approaches; Cognee demonstrates large gap
  favouring graph memory on multi-hop tasks. Indirect because Mem0 does not
  test multi-hop specifically.

**Pair 003**
- A: 2501.13956 (Zep/Graphiti, Jan 2025)
  Claim: "Temporal knowledge graph achieves 18.5% improvement over vector approaches"
- B: 2505.24478 (Cognee, May 2025)
  Claim: "Hybrid graph-vector memory achieves 92.5% on complex reasoning tasks"
- Label: supports
- Type: null
- Confidence: high
- Notes: Both papers agree graph-based memory outperforms vector-only.
  They support the same thesis from different angles.

**Pair 004**
- A: 2603.17244 (Kumiho, March 2026)
  Claim: "Existing graph memory systems lack formal belief revision correspondence"
- B: 2501.13956 (Zep/Graphiti, Jan 2025)
  Claim: "Graphiti provides temporal versioning with bitemporal edges"
- Label: extends
- Type: null
- Confidence: medium
- Notes: Kumiho extends Graphiti by adding formal belief revision semantics.
  Not a contradiction — Graphiti does not claim to have formal belief revision.

**Pair 005**
- A: Any pre-2024 paper claiming flat RAG is sufficient for QA
- B: 2504.16130 (GraphRAG, Edge et al., Apr 2024)
  Claim: "Graph-based RAG substantially outperforms flat RAG for global queries"
- Label: contradicts
- Type: temporal_obsolescence
- Confidence: high
- Notes: Pre-GraphRAG papers claiming RAG sufficiency are temporally obsolete.

[Annotate 15 more pairs from your corpus during June 26-28]

## Metrics to Report (Phase 1 — Hackathon README)

Run build_benchmark.py to generate predictions, compare against ground truth:

```
Contradiction Detection Performance (n=20 pairs):
- Precision:  X.XX  (TP / (TP + FP) on "contradicts" label)
- Recall:     X.XX  (TP / (TP + FN) on "contradicts" label)
- F1:         X.XX
- Accuracy:   X.XX  (all 4 labels)
- Mean confidence when correct:   X.XX
- Mean confidence when incorrect: X.XX
```

Target: Precision >= 0.70, F1 >= 0.65

## Metrics to Report (Phase 2 — Research Paper)

Across 500+ pairs, 3 contradiction types, 3 architectures:

| Architecture     | Precision | Recall | F1   | p50 Latency | p99 Latency |
|-----------------|-----------|--------|------|-------------|-------------|
| Flat RAG        | —         | —      | —    | —           | —           |
| Cognee Graph-RAG| —         | —      | —    | —           | —           |
| Graphiti TKG    | —         | —      | —    | —           | —           |

Breakdown by contradiction_type:
- direct: expected Cognee > Flat RAG
- indirect: expected largest gap (graph traversal required)
- temporal_obsolescence: expected Graphiti > Cognee (temporal edges)

## File Locations

```
scripts/
├── build_benchmark.py    # Generates predictions for all pairs
├── seed_corpus.py        # Ingests the seed paper list

data/
├── benchmark_pairs.json  # Ground truth (commit to repo)
├── predictions.json      # Generated by build_benchmark.py (gitignore)
└── seed_papers.json      # List of paper IDs to ingest (commit to repo)
```

## seed_papers.json format

```json
{
  "description": "ChronoScholar seed corpus — AI memory systems domain",
  "papers": [
    "2504.19413",
    "2501.13956",
    "2505.24478",
    "2603.17244",
    "2603.28533",
    "2601.17915",
    "2406.19764"
  ],
  "query_fallback": "agent memory knowledge graph temporal belief revision"
}
```
