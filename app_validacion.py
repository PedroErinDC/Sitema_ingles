"""
app_validacion.py - Ingesta, validacion y biblioteca de contenido.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile

import streamlit as st

import content as C
import models as M


C.ensure_dirs()
st.set_page_config(page_title="Ingles local - Ingesta y validacion", layout="wide")
st.title("Contenido y validacion")

TMP = Path(tempfile.gettempdir())
ss = st.session_state
ss.setdefault("attempt", 0)
ss.setdefault("result", None)
ss.setdefault("media_path", None)
ss.setdefault("media_name", None)
ss.setdefault("media_source_id", None)
ss.setdefault("media_meta", {})
ss.setdefault("last_media_status", "")


def reset_current_media(clear_status: bool = False):
    ss["attempt"] = 0
    ss["result"] = None
    ss["media_path"] = None
    ss["media_name"] = None
    ss["media_source_id"] = None
    ss["media_meta"] = {}
    if clear_status:
        ss["last_media_status"] = ""


def set_current_media(path: Path, name: str, source_id: str, metadata: dict | None = None):
    ss["media_path"] = str(path)
    ss["media_name"] = name
    ss["media_source_id"] = source_id
    ss["media_meta"] = metadata or {}
    ss["attempt"] = 0
    ss["result"] = None


def current_media_path() -> Path | None:
    if not ss.get("media_path"):
        return None
    path = Path(ss["media_path"])
    return path if path.exists() else None


def _update_progress(bar, status_box, value: float, message: str):
    bar.progress(min(max(value, 0.0), 1.0), text=message)
    status_box.caption(message)


def _download_progress_hook(bar, status_box):
    def hook(data: dict):
        state = data.get("status", "")
        if state == "downloading":
            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total:
                pct = downloaded / total
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                _update_progress(
                    bar,
                    status_box,
                    pct,
                    f"Descargando YouTube: {pct:.0%} ({downloaded_mb:.1f} / {total_mb:.1f} MB)",
                )
            else:
                downloaded_mb = downloaded / (1024 * 1024)
                _update_progress(bar, status_box, 0.15, f"Descargando YouTube... {downloaded_mb:.1f} MB")
        elif state == "finished":
            _update_progress(bar, status_box, 0.95, "Descarga terminada. Procesando archivo final...")

    return hook


def build_vtt_for_record(record: dict, tag: str) -> str | None:
    segments = record.get("segments") or []
    if not segments:
        return None
    segs = [M.Segment(float(seg["start"]), float(seg["end"]), seg["text"]) for seg in segments]
    out = TMP / f"{tag}.vtt"
    return M.write_vtt(segs, str(out))


def render_model_sidebar():
    with st.sidebar:
        st.header("Modelos")

        st.subheader("LLM")
        installed = M.llm_installed()
        preferred = M.preferred_llm()
        llm_choice = st.selectbox(
            "Modelo activo",
            options=list(M.LLM_CATALOG.keys()),
            index=list(M.LLM_CATALOG.keys()).index(preferred) if preferred in M.LLM_CATALOG else 0,
            format_func=lambda key: M.LLM_CATALOG[key]["label"]
            + (" - instalado" if key in installed else " - no descargado"),
        )
        effective_llm = M.resolve_llm_model(llm_choice)
        ss["llm"] = effective_llm or llm_choice
        if llm_choice != effective_llm and effective_llm:
            st.caption(f"Modelo seleccionado no instalado. Usando fallback: {effective_llm}")
        if llm_choice not in installed and st.button(f"Descargar {llm_choice}"):
            bar = st.progress(0.0, text="Descargando...")
            for chunk in M.llm_pull(llm_choice):
                total = chunk.get("total")
                completed = chunk.get("completed")
                if total:
                    bar.progress(min(completed / total, 1.0), text=chunk.get("status", "Descargando..."))
            bar.progress(1.0, text="Listo")
            st.rerun()

        st.divider()
        st.subheader("ASR")
        asr_order = st.multiselect(
            "Modelos a probar",
            options=list(M.ASR_CATALOG.keys()),
            default=["parakeet-tdt-0.6b-v3", "whisper-large-v3-turbo"],
            format_func=lambda key: M.ASR_CATALOG[key]["label"],
        )
        st.caption("Si una transcripcion sale mal, puedes probar el siguiente modelo.")
        if st.button("Liberar VRAM"):
            M.free_asr()
            st.toast("VRAM liberada")
    return ss["llm"], asr_order


def render_intro():
    st.info(
        "Flujo recomendado: 1) carga o descarga un medio, 2) transcribe, 3) valida subtitulos, "
        "4) guarda en biblioteca, 5) luego importalo en la app de estudio o GraphRAG."
    )
    cols = st.columns(4)
    cols[0].metric("Paso 1", "Cargar")
    cols[1].metric("Paso 2", "Transcribir")
    cols[2].metric("Paso 3", "Validar")
    cols[3].metric("Paso 4", "Guardar")


def render_current_media_summary():
    path = current_media_path()
    if not path:
        st.caption("No hay un medio activo cargado.")
        return

    title = ss.get("media_meta", {}).get("title") or ss.get("media_name") or path.name
    size_mb = path.stat().st_size / (1024 * 1024)
    st.success(f"Contenido actual: {title}")
    st.caption(f"Archivo: {path.name} | Tamano: {size_mb:.1f} MB")
    if ss.get("last_media_status"):
        st.caption(ss["last_media_status"])
    col_keep, col_delete = st.columns(2)
    if col_keep.button("Quitar de esta sesion", use_container_width=True):
        reset_current_media()
        st.rerun()
    if col_delete.button("Borrar este medio", use_container_width=True):
        C.delete_path(path)
        reset_current_media(clear_status=True)
        st.warning("Medio borrado completamente.")
        st.rerun()


def render_source_loader():
    st.subheader("Paso 1. Agregar contenido")
    source_mode = st.radio(
        "Origen",
        ["Archivo local", "URL de YouTube"],
        horizontal=True,
        help="Usa archivo local para medios ya descargados. Usa URL de YouTube para bajarlo directo.",
    )

    if source_mode == "Archivo local":
        uploaded = st.file_uploader(
            "Sube audio o video",
            type=["mp4", "mkv", "mov", "webm", "avi", "m4v", "mp3", "wav", "m4a", "aac", "flac", "ogg"],
            key="media_uploader",
        )
        if uploaded:
            source_id = f"upload:{uploaded.name}:{uploaded.size}"
            if ss.get("media_source_id") != source_id:
                saved_path = C.save_upload_bytes(uploaded.name, uploaded.getbuffer())
                set_current_media(saved_path, uploaded.name, source_id)
                ss["last_media_status"] = "Archivo local cargado."
                st.success(f"Archivo cargado: {uploaded.name}")
    else:
        yt_url = st.text_input("URL de YouTube", placeholder="https://www.youtube.com/watch?v=...")
        audio_only = st.checkbox("Descargar solo audio", value=False)
        if st.button("Descargar desde YouTube"):
            if not yt_url.strip():
                st.warning("Pega una URL valida.")
            else:
                progress_box = st.empty()
                progress_bar = st.progress(0.0, text="Preparando descarga...")
                status_box = st.empty()
                try:
                    _update_progress(progress_bar, status_box, 0.02, "Conectando con YouTube...")
                    local_path, info = C.download_youtube_media(
                        yt_url.strip(),
                        audio_only=audio_only,
                        progress_callback=_download_progress_hook(progress_bar, status_box),
                    )
                    _update_progress(progress_bar, status_box, 1.0, "Descarga completada.")
                except Exception as exc:
                    progress_bar.empty()
                    status_box.empty()
                    progress_box.error(f"Fallo la descarga: {exc}")
                else:
                    set_current_media(local_path, local_path.name, f"youtube:{yt_url.strip()}:{audio_only}", info)
                    ss["last_media_status"] = f"Descargado: {info.get('title', local_path.name)}"
                    progress_box.success(ss["last_media_status"])
                    st.rerun()

    render_current_media_summary()


def render_transcription_workflow(llm_choice: str, asr_order: list[str]):
    st.subheader("Paso 2. Transcribir y validar")
    media_path = current_media_path()
    if not media_path:
        st.info("Primero agrega un medio o carga uno desde la pestaña de pendientes.")
        return
    if not asr_order:
        st.warning("Elige al menos un modelo ASR en la barra lateral.")
        return

    translate = st.checkbox("Traducir ingles a espanol al guardar", value=True, key="translate_media")
    language = st.selectbox("Idioma esperado del audio", ["en"], index=0)

    if ss["attempt"] >= len(asr_order):
        st.error("Ya probaste todos los modelos ASR configurados para este medio.")
        return

    asr_key = asr_order[ss["attempt"]]
    st.info(f"Intento {ss['attempt'] + 1}/{len(asr_order)} con {M.ASR_CATALOG[asr_key]['label']}")

    if ss["result"] is None or ss["result"]["asr_key"] != asr_key:
        if st.button("Transcribir con este modelo", type="primary"):
            progress_bar = st.progress(0.0, text="Preparando transcripcion...")
            status_box = st.empty()
            try:
                _update_progress(progress_bar, status_box, 0.05, "Preparando archivo...")
                _update_progress(progress_bar, status_box, 0.2, "Extrayendo audio con ffmpeg...")
                _update_progress(progress_bar, status_box, 0.45, f"Cargando modelo ASR: {M.ASR_CATALOG[asr_key]['label']}...")
                _update_progress(progress_bar, status_box, 0.7, "Transcribiendo audio. Esto puede tardar varios minutos...")
                segments = M.transcribe_media(str(media_path), asr_key, language=language)
                _update_progress(progress_bar, status_box, 0.92, "Generando subtitulos...")
                vtt_path = M.write_vtt(segments, str(TMP / f"{media_path.stem}.{asr_key}.vtt"))
                _update_progress(progress_bar, status_box, 1.0, "Transcripcion completada.")
                ss["result"] = {"segments": segments, "vtt_path": vtt_path, "asr_key": asr_key}
            except Exception as exc:
                progress_bar.empty()
                status_box.error(f"Fallo la transcripcion: {exc}")
            else:
                st.rerun()

    if not (ss["result"] and ss["result"]["asr_key"] == asr_key):
        return

    if C.is_video(ss["media_name"] or media_path.name):
        st.video(str(media_path), subtitles={"Subtitulos EN": ss["result"]["vtt_path"]})
    else:
        st.audio(str(media_path))

    with st.expander("Texto completo transcrito", expanded=True):
        st.write(" ".join(seg.text for seg in ss["result"]["segments"]))

    st.markdown("**Paso 3. Decide si la transcripcion esta bien**")
    col_ok, col_retry = st.columns(2)

    if col_ok.button("Guardar en biblioteca", use_container_width=True):
        metadata = dict(ss.get("media_meta", {}))
        out_file = C.save_transcript_record(
            ss["media_name"] or media_path.name,
            ss["result"]["segments"],
            asr_model=asr_key,
            llm_model=llm_choice,
            kind="video" if C.is_video(ss["media_name"] or media_path.name) else "audio",
            source_path=str(media_path),
            translate=translate,
            metadata=metadata,
        )
        reset_current_media(clear_status=True)
        st.success(f"Guardado en {out_file}. El medio ya paso a biblioteca y salio de pendientes.")
        st.rerun()

    if col_retry.button("Probar otro modelo", use_container_width=True):
        ss["attempt"] += 1
        ss["result"] = None
        M.free_asr()
        st.rerun()


def render_pending_tab():
    st.subheader("Pendientes por revisar")
    st.caption("Aqui aparecen medios cargados o descargados que aun no guardaste en biblioteca.")
    pending = C.list_pending_media_uploads()
    if not pending:
        st.info("No hay medios pendientes.")
        return

    for path in pending:
        size_mb = path.stat().st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        st.markdown(f"**{path.name}**")
        st.caption(f"{size_mb:.1f} MB | {modified}")
        col_load, col_delete = st.columns(2)
        if col_load.button("Cargar para validar", key=f"load_{path.name}", use_container_width=True):
            set_current_media(path, path.name, f"pending:{path.resolve()}")
            ss["last_media_status"] = "Pendiente cargado desde uploads."
            st.rerun()
        if col_delete.button("Borrar completamente", key=f"delete_{path.name}", use_container_width=True):
            C.delete_path(path)
            if current_media_path() and current_media_path() == path:
                reset_current_media(clear_status=True)
            st.warning(f"Borrado: {path.name}")
            st.rerun()


def render_record_preview(record_path: Path, record: dict):
    source_path = Path(record.get("source_path", "")) if record.get("source_path") else None
    kind = record.get("kind", "content")
    display = C.display_name(record)
    st.markdown(f"### {display}")
    st.caption(f"Tipo: {kind} | Archivo: {record_path.name}")

    preview_tabs = st.tabs(["Vista", "Texto ingles", "Texto espanol", "Metadata"])
    if kind in {"video", "audio"} and source_path and source_path.exists():
        vtt_path = build_vtt_for_record(record, f"preview_{record_path.stem}")
        with preview_tabs[0]:
            if kind == "video":
                subtitles = {"Subtitulos EN": vtt_path} if vtt_path else None
                st.video(str(source_path), subtitles=subtitles)
            else:
                st.audio(str(source_path))
                if vtt_path:
                    st.caption("Este audio tiene subtitulos guardados en el registro.")
    else:
        with preview_tabs[0]:
            st.info("Este registro no tiene un medio reproducible asociado.")

    with preview_tabs[1]:
        st.text_area("Texto completo en ingles", value=record.get("text_en", ""), height=320, disabled=True)
    with preview_tabs[2]:
        st.text_area("Texto completo en espanol", value=record.get("text_es", ""), height=320, disabled=True)
    with preview_tabs[3]:
        st.json(
            {
                "source": record.get("source"),
                "source_path": record.get("source_path"),
                "asr_model": record.get("asr_model"),
                "created_at": record.get("created_at"),
                "metadata": record.get("metadata", {}),
            }
        )

    delete_col, spacer = st.columns([1, 3])
    if delete_col.button("Borrar de biblioteca", key=f"remove_record_{record_path.name}", use_container_width=True):
        C.delete_record(record_path, delete_source=True)
        st.warning("Registro borrado de biblioteca.")
        st.rerun()


def render_library_tab():
    st.subheader("Biblioteca")
    st.caption("Aqui puedes revisar contenido ya guardado, reproducir medios con subtitulos y leer texto completo.")
    records = C.list_records()
    if not records:
        st.info("Todavia no hay contenido guardado en biblioteca.")
        return

    options = []
    mapping = {}
    for path in records:
        record = C.load_record(path)
        label = f"{C.display_name(record)} | {record.get('kind', 'content')} | {record.get('created_at', '')}"
        options.append(label)
        mapping[label] = (path, record)

    selected = st.selectbox("Elige un registro", options)
    record_path, record = mapping[selected]
    render_record_preview(record_path, record)


def render_docs_tab(llm_choice: str):
    st.subheader("Documentos")
    st.caption("Usa esta seccion para PDFs o texto. Se guardan directo en biblioteca documental.")
    translate = st.checkbox("Traducir ingles a espanol al guardar", value=True, key="translate_docs")
    docs = st.file_uploader("Sube PDF, TXT o MD", type=["pdf", "txt", "md"], key="doc_uploader")
    if docs and st.button("Importar documento"):
        with st.spinner("Extrayendo contenido..."):
            out_file = C.import_document(docs.name, docs.getbuffer(), llm_model=llm_choice, translate=translate)
        st.success(f"Documento importado en {out_file}")
        st.rerun()


llm_choice, asr_order = render_model_sidebar()
render_intro()
tab_add, tab_pending, tab_library, tab_docs = st.tabs(
    ["1. Cargar y validar", "2. Pendientes", "3. Biblioteca", "4. Documentos"]
)

with tab_add:
    render_source_loader()
    st.divider()
    render_transcription_workflow(llm_choice, asr_order)

with tab_pending:
    render_pending_tab()

with tab_library:
    render_library_tab()

with tab_docs:
    render_docs_tab(llm_choice)
