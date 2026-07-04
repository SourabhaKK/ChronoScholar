import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.routers import contradictions, graph, ingest, query
from app.services.cognee_service import CogneeService
from app.services.contradiction_service import ContradictionService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        # hasattr guards let test fixtures pre-inject mocks before startup
        if not hasattr(application.state, "cognee_service"):
            application.state.cognee_service = await CogneeService.create(settings)
        if not hasattr(application.state, "contradiction_service"):
            llm_service = LLMService(settings)
            application.state.contradiction_service = ContradictionService(llm_service)
        if not hasattr(application.state, "arxiv_service"):
            from app.services.arxiv_service import ArxivService
            application.state.arxiv_service = ArxivService(
                request_delay=settings.arxiv_request_delay
            )
        if not hasattr(application.state, "run_store"):
            application.state.run_store = {"contradictions": []}
        import json as _json
        from datetime import UTC, datetime
        from pathlib import Path
        from app.schemas.contradiction import ContradictionPair
        predictions_path = Path("data/predictions.json")
        if predictions_path.exists():
            try:
                raw = _json.loads(predictions_path.read_text())
                pairs: list[ContradictionPair] = []
                for entry in raw:
                    # Benchmark output uses predicted_label/predicted_confidence;
                    # server cache uses label/confidence. Normalise either format.
                    label = entry.get("label") or entry.get("predicted_label") or "unrelated"
                    confidence = entry.get("confidence") or entry.get("predicted_confidence") or 0.0
                    # Only include valid labels
                    if label not in ("contradicts", "supports", "extends", "unrelated"):
                        label = "unrelated"
                    pairs.append(ContradictionPair(
                        pair_id=entry.get("pair_id", ""),
                        paper_id_a=entry.get("paper_id_a", ""),
                        paper_id_b=entry.get("paper_id_b", ""),
                        label=label,
                        confidence=float(confidence),
                        claim_a=entry.get("claim_a") or entry.get("notes") or "",
                        claim_b=entry.get("claim_b") or "",
                        explanation=entry.get("explanation") or entry.get("annotation_notes") or "",
                        detection_method=entry.get("detection_method", "llm"),
                        detected_at=entry.get("detected_at") or datetime.now(UTC).isoformat(),
                    ))
                application.state.run_store["contradictions"] = pairs
                logger.info("Loaded %d cached contradictions", len(pairs))
            except Exception as exc:
                logger.warning("Could not load cached contradictions: %s", exc)
        logger.info("ChronoScholar startup complete")
        yield
        logger.info("ChronoScholar shutdown")

    app = FastAPI(
        title="ChronoScholar",
        description="Temporally-aware research memory agent with Cognee knowledge graph",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.get("/ready", tags=["health"])
    async def ready() -> dict:
        cognee_svc: CogneeService = app.state.cognee_service
        stats = await cognee_svc.get_stats()
        return {
            "ready": cognee_svc.graph_loaded,
            "graph_loaded": cognee_svc.graph_loaded,
            **stats,
        }

    app.include_router(ingest.router)
    app.include_router(query.router)
    app.include_router(contradictions.router)
    app.include_router(graph.router)

    try:
        app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
    except RuntimeError:
        logger.warning("Static directory not found — UI not available")

    return app
