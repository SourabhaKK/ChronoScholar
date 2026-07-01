import json
import logging
from datetime import datetime, timezone
from itertools import combinations
from uuid import uuid4

from app.prompts import CONTRADICTION_FALLBACK, CONTRADICTION_USER_TEMPLATE
from app.schemas.contradiction import ContradictionPair
from app.schemas.paper import Paper
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def parse_llm_response(response: str, paper_a: Paper, paper_b: Paper) -> ContradictionPair:
    try:
        clean = response.strip().strip("```json").strip("```").strip()
        data = json.loads(clean)
        return ContradictionPair(
            pair_id=str(uuid4()),
            paper_id_a=paper_a.paper_id,
            paper_id_b=paper_b.paper_id,
            detection_method="llm",
            detected_at=datetime.now(timezone.utc).isoformat(),
            **data,
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.warning("LLM response parse failed: %s. Using fallback.", exc)
        return ContradictionPair(
            pair_id=str(uuid4()),
            paper_id_a=paper_a.paper_id,
            paper_id_b=paper_b.paper_id,
            detection_method="fallback",
            detected_at=datetime.now(timezone.utc).isoformat(),
            **CONTRADICTION_FALLBACK,
        )


class ContradictionService:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def detect(self, paper_a: Paper, paper_b: Paper) -> ContradictionPair:
        try:
            prompt = CONTRADICTION_USER_TEMPLATE.substitute(
                paper_id_a=paper_a.paper_id,
                date_a=paper_a.published_date,
                title_a=paper_a.title,
                abstract_a=paper_a.abstract,
                paper_id_b=paper_b.paper_id,
                date_b=paper_b.published_date,
                title_b=paper_b.title,
                abstract_b=paper_b.abstract,
            )
            response = self.llm_service.complete(
                prompt, fallback=json.dumps(CONTRADICTION_FALLBACK)
            )
            return parse_llm_response(response, paper_a, paper_b)
        except Exception as exc:
            logger.error("ContradictionService.detect failed unexpectedly: %s", exc)
            return ContradictionPair(
                pair_id=str(uuid4()),
                paper_id_a=paper_a.paper_id,
                paper_id_b=paper_b.paper_id,
                detection_method="fallback",
                detected_at=datetime.now(timezone.utc).isoformat(),
                **CONTRADICTION_FALLBACK,
            )

    def detect_batch(self, papers: list[Paper]) -> list[ContradictionPair]:
        results: list[ContradictionPair] = []
        for paper_a, paper_b in combinations(papers, 2):
            results.append(self.detect(paper_a, paper_b))
        return results
