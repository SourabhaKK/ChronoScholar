import logging
import time

import arxiv

from app.schemas.paper import Paper

logger = logging.getLogger(__name__)


class ArxivService:
    def __init__(self, request_delay: float = 3.0) -> None:
        self.request_delay = request_delay

    def fetch(
        self,
        query: str,
        max_results: int = 50,
        domain_tag: str | None = None,
    ) -> list[Paper]:
        if domain_tag:
            query = f"{query} AND cat:{domain_tag}"
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers: list[Paper] = []
        for result in search.results():
            papers.append(self._parse_result(result))
            time.sleep(self.request_delay)
            if len(papers) >= max_results:
                break
        return papers

    def fetch_by_id(self, paper_id: str) -> Paper | None:
        search = arxiv.Search(id_list=[paper_id])
        results = list(search.results())
        if not results:
            return None
        return self._parse_result(results[0])

    @staticmethod
    def _parse_result(result: arxiv.Result) -> Paper:
        raw_id = result.entry_id.split("/abs/")[-1]
        clean_id = raw_id.split("v")[0]
        return Paper(
            paper_id=clean_id,
            title=result.title,
            abstract=result.summary,
            published_date=result.published.strftime("%Y-%m"),
            authors=[str(a) for a in result.authors],
            categories=list(result.categories),
            arxiv_url=f"https://arxiv.org/abs/{clean_id}",
        )
