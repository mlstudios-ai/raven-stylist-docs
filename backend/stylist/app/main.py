"""FastAPI app for the stylist orchestrator.

Phase 1: single ``POST /turn`` endpoint returning a JSON payload.
Streaming (SSE) is planned for Phase 4 once the frontend exists.

Run locally:
    uvicorn backend.stylist.app.main:app --reload --port 8002
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .orchestrator import handle_turn

app = FastAPI(
    title="Raven Stylist Orchestrator",
    description=(
        "Master agent. Receives chat turns from the frontend, routes to "
        "style / VTO sub-agents, returns chat replies plus optional "
        "outfit card and VTO image."
    ),
    version="0.1.0",
)

# Demo CORS — frontend will hit this from a different localhost port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Signal(BaseModel):
    kind: Literal["thumb_up", "thumb_down"]
    label: str = Field(..., description="Outfit label (or VTO scene label) being thumbed")
    reason: str | None = Field(None, description="Optional reason; defaults to the label")


class TurnRequest(BaseModel):
    session_id: str
    user_id: str
    message: str
    signals: list[Signal] | None = None


class OutfitCard(BaseModel):
    label: str
    summary: str
    pieces: list[dict[str, Any]]


class VtoBlock(BaseModel):
    image_b64: str
    image_mime: str
    description: str
    scene: dict[str, Any]


class TurnResponse(BaseModel):
    type: Literal["chat", "outfit", "vto", "outfit_vto", "clarification"]
    text: str
    outfit_card: OutfitCard | None = None
    vto: VtoBlock | None = None
    session_id: str
    turn_id: str


@app.post("/turn", response_model=TurnResponse)
def post_turn(req: TurnRequest) -> dict[str, Any]:
    signals = [s.model_dump() for s in req.signals] if req.signals else None
    return handle_turn(
        session_id=req.session_id,
        user_id=req.user_id,
        message=req.message,
        signals=signals,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
