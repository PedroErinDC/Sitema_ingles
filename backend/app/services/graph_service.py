from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

import graphrag as legacy_graphrag

from ..db_models import ContentItem


def graph_stats() -> dict[str, int]:
    graph = legacy_graphrag.load_graph()
    return {"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges()}


def index_content(session: Session, content_ids: list[int], llm_model: str) -> dict[str, int]:
    if not content_ids:
        return {"indexed": 0, **graph_stats()}

    stmt = select(ContentItem).where(ContentItem.id.in_(content_ids)).order_by(ContentItem.created_at.desc())
    items = list(session.scalars(stmt).all())
    nodes = edges = 0
    for item in items:
        if item.text_en.strip():
            nodes, edges = legacy_graphrag.index_material(item.text_en, item.source, llm_model)
    return {"indexed": len(items), "nodes": nodes, "edges": edges}


def query_graph(question: str, llm_model: str, hops: int) -> str:
    return legacy_graphrag.query(question, llm_model, hops=hops)
