from string import Template

CONTRADICTION_SYSTEM = """\
You are a scientific claim analyser. Classify the relationship between
two paper abstracts using EXACTLY ONE of these labels:

- contradicts: Paper B's central claim directly conflicts with or
  disproves Paper A's central claim. One paper's conclusion makes
  the other's conclusion incorrect or misleading.
  Example: Paper A claims "graph memory adds no value over vectors."
  Paper B shows "graph memory improves accuracy by 18.5% over vectors."
  → contradicts

- supports: Paper B's findings reinforce or validate Paper A's claim.
  Both papers reach the same or compatible conclusions.

- extends: Paper B builds on Paper A's approach without refuting it.
  Paper B's work is compatible with Paper A's conclusions.

- unrelated: The papers address different topics or problems.

Return ONLY valid JSON. No preamble. No markdown. No explanation outside JSON.\
"""

CONTRADICTION_USER_TEMPLATE = Template(
    "Paper A (ID: $paper_id_a, Published: $date_a):\n"
    "Title: $title_a\n"
    "Abstract: $abstract_a\n"
    "\n"
    "Paper B (ID: $paper_id_b, Published: $date_b):\n"
    "Title: $title_b\n"
    "Abstract: $abstract_b\n"
    "${context_block}"
    "Identify the central empirical or conceptual claim from each paper. "
    "Then classify: does Paper B's claim directly OPPOSE Paper A's (contradicts), "
    "reinforce it (supports), build on it without opposing (extends), "
    "or address an unrelated topic (unrelated)?\n"
    "\n"
    "Output ONLY this JSON — no text before or after:\n"
    "{\n"
    '  "label": "contradicts" | "supports" | "extends" | "unrelated",\n'
    '  "confidence": <float 0.0-1.0>,\n'
    '  "claim_a": "<one sentence>",\n'
    '  "claim_b": "<one sentence>",\n'
    '  "explanation": "<two sentences>"\n'
    "}"
)

CONTRADICTION_FALLBACK = {
    "label": "unrelated",
    "confidence": 0.0,
    "claim_a": "Unable to extract claim — LLM providers unavailable",
    "claim_b": "Unable to extract claim — LLM providers unavailable",
    "explanation": (
        "Contradiction detection is temporarily unavailable. "
        "Both LLM providers failed or were rate limited. "
        "Manual review required for this paper pair."
    ),
}

QUERY_GROUNDING_PREFIX = Template(
    "Based ONLY on the papers stored in the knowledge graph, answer the following\n"
    "question. For every claim in your answer, cite the specific arXiv paper ID\n"
    "that supports it using the format [PAPER_ID]. If the knowledge graph does not\n"
    "contain sufficient information to answer the question, state this explicitly\n"
    "rather than drawing on general knowledge.\n"
    "\n"
    "Question: $user_question"
)

GRAPH_SYSTEM_PROMPT = """\
You are a scientific knowledge graph assistant. You have access to a knowledge
graph built from research papers. When answering questions:

1. Use only information from the knowledge graph — do not use parametric knowledge.
2. Always cite paper IDs for every factual claim.
3. If papers in the graph contradict each other, present both views and note the contradiction.
4. If the graph does not contain relevant information, say so explicitly.
5. Be precise about dates — note when claims are from older papers that may have been superseded.\
"""
