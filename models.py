"""
models.py - Gestor local de LLM, ASR y traduccion con carga perezosa.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile


LLM_CATALOG = {
    "qwen3:8b": {
        "label": "Qwen 3 8B - ligero y practico",
        "vram_gb": 7,
    },
    "qwen3:14b": {
        "label": "Qwen 3 14B - mejor equilibrio entre calidad y VRAM",
        "vram_gb": 11,
    },
    "gpt-oss:20b": {
        "label": "GPT-OSS 20B - generalista potente",
        "vram_gb": 13,
    },
    "mistral-small:24b": {
        "label": "Mistral Small 24B (Q4) - alta calidad",
        "vram_gb": 14,
    },
}

ASR_CATALOG = {
    "parakeet-tdt-0.6b-v3": {
        "label": "NVIDIA Parakeet TDT v3 - rapido, no alucina (EN + europeos)",
        "backend": "parakeet",
        "ref": "nvidia/parakeet-tdt-0.6b-v3",
    },
    "whisper-large-v3-turbo": {
        "label": "Whisper Large v3 Turbo - multilingue (respaldo)",
        "backend": "whisper",
        "ref": "large-v3-turbo",
    },
    "whisper-large-v3": {
        "label": "Whisper Large v3 - maxima cobertura de idiomas",
        "backend": "whisper",
        "ref": "large-v3",
    },
}


@dataclass
class Segment:
    start: float
    end: float
    text: str


def llm_installed() -> list[str]:
    """Lista modelos LLM instalados localmente."""
    try:
        import ollama

        result = ollama.list()
        models = result.get("models", []) if isinstance(result, dict) else getattr(result, "models", [])
        installed = []
        for model in models:
            if isinstance(model, dict):
                installed.append(model.get("model", model.get("name", "")))
            else:
                installed.append(getattr(model, "model", getattr(model, "name", "")))
        return [name for name in installed if name]
    except Exception:
        return []


def llm_available(model: str = "") -> bool:
    installed = set(llm_installed())
    return bool(installed) if not model else model in installed


def preferred_llm() -> str:
    """Devuelve el mejor modelo instalado que tambien exista en el catalogo."""
    installed = llm_installed()
    for model in LLM_CATALOG:
        if model in installed:
            return model
    return installed[0] if installed else next(iter(LLM_CATALOG))


def resolve_llm_model(model: str = "") -> str:
    """Si el modelo pedido no existe localmente, cae al mejor disponible."""
    if model and llm_available(model):
        return model
    preferred = preferred_llm()
    if preferred and llm_available(preferred):
        return preferred
    return ""


def llm_pull(model: str):
    """Descarga un LLM bajo demanda, emitiendo progreso."""
    import ollama

    for chunk in ollama.pull(model, stream=True):
        yield chunk


def llm_chat(model: str, prompt: str, system: str = "", options: dict | None = None) -> str:
    """Ejecuta una sola interaccion con el LLM elegido."""
    import ollama

    model = resolve_llm_model(model)
    if not model:
        raise RuntimeError("No hay ningun modelo LLM instalado en Ollama.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    kwargs: dict = {"model": model, "messages": messages}
    if options:
        kwargs["options"] = options
    response = ollama.chat(**kwargs)
    message = response["message"] if isinstance(response, dict) else response.message
    return message["content"] if isinstance(message, dict) else message.content


_ASR_CACHE: dict[str, object] = {"key": None, "model": None}
TRANSLATION_MEMORY_PATH = Path("data/corrections/translation_memory.jsonl")


def free_asr():
    """Libera el modelo ASR actual de memoria."""
    _ASR_CACHE["model"] = None
    _ASR_CACHE["key"] = None
    try:
        import gc
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _load_whisper(ref: str):
    from faster_whisper import WhisperModel

    device = "cuda"
    compute_type = "float16"
    try:
        import torch

        if not torch.cuda.is_available():
            device = "cpu"
            compute_type = "int8"
    except Exception:
        device = "cpu"
        compute_type = "int8"

    try:
        return WhisperModel(ref, device=device, compute_type=compute_type)
    except Exception as exc:
        # En algunos entornos torch detecta CUDA, pero faster-whisper falla
        # al cargar las librerias reales de ctranslate2/cuBLAS. En ese caso
        # caemos a CPU para no romper la transcripcion completa.
        if device == "cuda":
            message = str(exc).lower()
            gpu_markers = ("libcublas", "cudnn", "cuda", "ctranslate2")
            if any(marker in message for marker in gpu_markers):
                return WhisperModel(ref, device="cpu", compute_type="int8")
        raise


def _is_whisper_gpu_runtime_error(exc: Exception) -> bool:
    message = str(exc).lower()
    gpu_markers = ("libcublas", "cudnn", "cuda", "ctranslate2")
    return any(marker in message for marker in gpu_markers)


def _load_parakeet(ref: str):
    import nemo.collections.asr as nemo_asr

    return nemo_asr.models.ASRModel.from_pretrained(ref)


def _get_asr(asr_key: str):
    if _ASR_CACHE["key"] == asr_key and _ASR_CACHE["model"] is not None:
        return _ASR_CACHE["model"]
    free_asr()
    info = ASR_CATALOG[asr_key]
    model = _load_parakeet(info["ref"]) if info["backend"] == "parakeet" else _load_whisper(info["ref"])
    _ASR_CACHE.update(key=asr_key, model=model)
    return model


def extract_audio(media_path: str) -> str:
    """Extrae audio 16 kHz mono de un video o audio usando ffmpeg."""
    path = Path(media_path)
    if path.suffix.lower() == ".wav":
        return str(path)
    out = str(path.with_suffix(".wav"))
    subprocess.run(
        ["ffmpeg", "-y", "-i", media_path, "-ar", "16000", "-ac", "1", out],
        check=True,
        capture_output=True,
    )
    return out


def _whisper_segments(model, audio_path: str, language: str) -> list[Segment]:
    segments, _ = model.transcribe(audio_path, language=language, vad_filter=True)
    return [Segment(float(seg.start), float(seg.end), seg.text.strip()) for seg in segments]


_PARAKEET_CHUNK_SECS = 90   # segundos por fragmento — controla VRAM pico
_PARAKEET_MIN_CHUNK_SECS = 3  # fragmentos más cortos que esto se descartan (NeMo crashea con audio muy corto)


def _split_audio_chunks(audio_path: str, chunk_secs: int) -> tuple[list[tuple[float, str]], str]:
    """Divide WAV en fragmentos, devuelve lista de (offset_seg, ruta_chunk) y directorio temporal."""
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    tmpdir = tempfile.mkdtemp(prefix="parakeet_chunks_")
    chunks: list[tuple[float, str]] = []
    offset = 0.0
    i = 0
    while offset < duration:
        remaining = duration - offset
        if remaining < _PARAKEET_MIN_CHUNK_SECS:
            break  # fragmento final demasiado corto — NeMo puede crashear
        chunk_path = os.path.join(tmpdir, f"chunk_{i:04d}.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path,
             "-ss", str(offset), "-t", str(chunk_secs),
             "-ar", "16000", "-ac", "1", chunk_path],
            capture_output=True, check=True,
        )
        chunks.append((offset, chunk_path))
        offset += chunk_secs
        i += 1
    return chunks, tmpdir


def _parakeet_segments(model, audio_path: str) -> list[Segment]:
    chunks, tmpdir = _split_audio_chunks(audio_path, _PARAKEET_CHUNK_SECS)
    all_segments: list[Segment] = []

    try:
        for offset, chunk_path in chunks:
            out = model.transcribe([chunk_path], timestamps=True)

            chunk_segs: list[Segment] = []
            if out:
                hyp = out[0]
                ts = getattr(hyp, "timestamp", None) or {}
                chunk_segs = [
                    Segment(
                        float(seg["start"]) + offset,
                        float(seg["end"]) + offset,
                        seg.get("segment", seg.get("text", "")).strip(),
                    )
                    for seg in ts.get("segment", [])
                    if seg.get("segment", seg.get("text", "")).strip()
                ]
                if not chunk_segs:
                    text = (getattr(hyp, "text", "") or str(hyp)).strip()
                    if text:
                        chunk_segs = [Segment(offset, offset + _PARAKEET_CHUNK_SECS, text)]

            all_segments.extend(chunk_segs)
    finally:
        for _, p in chunks:
            try:
                os.remove(p)
            except Exception:
                pass
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass

    if not all_segments:
        raise RuntimeError(
            f"Parakeet no generó segmentos para '{Path(audio_path).name}'. "
            "El audio puede estar vacío o en silencio."
        )
    return all_segments


def transcribe_media(media_path: str, asr_key: str, language: str = "en") -> list[Segment]:
    """Extrae audio y transcribe con el modelo ASR elegido."""
    audio_path = extract_audio(media_path)
    info = ASR_CATALOG[asr_key]
    model = _get_asr(asr_key)
    try:
        if info["backend"] == "parakeet":
            return _parakeet_segments(model, audio_path)
        try:
            return _whisper_segments(model, audio_path, language)
        except Exception as exc:
            if _is_whisper_gpu_runtime_error(exc):
                from faster_whisper import WhisperModel

                fallback_model = WhisperModel(info["ref"], device="cpu", compute_type="int8")
                _ASR_CACHE.update(key=asr_key, model=fallback_model)
                return _whisper_segments(fallback_model, audio_path, language)
            raise
    finally:
        free_asr()


def _fmt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining:06.3f}"


def to_vtt(segments: list[Segment]) -> str:
    """Genera subtitulos WebVTT compatibles con Streamlit."""
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.extend(
            [
                f"{_fmt(segment.start)} --> {_fmt(segment.end)}",
                segment.text,
                "",
            ]
        )
    return "\n".join(lines)


def write_vtt(segments: list[Segment], path: str) -> str:
    Path(path).write_text(to_vtt(segments), encoding="utf-8")
    return path


def _chunk_text(text: str, max_chars: int = 2400) -> list[str]:
    chunks = []
    current = []
    current_len = 0
    for paragraph in text.splitlines():
        block = paragraph.strip()
        if not block:
            continue
        if current_len + len(block) + 1 > max_chars and current:
            chunks.append("\n".join(current))
            current = [block]
            current_len = len(block)
        else:
            current.append(block)
            current_len += len(block) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks or [text]


def _translate_with_argos(text: str, source_lang: str, target_lang: str) -> str:
    from argostranslate import translate

    langs = translate.get_installed_languages()
    src = next((lang for lang in langs if lang.code == source_lang), None)
    dst = next((lang for lang in langs if lang.code == target_lang), None)
    if not src or not dst:
        raise RuntimeError("Argos Translate no tiene instalado el par de idiomas solicitado.")
    translator = src.get_translation(dst)
    return translator.translate(text)


def translate_text(
    text: str,
    source_lang: str = "en",
    target_lang: str = "es",
    llm_model: str = "",
) -> str:
    """Traduce texto largo por chunks. Usa Argos si esta disponible; si no, usa LLM."""
    text = text.strip()
    if not text:
        return ""

    try:
        return _translate_with_argos(text, source_lang, target_lang)
    except Exception:
        pass

    llm_model = resolve_llm_model(llm_model)
    if llm_model:
        translated = []
        for chunk in _chunk_text(text):
            prompt = (
                f"Traduce del {source_lang} al {target_lang}.\n\n"
                "REGLAS CRITICAS:\n"
                "- NUNCA traduzcas palabra por palabra modismos, phrasal verbs ni expresiones fijas. Traduce el SIGNIFICADO real.\n"
                "- Si existe equivalente idiomatico natural en el idioma destino, usalo.\n"
                "- Conserva el registro (coloquial/formal) del original.\n"
                "- Mantén nombres propios y terminos tecnicos sin traducir.\n"
                "- Devuelve solo la traduccion, sin notas entre parentesis.\n\n"
                "EJEMPLOS: 'fair and square'→'con todas las de la ley', 'piece of cake'→'pan comido', "
                "'cost an arm and a leg'→'costar un ojo de la cara', 'hit the nail on the head'→'dar en el clavo', "
                "'beat around the bush'→'andarse por las ramas', 'go the extra mile'→'esforzarse al maximo', "
                "'figure out'→'descubrir/resolver', 'end up'→'terminar/acabar', 'at the end of the day'→'en definitiva'.\n\n"
                f"TEXTO:\n{chunk}"
            )
            try:
                translated.append(llm_chat(llm_model, prompt))
            except Exception:
                return ""
        return "\n\n".join(translated).strip()
    return ""


_TRANSLATION_SYSTEM = (
    "Eres un traductor experto de subtítulos de inglés a español.\n\n"
    "GLOSARIO OBLIGATORIO — aplica siempre, sin excepción:\n"
    '- "no way" / "no fucking way" / "no way in hell" → "¡Imposible!" / "¡Ni de coña!" / "¡No puede ser!"\n'
    '- "holy shit" / "holy crap" / "damn" → "¡Madre mía!" / "¡Joder!" / "¡Hostia!"\n'
    '- "come on" → "¡Vamos!" / "¡Anda ya!" / "¡Venga!"\n'
    '- "knock it off" → "¡Para ya!" / "¡Déjalo!"\n'
    '- "you got me" / "you really got me" → "Me pillaste" / "Me has pillado"\n'
    '- "fair and square" → "con todas las de la ley"\n'
    '- "get out of here" → "¡Venga ya!" / "¡No me digas!"\n'
    '- "gonna" → "voy/vas/va a" (según persona)\n'
    '- "wanna" → "quiero/quieres/quiere"\n'
    '- "gotta" → "tengo/tienes/tiene que"\n'
    '- "piss someone off" / "take someone off" → "sacar de quicio" / "hacer enojar"\n'
    '- "pussy" (insulto) → "cobarde" / "gallina" / "zorra" (según contexto)\n\n'
    "MODISMOS (traduce el significado, nunca las palabras):\n"
    '- "piece of cake" → "pan comido"\n'
    '- "hit the nail on the head" → "dar en el clavo"\n'
    '- "beat around the bush" → "andarse por las ramas"\n'
    '- "pull someone\'s leg" → "tomarle el pelo"\n'
    '- "cost an arm and a leg" → "costar un ojo de la cara"\n'
    '- "under the weather" → "estar pachucho"\n'
    '- "once in a blue moon" → "muy de vez en cuando"\n'
    '- "get out of hand" → "irse de las manos"\n\n'
    "REGLAS:\n"
    "1. Traduce siempre el SIGNIFICADO, nunca palabra por palabra.\n"
    "2. Conserva el registro: coloquial→coloquial, formal→formal.\n"
    "3. Las groserías en inglés → groserías equivalentes en español (no las suavices).\n"
    "4. Si hay errores ASR (palabras cortadas, fonética rota), infiere la intención por contexto.\n"
    "5. Responde ÚNICAMENTE con JSON válido, sin texto adicional."
)


def _normalize_asr_batch(
    items: list[dict],
    llm_model: str,
    options: dict,
) -> list[dict]:
    """Pass 1: fix ASR transcription errors before translation."""
    segs = [{"id": item["id"], "text": item["text"]} for item in items]
    prompt = (
        "Fix ASR transcription errors in these English subtitle segments.\n"
        "Rules:\n"
        "- Correct phonetic errors, cut-off words, run-on words, and hallucinations\n"
        "- Do NOT translate — keep the text in English\n"
        "- Preserve the speaker's intended meaning and phrasing\n"
        "- Only fix what is clearly a transcription error; leave everything else as-is\n\n"
        'Return JSON: [{"id": 0, "text": "corrected text"}]\n\n'
        f"SEGMENTS:\n{json.dumps(segs, ensure_ascii=False)}"
    )
    try:
        raw = llm_chat(
            llm_model, prompt,
            system="You are an ASR error corrector. Fix transcription errors only, do not translate. Reply with valid JSON only.",
            options={**options, "num_ctx": 4096},
        )
        match = re.search(r"\[.*\]", raw.strip(), flags=re.S)
        data = json.loads(match.group(0) if match else raw)
        if isinstance(data, list):
            fixes = {
                int(item["id"]): str(item.get("text", "")).strip()
                for item in data
                if isinstance(item, dict) and "id" in item and item.get("text")
            }
            for item in items:
                if fixes.get(item["id"]):
                    item["text"] = fixes[item["id"]]
    except Exception:
        pass
    return items


def translate_terms(terms: list[str], llm_model: str = "") -> dict[str, str]:
    """Traduce un lote de terminos EN->ES."""
    clean_terms = [term.strip() for term in terms if term.strip()]
    if not clean_terms:
        return {}

    try:
        return {term: _translate_with_argos(term, "en", "es").strip() for term in clean_terms}
    except Exception:
        pass

    llm_model = resolve_llm_model(llm_model)
    if not llm_model:
        return {}

    prompt = f"""Traduce del ingles al espanol estos terminos.
Devuelve solo JSON valido como objeto {{termino: "traduccion"}}.

TERMINOS:
{json.dumps(clean_terms, ensure_ascii=False)}
"""
    try:
        raw = llm_chat(llm_model, prompt, system="Responde unicamente con JSON valido.")
        data = json.loads(raw.strip().strip("`"))
        return {key: str(value).strip() for key, value in data.items() if str(value).strip()}
    except Exception:
        return {}


def translate_segments(
    texts: list[str],
    source_lang: str = "en",
    target_lang: str = "es",
    llm_model: str = "",
) -> list[str]:
    """Traduce una lista de segmentos conservando el indice de cada linea."""
    cleaned = [text.strip() for text in texts]
    if not cleaned:
        return []

    try:
        return [
            _translate_with_argos(text, source_lang, target_lang).strip() if text else ""
            for text in cleaned
        ]
    except Exception:
        pass

    llm_model = resolve_llm_model(llm_model)
    if not llm_model:
        return [""] * len(cleaned)

    examples = []
    if TRANSLATION_MEMORY_PATH.exists():
        try:
            lines = TRANSLATION_MEMORY_PATH.read_text(encoding="utf-8").splitlines()[-8:]
            for line in lines:
                item = json.loads(line)
                text_en = str(item.get("text_en", "")).strip()
                text_es = str(item.get("text_es", "")).strip()
                if text_en and text_es:
                    examples.append({"en": text_en, "es": text_es})
        except Exception:
            examples = []

    translated = [""] * len(cleaned)
    batch_size = 20
    translate_options = {"num_ctx": 8192}
    for start in range(0, len(cleaned), batch_size):
        batch = []
        for index, text in enumerate(cleaned[start : start + batch_size]):
            if not text:
                continue
            global_i = start + index
            batch.append({
                "id": global_i,
                "prev": cleaned[global_i - 1] if global_i > 0 else "",
                "text": text,
                "next": cleaned[global_i + 1] if global_i < len(cleaned) - 1 else "",
            })
        if not batch:
            continue

        # Pass 1: fix ASR errors before translating
        if source_lang == "en":
            batch = _normalize_asr_batch(batch, llm_model, translate_options)

        memory_block = ""
        if examples:
            memory_block = (
                "Correcciones previas de estilo (úsalas como referencia):\n"
                f"{json.dumps(examples, ensure_ascii=False)}\n\n"
            )

        prompt = (
            f"{memory_block}"
            f'Traduce del {source_lang} al {target_lang} el campo "text" de cada segmento.\n\n'
            '"prev" y "next" son contexto adyacente — no los traduzcas, solo úsalos para entender "text".\n\n'
            'Devuelve JSON: [{"id": 0, "translation": "..."}]\n\n'
            f"SEGMENTOS:\n{json.dumps(batch, ensure_ascii=False)}"
        )
        parsed = {}
        try:
            raw = llm_chat(llm_model, prompt, system=_TRANSLATION_SYSTEM, options=translate_options)
            match = re.search(r"\[.*\]", raw.strip(), flags=re.S)
            data = json.loads(match.group(0) if match else raw)
            if isinstance(data, list):
                parsed = {
                    int(item["id"]): str(item.get("translation", "")).strip()
                    for item in data
                    if isinstance(item, dict) and "id" in item
                }
        except Exception:
            parsed = {}

        for item in batch:
            index = item["id"]
            if parsed.get(index):
                translated[index] = parsed[index]
            else:
                translated[index] = translate_text(
                    item["text"],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    llm_model=llm_model,
                )

    return translated
