"""Structured claim format shared by the bull and bear agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    statement: str
    evidence: str
    source_url: str = Field(description="URL, or 'sec-edgar:<accession>' for EDGAR figures")
    source_date: str = Field(description="Publication or filing date, YYYY-MM-DD")
    confidence: Literal["low", "medium", "high"]
    would_change_mind: str
    rebuts: str | None = Field(default=None, description="Id of the opponent claim this answers")
    id: str = ""


class ClaimSet(BaseModel):
    claims: list[Claim]


SUBMIT_CLAIMS = "submit_claims"

_CLAIM_PROPERTIES = {
    "statement": {"type": "string"},
    "evidence": {"type": "string"},
    "source_url": {"type": "string"},
    "source_date": {"type": "string"},
    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    "would_change_mind": {"type": "string"},
    "rebuts": {"type": ["string", "null"]},
}

SUBMIT_CLAIMS_TOOL = {
    "name": SUBMIT_CLAIMS,
    "description": "Submit your final list of claims. Call this exactly once, when your research is done.",
    "strict": True,
    "eager_input_streaming": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": _CLAIM_PROPERTIES,
                    "required": list(_CLAIM_PROPERTIES),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    },
}
