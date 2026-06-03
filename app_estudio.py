"""
app_estudio.py - Estudio adaptativo de vocabulario y gramatica.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import content as C
import graphrag as G
import learning as L
import models as M
import notes as N


st.set_page_config(page_title="Estudiar ingles adaptativo", layout="wide")
C.ensure_dirs()
L.init_db()

ss = st.session_state
ss.setdefault("queue", [])
ss.setdefault("revealed", False)
ss.setdefault("grammar_quiz", [])
ss.setdefault("grammar_index", 0)

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

tabs = st.tabs(["Estudiar hoy", "Gramatica", "Progreso", "Importar", "Notas"])
tab_study, tab_grammar, tab_progress, tab_import, tab_notes = tabs

with tab_study:
    if st.button("Empezar sesion"):
        ss["queue"] = L.due_today(limit=20)
        ss["revealed"] = False

    if not ss["queue"]:
        st.info("No hay vocabulario pendiente. Importa contenido o espera al siguiente repaso.")
    else:
        card = ss["queue"][0]
        topic = card.get("topic") or card.get("pos") or "-"
        st.caption(f"Quedan {len(ss['queue'])} | tema: {topic} | fallos previos: {card['lapses']}")
        st.markdown(f"## {card['word'] or card['lemma']}")

        if not ss["revealed"]:
            if st.button("Mostrar significado"):
                ss["revealed"] = True
                st.rerun()
        else:
            st.markdown(f"**Traduccion:** {card['translation'] or '(sin traducir aun)'}")
            if card["example_en"]:
                st.markdown(f"*{card['example_en']}*")
            st.markdown("**Que tal lo sabias?**")
            columns = st.columns(4)
            ratings = [("Falle", 1), ("Dificil", 2), ("Bien", 3), ("Facil", 4)]
            for col, (label, rating) in zip(columns, ratings):
                if col.button(label, use_container_width=True):
                    L.review_word(card["id"], rating)
                    failed = ss["queue"].pop(0)
                    if rating == 1:
                        ss["queue"].append(failed)
                    ss["revealed"] = False
                    st.rerun()

with tab_grammar:
    col_left, col_right = st.columns([2, 1])
    if col_left.button("Generar quiz de gramatica"):
        ss["grammar_quiz"] = L.build_grammar_quiz_session(limit=5)
        ss["grammar_index"] = 0

    rank = L.grammar_rank_summary()
    col_right.metric("Rango", rank["rank"])
    col_right.metric("Nivel estimado", rank["best_level"])

    quiz = ss["grammar_quiz"]
    if not quiz:
        st.info("Genera un quiz para repasar reglas gramaticales pendientes.")
    elif ss["grammar_index"] >= len(quiz):
        st.success("Quiz completado.")
    else:
        item = quiz[ss["grammar_index"]]
        st.caption(f"Pregunta {ss['grammar_index'] + 1}/{len(quiz)} | nivel {item['level']}")
        st.markdown("**Que regla gramatical describe mejor este ejemplo?**")
        st.write(item["prompt"])
        answer = st.radio("Opciones", item["options"], key=f"grammar_option_{ss['grammar_index']}")
        if st.button("Responder quiz"):
            correct = item["options"][item["answer_index"]] == answer
            L.review_grammar(item["id"], 4 if correct else 1, correct=correct)
            if correct:
                st.success(f"Correcto. {item['title']}")
            else:
                st.error(f"Incorrecto. La respuesta era: {item['title']}")
            if item["description"]:
                st.caption(item["description"])
            ss["grammar_index"] += 1
            st.rerun()

with tab_progress:
    counts = L.status_counts()
    grammar_counts = L.grammar_status_counts()
    metrics = st.columns(4)
    metrics[0].metric("Palabras nuevas", counts["nueva"])
    metrics[1].metric("Palabras aprendiendo", counts["aprendiendo"])
    metrics[2].metric("Palabras dominadas", counts["dominada"])
    metrics[3].metric("Gramatica dominada", grammar_counts["dominada"])
    st.bar_chart({"vocabulario": counts, "gramatica": grammar_counts})

    st.subheader("Temas debiles de vocabulario")
    weak = L.weak_topics()
    if not weak:
        st.caption("Aun no hay suficientes respuestas para detectar puntos debiles.")
    for item in weak:
        ratio = (item["fallos"] / item["intentos"]) if item["intentos"] else 0
        st.write(f"**{item['tema']}** - {item['fallos']}/{item['intentos']} fallos ({ratio:.0%})")
        if st.button(f"Reforzar {item['tema']}", key=f"reinforce_{item['tema']}"):
            with st.spinner("Buscando ejemplos en tu grafo de conocimiento..."):
                answer = G.query(f"Explicame y dame ejemplos del tema: {item['tema']}", llm)
            st.markdown(answer)

    st.subheader("Temas debiles de gramatica")
    weak_grammar = L.weak_grammar_topics()
    if not weak_grammar:
        st.caption("Aun no hay suficiente historial de quizzes.")
    for item in weak_grammar:
        ratio = (item["fallos"] / item["intentos"]) if item["intentos"] else 0
        st.write(f"**{item['tema']}** - {item['fallos']}/{item['intentos']} fallos ({ratio:.0%})")
        if st.button(f"Reforzar gramatica {item['tema']}", key=f"grammar_reinforce_{item['tema']}"):
            with st.spinner("Consultando tu material indexado..."):
                answer = G.query(f"Explicame la gramatica: {item['tema']} y dame ejemplos de mi material", llm)
            st.markdown(answer)

with tab_import:
    records = C.list_records()
    if not records:
        st.info("No hay contenido importado. Usa app_validacion.py primero.")
    else:
        labels = [
            f"{path.name} | {C.load_record(path).get('kind', 'content')} | {C.load_record(path).get('source', path.name)}"
            for path in records
        ]
        label_to_path = dict(zip(labels, records))
        selected_label = st.selectbox("Contenido", labels)
        topic = st.text_input("Etiqueta de tema opcional")
        import_vocab = st.checkbox("Importar vocabulario", value=True)
        import_grammar = st.checkbox("Importar puntos de gramatica", value=True)
        if st.button("Procesar contenido"):
            record = C.load_record(label_to_path[selected_label])
            total_vocab = total_grammar = 0
            with st.spinner("Analizando contenido..."):
                if import_vocab:
                    total_vocab = L.add_words_from_text(record.get("text_en", ""), topic=topic, llm_model=llm)
                if import_grammar:
                    total_grammar = L.import_grammar_points(record.get("text_en", ""), topic=topic, llm_model=llm)
            st.success(f"Vocabulario: {total_vocab} | Gramatica: {total_grammar}")

with tab_notes:
    st.caption("Exporta un snapshot en Markdown para Obsidian o lectura manual.")
    if st.button("Exportar nota de estudio"):
        path = N.export_markdown("snapshot_estudio", N.build_study_snapshot())
        st.success(f"Nota exportada en {path}")
    notes_dir = Path("data/obsidian")
    existing = sorted(notes_dir.glob("*.md"), reverse=True) if notes_dir.exists() else []
    if existing:
        latest = existing[0]
        st.write(f"Ultima nota: {latest.name}")
        st.code(latest.read_text(encoding='utf-8')[:4000])
