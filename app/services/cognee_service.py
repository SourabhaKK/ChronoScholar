import logging

from app.config import Settings
from app.schemas.paper import Paper

logger = logging.getLogger(__name__)


class CogneeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.graph_loaded: bool = False

    @classmethod
    async def create(cls, settings: Settings) -> "CogneeService":
        instance = cls(settings)
        try:
            import cognee

            await cognee.config.set_llm_config({
                "provider": settings.llm_provider,
                "api_key": settings.groq_api_key,
            })
        except Exception as exc:
            logger.warning("Cognee config skipped (may be offline): %s", exc)
        return instance

    async def run_ingestion(
        self,
        papers: list[Paper],
        run_id: str,
        run_store: dict,
    ) -> dict:
        import cognee

        if not papers:
            if run_id in run_store:
                run_store[run_id]["progress_percent"] = 100
            return {"papers_ingested": 0, "entity_count": 0, "edge_count": 0}

        batch_size = self.settings.cognee_batch_size
        total_batches = max(1, (len(papers) + batch_size - 1) // batch_size)

        for batch_idx in range(0, len(papers), batch_size):
            batch = papers[batch_idx : batch_idx + batch_size]
            documents = [
                {"text": f"{p.title}\n\n{p.abstract}", "metadata": p.model_dump()}
                for p in batch
            ]
            await cognee.add(documents)
            await cognee.cognify()

            completed = (batch_idx // batch_size) + 1
            progress = int((completed / total_batches) * 80)
            if run_id in run_store:
                run_store[run_id]["progress_percent"] = progress

        self.graph_loaded = True
        if run_id in run_store:
            run_store[run_id]["progress_percent"] = 100

        return {"papers_ingested": len(papers), "entity_count": 0, "edge_count": 0}

    async def search(self, question: str, mode: str = "GRAPH_COMPLETION") -> dict:
        import cognee

        try:
            from cognee.api.v1.search import SearchType

            _mode_map: dict[str, SearchType] = {
                "GRAPH_COMPLETION": SearchType.GRAPH_COMPLETION,
                "SEMANTIC": SearchType.SEMANTIC,
            }
            search_type: object = _mode_map.get(mode, SearchType.GRAPH_COMPLETION)
        except (ImportError, AttributeError):
            search_type = mode

        results = await cognee.search(question, query_type=search_type)
        return {
            "answer": str(results) if results else "",
            "sources": [],
            "latency_ms": 0,
        }

    def get_stats(self) -> dict:
        return {
            "paper_count": 0,
            "entity_count": 0,
            "edge_count": 0,
        }

    async def get_graph_html(self) -> str:
        from pyvis.network import Network

        net = Network(height="600px", width="100%")
        return net.generate_html()
