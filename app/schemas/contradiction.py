from typing import Literal

from pydantic import BaseModel, Field, model_validator

ContradictionLabel = Literal["contradicts", "supports", "extends", "unrelated"]
DetectionMethod = Literal["llm", "fallback"]


class ContradictionPair(BaseModel):
    pair_id: str
    paper_id_a: str
    paper_id_b: str
    label: ContradictionLabel
    confidence: float = Field(ge=0.0, le=1.0)
    claim_a: str
    claim_b: str
    explanation: str
    detection_method: DetectionMethod
    detected_at: str


class DetectRequest(BaseModel):
    paper_id_a: str = Field(min_length=1)
    paper_id_b: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_papers_differ(self) -> "DetectRequest":
        if self.paper_id_a == self.paper_id_b:
            raise ValueError("paper_id_a and paper_id_b must be different.")
        return self


class ContradictionResponse(BaseModel):
    total: int
    returned: int
    offset: int
    contradictions: list[ContradictionPair]
