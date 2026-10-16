from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceFile(StrictModel):
    path: str
    origin_path: str | None = None
    sha256: str
    content: str


class Snapshot(StrictModel):
    id: str
    source_commit: str
    fixture_sha256: str
    files: list[SourceFile]


class ContextChunk(StrictModel):
    source_id: str
    path: str
    start_line: int
    end_line: int
    symbol: str
    content: str

    def formatted(self, snapshot_id: str) -> str:
        lines = self.content.splitlines()
        numbered = "\n".join(f"{self.start_line + i}: {line}" for i, line in enumerate(lines))
        return (
            f"SOURCE {self.source_id} | snapshot {snapshot_id} | "
            f"{self.path}:{self.start_line}-{self.end_line} | {self.symbol}\n{numbered}"
        )


class Candidate(ContextChunk):
    lexical_rank: int | None = None
    dense_rank: int | None = None
    fusion_score: float = 0
    rerank_score: float | None = None
    selected: bool = False
    selection_reason: str = ""


class RetrievalTrace(StrictModel):
    query: str
    snapshot_id: str
    source_commit: str
    index_id: str
    method: str
    embedding_model: str
    rerank_model: str | None
    rerank_status: str
    candidates: list[Candidate]
    supplied_context: list[ContextChunk]
    context_budget: int
    context_cost: int
    budget_unit: str = "UTF-8 bytes (conservative token bound, not measured model tokens)"
    latency_ms: int


class Citation(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class Diagnosis(StrictModel):
    outcome: Literal["diagnosis", "insufficient_evidence"]
    diagnosis: str = Field(min_length=10, max_length=4000)
    citations: list[Citation] = Field(max_length=8)
    observations: list[str] = Field(min_length=1, max_length=8)
    uncertainty: list[str] = Field(min_length=1, max_length=8)
    next_check: str = Field(min_length=5, max_length=1500)

    @model_validator(mode="after")
    def grounded_claim_requires_citation(self) -> "Diagnosis":
        if self.outcome == "diagnosis" and not self.citations:
            raise ValueError("A diagnosis requires at least one supplied source citation")
        return self


class InvestigationRequest(StrictModel):
    report: str | None = Field(default=None, min_length=10, max_length=4000)
