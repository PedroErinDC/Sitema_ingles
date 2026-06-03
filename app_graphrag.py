"""
app_graphrag.py - Front local para GraphRAG.
"""

from __future__ import annotations

import streamlit as st

import content as C
import graphrag as G
import models as M


st.set_page_config(page_title="GraphRAG local", layout="wide")
st.title("GraphRAG - grafo de conocimiento de tu ingles")

installed = M.llm_installed()
preferred_llm = M.preferred_llm()
llm = st.sidebar.selectbox(
    "LLM activo",
    options=list(M.LLM_CATALOG.keys()),
    index=list(M.LLM_CATALOG.keys()).index(preferred_llm) if preferred_llm in M.LLM_CATALOG else 0,
    format_func=lambda key: M.LLM_CATALOG[key]["label"]
    + (" - instalado" if key in installed else " - no descargado"),
)
llm = M.resolve_llm_model(llm)

tab_index, tab_chat = st.tabs(["Indexar material", "Preguntar"])

with tab_index:
    st.caption("Toma contenido guardado en data/transcripts/ y data/library/ y lo agrega al grafo.")
    records = C.list_records()
    if not records:
        st.info("No hay contenido aun. Usa la app de ingesta primero.")
    else:
        options = [
            f"{path.name} | {C.load_record(path).get('kind', 'content')} | {C.load_record(path).get('source', path.name)}"
            for path in records
        ]
        mapping = dict(zip(options, records))
        picks = st.multiselect("Material a indexar", options, default=options)
        if st.button("Construir o actualizar grafo"):
            progress = st.progress(0.0)
            nodes = edges = 0
            for index, label in enumerate(picks, start=1):
                record = C.load_record(mapping[label])
                with st.spinner(f"Indexando {record.get('source', mapping[label].name)}..."):
                    nodes, edges = G.index_material(record.get("text_en", ""), mapping[label].name, llm)
                progress.progress(index / len(picks))
            st.success(f"Grafo actualizado: {nodes} nodos, {edges} relaciones.")

    graph = G.load_graph()
    metric_1, metric_2 = st.columns(2)
    metric_1.metric("Nodos en el grafo", graph.number_of_nodes())
    metric_2.metric("Relaciones", graph.number_of_edges())

with tab_chat:
    hops = st.slider("Saltos de vecindario", 1, 3, 1)
    question = st.text_input(
        "Pregunta",
        placeholder="Ej.: que se sobre phrasal verbs o conecta run con otros temas",
    )
    if st.button("Responder") and question:
        with st.spinner("Recorriendo el grafo..."):
            answer = G.query(question, llm, hops=hops)
        st.markdown(answer)
