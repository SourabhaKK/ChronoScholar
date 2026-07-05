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
            search_type: SearchType | str = _mode_map.get(mode, SearchType.GRAPH_COMPLETION)
        except ImportError:
            search_type = mode

        results = await cognee.search(question, query_type=search_type)  # type: ignore[arg-type]
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

        net = Network(height="100vh", width="100%", bgcolor="#080c14", font_color="#8a9ab5")

        color_map = {
            "Paper": "#5b8dee", "Claim": "#e53e3e", "Method": "#38a169",
            "Dataset": "#ed8936", "Author": "#9f7aea", "Entity": "#2a3f6e",
        }

        if self.graph_loaded:
            try:
                from cognee.infrastructure.databases.graph import get_graph_engine

                graph_engine = await get_graph_engine()
                nodes, edges = await graph_engine.get_graph_data()

                added_ids: set[str] = set()
                for node in list(nodes)[:250]:
                    nid = str(getattr(node, "id", id(node)))
                    name = (
                        getattr(node, "name", None)
                        or getattr(node, "label", None)
                        or getattr(node, "description", None)
                        or nid[:12]
                    )
                    ntype = str(getattr(node, "type", getattr(node, "node_type", "Entity")))
                    color = color_map.get(ntype, "#2a3f6e")
                    net.add_node(nid, label=str(name)[:24], title=f"{ntype}: {name}", color=color, size=16)
                    added_ids.add(nid)

                for edge in list(edges)[:600]:
                    src = str(getattr(edge, "source_node_id", ""))
                    dst = str(getattr(edge, "target_node_id", ""))
                    rel = str(getattr(edge, "relationship_type", getattr(edge, "type", "")))
                    if src in added_ids and dst in added_ids:
                        net.add_edge(src, dst, title=rel, color="#4a6fa5")

            except Exception as exc:
                logger.warning("Graph visualisation could not load data: %s", exc)
                net.add_node("msg", label="Graph data unavailable", color="#e53e3e", size=20)

        try:
            import json as _json
            net.set_options(_json.dumps({
                "nodes": {
                    "shape": "dot", "size": 16, "borderWidth": 1,
                    "font": {"size": 13, "color": "#e8edf5", "strokeWidth": 2, "strokeColor": "#080c14"},
                },
                "edges": {
                    "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
                    "color": {"color": "#4a6fa5", "highlight": "#5b8dee", "opacity": 0.7},
                    "width": 1.5,
                    "smooth": {"type": "continuous"},
                },
                "physics": {
                    "stabilization": {"iterations": 150, "fit": True},
                    "barnesHut": {"gravitationalConstant": -5000, "springLength": 100, "springConstant": 0.04},
                },
                "interaction": {"hover": True, "tooltipDelay": 100, "navigationButtons": True},
            }))
        except Exception:
            pass

        html = net.generate_html()
        dark_override = """
  <style>
    body, html { background-color:#080c14 !important; color:#e8edf5 !important; margin:0; padding:0; }
    #mynetwork { background-color:#0e1420 !important; border:1px solid #1e2d4a !important;
                 border-radius:0; width:100% !important; height:100vh !important; }
  </style>
"""
        html = html.replace("</head>", dark_override + "</head>")
        return html
