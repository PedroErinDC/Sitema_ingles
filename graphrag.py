"""
graphrag.py - GraphRAG local para el sistema de aprendizaje.

Construye un grafo de conocimiento desde transcripciones y lo consulta
con embeddings + un LLM local.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import networkx as nx

import models as M


GRAPH_PATH = Path("data/graph.json")
EMB_PATH = Path("data/graph_embeddings.json")

_EMB = {"model": None}


def _embedder():
    if _EMB["model"] is None:
        from sentence_transformers import SentenceTransformer

        _EMB["model"] = SentenceTransformer("BAAI/bge-m3")
    return _EMB["model"]


def _embed(texts: list[str]) -> list[list[float]]:
    return _embedder().encode(texts, normalize_embeddings=True).tolist()


EXTRACT_PROMPT = """Eres un extractor de conocimiento para aprender ingles.
Del TEXTO en ingles extrae entidades y relaciones.

Tipos de entidad:
- WORD: palabra o vocabulario clave en ingles, en forma base.
- GRAMMAR: regla o estructura.
- TOPIC: tema del que trata el texto.
- PHRASE: expresion o colocacion util.

Devuelve solo JSON valido, sin texto extra, con esta forma exacta:
{{"entities":[{{"name":"...","type":"WORD|GRAMMAR|TOPIC|PHRASE","description":"breve en espanol"}}],
"relations":[{{"source":"...","target":"...","description":"como se relacionan"}}]}}

TEXTO:
\"\"\"{chunk}\"\"\"
JSON:"""


def chunk_text(text: str, size: int = 220, overlap: int = 40) -> list[str]:
    """Trocea un texto por palabras."""
    words = text.split()
    out = []
    index = 0
    step = max(1, size - overlap)
    while index < len(words):
        out.append(" ".join(words[index : index + size]))
        index += step
    return out


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    match = re.search(r"\{.*\}", raw, re.S)
    return json.loads(match.group(0) if match else raw)


def _norm(name: str) -> str:
    return name.strip().lower()


def build_graph(text: str, source: str, llm_model: str, g: nx.Graph | None = None) -> nx.Graph:
    """Agrega entidades y relaciones al grafo desde un texto fuente."""
    graph = g if g is not None else nx.Graph()
    for chunk in chunk_text(text):
        try:
            raw = M.llm_chat(
                llm_model,
                EXTRACT_PROMPT.format(chunk=chunk),
                system="Responde unicamente con JSON valido.",
            )
            data = _parse_json(raw)
        except Exception:
            continue

        for entity in data.get("entities", []):
            name = entity.get("name", "").strip()
            if not name:
                continue
            key = _norm(name)
            if key in graph:
                graph.nodes[key]["sources"].add(source)
            else:
                graph.add_node(
                    key,
                    name=name,
                    type=entity.get("type", "WORD"),
                    description=entity.get("description", ""),
                    sources={source},
                )

        for relation in data.get("relations", []):
            src = _norm(relation.get("source", ""))
            dst = _norm(relation.get("target", ""))
            if src in graph and dst in graph and src != dst:
                graph.add_edge(src, dst, description=relation.get("description", "relacionado"))
    return graph


def save_graph(g: nx.Graph):
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "nodes": [
            {
                "id": node_id,
                **{
                    key: (sorted(value) if isinstance(value, set) else value)
                    for key, value in attrs.items()
                },
            }
            for node_id, attrs in g.nodes(data=True)
        ],
        "edges": [{"source": u, "target": v, **attrs} for u, v, attrs in g.edges(data=True)],
    }
    GRAPH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_graph() -> nx.Graph:
    if not GRAPH_PATH.exists():
        return nx.Graph()
    data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    g = nx.Graph()
    for node in data["nodes"]:
        node = dict(node)
        node_id = node.pop("id")
        if "sources" in node:
            node["sources"] = set(node["sources"])
        g.add_node(node_id, **node)
    for edge in data["edges"]:
        edge = dict(edge)
        g.add_edge(edge.pop("source"), edge.pop("target"), **edge)
    return g


def build_node_embeddings(g: nx.Graph):
    """Embebe nodos para enlazar preguntas con el grafo."""
    nodes = list(g.nodes())
    if not nodes:
        return
    texts = [f"{g.nodes[node]['name']}: {g.nodes[node].get('description', '')}" for node in nodes]
    payload = {"nodes": nodes, "vecs": _embed(texts)}
    EMB_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMB_PATH.write_text(json.dumps(payload), encoding="utf-8")


def index_material(text: str, source: str, llm_model: str):
    """Pipeline completo de indexado."""
    graph = build_graph(text, source, llm_model, g=load_graph())
    save_graph(graph)
    build_node_embeddings(graph)
    return graph.number_of_nodes(), graph.number_of_edges()


def query(question: str, llm_model: str, hops: int = 1, top_k: int = 5) -> str:
    """Responde usando solo el grafo y el modelo local."""
    graph = load_graph()
    if graph.number_of_nodes() == 0:
        return "El grafo esta vacio. Indexa material primero."
    if not EMB_PATH.exists():
        build_node_embeddings(graph)

    import numpy as np

    index = json.loads(EMB_PATH.read_text(encoding="utf-8"))
    vecs = np.array(index["vecs"])
    q_vec = np.array(_embed([question])[0])
    similarities = vecs @ q_vec
    order = similarities.argsort()[::-1]
    seeds = [index["nodes"][i] for i in order[:top_k] if index["nodes"][i] in graph]

    subgraph_nodes = set(seeds)
    for seed in seeds:
        subgraph_nodes |= set(nx.ego_graph(graph, seed, radius=hops).nodes())

    lines = ["ENTIDADES:"]
    for node in subgraph_nodes:
        attrs = graph.nodes[node]
        lines.append(f"- {attrs['name']} ({attrs.get('type', '')}): {attrs.get('description', '')}")
    lines.append("")
    lines.append("RELACIONES:")
    for src, dst, attrs in graph.subgraph(subgraph_nodes).edges(data=True):
        lines.append(
            f"- {graph.nodes[src]['name']} -[{attrs.get('description', 'rel')}]- {graph.nodes[dst]['name']}"
        )
    context = "\n".join(lines)

    prompt = f"""Usa solo este grafo de conocimiento para responder en espanol,
explicando con ejemplos claros para un estudiante de ingles.

{context}

PREGUNTA: {question}
RESPUESTA:"""
    return M.llm_chat(llm_model, prompt)
