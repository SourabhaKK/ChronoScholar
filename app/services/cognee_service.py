import logging
from pathlib import Path

from app.config import Settings
from app.schemas.paper import Paper

logger = logging.getLogger(__name__)


class CogneeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.graph_loaded: bool = False
        self._paper_count: int = 0

    @classmethod
    async def create(cls, settings: Settings) -> "CogneeService":
        instance = cls(settings)
        # Cognee 1.2.2 reads LLM_MODEL, LLM_API_KEY, EMBEDDING_* from env directly.
        # set_llm_config() with a "provider" key is rejected in 1.2.x — skip it.
        try:
            import cognee

            # Force Cognee to use project-relative paths, not venv internals.
            # data_root_directory / system_root_directory are sync in 1.2.2.
            # Fall back to data/ when cognee_db_path is unset.
            db_path = settings.cognee_db_path or "data/cognee.db"
            data_path = Path(db_path).parent.absolute()
            data_path.mkdir(parents=True, exist_ok=True)
            cognee.config.data_root_directory(str(data_path))
            cognee.config.system_root_directory(str(data_path / "cognee_system"))
            # Auto-detect existing graph: search the Cognee system dir for .lbug files.
            # Cognee 1.2.2 stores the Ladybug graph at
            # <system_root>/databases/{user_uuid}/{graph_uuid}.lbug regardless of
            # data_root_directory(), so we scan both the project path and the package
            # default (.venv/…/.cognee_system) rather than relying on the async engine.
            search_roots = [data_path / "cognee_system", Path(cognee.__file__).parent / ".cognee_system"]
            lbug_found = any(p.exists() and list(p.rglob("*.lbug")) for p in search_roots)
            if lbug_found:
                # Scan for orphaned processes holding the Ladybug DB file locked.
                try:
                    import os

                    import psutil

                    graph_db_path: str | None = None
                    for root, _dirs, files in os.walk("data/cognee_system"):
                        for f in files:
                            if "ladybug" in f.lower() or f.endswith(".lbug"):
                                graph_db_path = os.path.join(root, f)
                                break
                        if graph_db_path:
                            break

                    if graph_db_path:
                        current_pid = os.getpid()
                        for proc in psutil.process_iter(["pid", "open_files"]):
                            try:
                                for file_info in proc.info.get("open_files") or []:
                                    if graph_db_path in file_info.path and proc.pid != current_pid:
                                        logger.warning(
                                            "Stale lock on graph DB held by PID %d — "
                                            "kill this process before running demo",
                                            proc.pid,
                                        )
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                except ImportError:
                    logger.debug("psutil not available — skipping orphan lock detection")

                instance.graph_loaded = True
                logger.info("Existing graph detected via .lbug file — graph_loaded=True")
        except ImportError as exc:
            logger.warning("Cognee import failed: %s", exc)
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
            for p in batch:
                await cognee.add(f"{p.title}\n\n{p.abstract}")
            await cognee.cognify()
            self._paper_count += len(batch)

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

            # Build map lazily from the enum itself so missing members never raise AttributeError.
            _mode_map: dict[str, SearchType] = {m.name: m for m in SearchType}
            search_type: object = _mode_map.get(mode, SearchType.GRAPH_COMPLETION)
        except ImportError:
            search_type = mode

        results = await cognee.search(question, query_type=search_type)
        logger.info(
            "search: mode=%s, graph_loaded=%s, result_length=%d",
            mode, self.graph_loaded, len(str(results))
        )
        if hasattr(results, "__len__") and len(results) == 0:
            logger.warning("search: empty results — fallback path likely used")

        # CHUNKS returns a list of data objects; extract readable text rather than str()-ing
        # the whole list (which produces {'id': '...', 'text': '...'} noise in the UI).
        if mode == "CHUNKS" and results:
            items = results if isinstance(results, list) else [results]
            texts: list[str] = []
            for obj in items:
                txt = (
                    getattr(obj, "text", None)
                    or getattr(obj, "content", None)
                    or getattr(obj, "chunk_text", None)
                    or (obj.get("text") if isinstance(obj, dict) else None)
                    or (obj.get("content") if isinstance(obj, dict) else None)
                    or (obj.get("chunk_text") if isinstance(obj, dict) else None)
                )
                if txt:
                    texts.append(str(txt))
            answer = " ".join(texts) if texts else str(results)
        else:
            answer = str(results) if results else ""

        return {
            "answer": answer,
            "sources": [],
            "latency_ms": 0,
        }

    async def get_stats(self) -> dict:
        if not self.graph_loaded:
            return {"paper_count": 0, "entity_count": 0, "edge_count": 0}
        try:
            from cognee.infrastructure.databases.graph import get_graph_engine

            graph_engine = await get_graph_engine()
            nodes, edges = await graph_engine.get_graph_data()
            return {
                "paper_count": self._paper_count,
                "entity_count": len(nodes),
                "edge_count": len(edges),
                "node_types": {},
                "edge_types": {},
            }
        except Exception as exc:
            logger.warning("Could not get graph stats: %s", exc)
            return {"paper_count": self._paper_count, "entity_count": 0, "edge_count": 0}

    async def get_graph_html(self) -> str:
        from pyvis.network import Network

        net = Network(height="600px", width="100%")
        return net.generate_html()
