# Sistema Local de Aprendizaje de Inglés — PLAN FINAL + Código (2026)

> Sistema **100% local y offline**. Sin Claude, sin ChatGPT, sin nube.
> Para **VS Code / Jupyter + Python** sobre una **NVIDIA RTX 5070 Ti (16 GB)**.
> Incluye el **motor adaptativo**, **GraphRAG local** y el código completo de los 6 módulos al final.

---

## 1. Objetivo

Una app local que aprende **de ti** y te hace estudiar de forma eficiente:

1. **Ingiere** material (audio, video, PDF, texto).
2. **Transcribe** audio/video y guarda inglés + español.
3. **Valida** la transcripción reproduciendo el video con subtítulos antes de guardar; si está mal, prueba otro modelo.
4. **Extrae vocabulario** y detecta lo que no sabes.
5. **Clasifica** tu dominio (nueva / aprendiendo / más o menos / dominada) con repetición espaciada.
6. **No repite lo que ya dominas** y **refuerza lo que fallas**.
7. **Detecta tus temas débiles** y te trae material de TU propio contenido para reforzarlos.
8. **Genera tests** y un sistema de rangos/niveles para la gramática.

---

## 2. Los TRES "cerebros" (idea central)

La confusión habitual es pensar que GraphRAG u Obsidian "aprenden de ti". No: son cerebros del **conocimiento**. El que aprende de ti es otro. Hay tres capas, cada una con su trabajo:

| Cerebro | Qué guarda | Quién lo usa | Para qué |
|---|---|---|---|
| **1. Motor adaptativo (SRS + DB)** | **Tu rendimiento**: qué dominas, qué fallas | El sistema | Decidir **qué** estudiar (omite lo dominado, refuerza lo fallado) |
| **2. GraphRAG** | El **conocimiento de tu material** (grafo) | La IA | Traer **el material** para reforzar un tema débil y responder preguntas |
| **3. Obsidian (opcional)** | Tus **notas** legibles y enlazadas | Tú | **Dónde** te sientas a estudiar a mano |

**El bucle completo:**

```
   Estudias / haces test
            │
            ▼
 ┌──────────────────────┐   actualiza dominio (SM-2)
 │ 1. MOTOR ADAPTATIVO  │──────────────┐
 │   (SRS + SQLite)     │              │ no repite lo dominado
 └──────────┬───────────┘              │ refuerza lo fallado
            │ detecta TEMAS débiles    │
            ▼                          ▼
 ┌──────────────────────┐      "qué estudiar hoy"
 │ 2. GraphRAG          │  ◀── tema débil (ej: "past perfect")
 │   trae ejemplos de   │
 │   TU material        │──▶ explicación + ejemplos para reforzar
 └──────────────────────┘
            │
            ▼
 ┌──────────────────────┐
 │ 3. Obsidian (opc.)   │  ◀── exportas notas para estudiar a mano
 └──────────────────────┘
```

> Resumen: **el SRS decide *qué* estudiar → GraphRAG trae *el material* → Obsidian es *dónde* lo estudias.**

### GraphRAG vs Obsidian (aclaración rápida)
- **GraphRAG:** el grafo lo construye **la IA** automáticamente y lo lee **la máquina** para responderte.
- **Obsidian:** el grafo lo construyes **tú** a mano con `[[enlaces]]` y lo navegas **tú** para estudiar.
- No compiten: Obsidian es la cara para el humano; GraphRAG el motor para la IA. Plugins como Smart Connections (con Ollama) unen ambos en local.

---

## 3. Hardware (IMPORTANTE)

La RTX 5070 Ti es **Blackwell (`sm_120`)**:

| Requisito | Valor |
|---|---|
| VRAM | 16 GB GDDR7 |
| CUDA mínimo | **12.8+** (soporte real de `sm_120`) |
| PyTorch | wheels `cu128` (o nightly si la estable no trae `sm_120`) |
| Driver | ≥ 570 |

- Toda librería con CUDA debe estar compilada para `sm_120` o dará *"no kernel image is available"*.
- **Ollama** detecta la Blackwell solo (vía fácil para el LLM).

```python
import torch
print(torch.cuda.get_device_name(0))       # NVIDIA GeForce RTX 5070 Ti
print(torch.cuda.get_device_capability())  # (12, 0)
```

---

## 4. Stack tecnológico (mayo 2026)

| Función | Herramienta |
|---|---|
| LLM local | Ollama + **Qwen 3.5 9B** (multilingüe + multimodal); alt: GPT-OSS 20B, Mistral Small 24B |
| ASR | **NVIDIA Parakeet TDT v3** (rápido, no alucina); respaldo: Whisper Large v3 Turbo |
| Audio de video | `ffmpeg` |
| Traducción EN→ES | LLM local o `argostranslate` |
| Vocabulario | `spaCy` (`en_core_web_sm`) |
| Embeddings | `sentence-transformers` → `BAAI/bge-m3` |
| Grafo | `networkx` (→ JSON) |
| **SRS / motor adaptativo** | **SM-2 sobre `sqlite3`** (sin dependencias extra) |
| Base de datos | `SQLite` |
| Front | `Streamlit` |

---

## 5. Estructura del proyecto

```
ingles-local/
├── plan_final_ingles.md
├── requirements.txt
├── data/
│   ├── uploads/  transcripts/  graph.json  graph_embeddings.json  ingles.db
├── models.py            # gestor de modelos perezoso + ASR + subtítulos
├── learning.py          # ★ motor adaptativo: SRS + DB + qué estudiar + temas débiles
├── graphrag.py          # GraphRAG local (networkx + Ollama + embeddings)
├── app_validacion.py    # front: validar transcripción de video
├── app_estudio.py       # ★ front: estudiar (adaptativo) + progreso + refuerzo
└── app_graphrag.py      # front: indexar grafo + chatear
```

---

## 6. Cómo cumple tu objetivo (el motor adaptativo, `learning.py`)

- **No repite lo dominado:** al acertar, SM-2 alarga el intervalo (30+ días). `due_today()` solo trae lo vencido o nuevo, así que lo dominado **no aparece**.
- **Refuerza lo que fallas:** al fallar, el intervalo se reinicia a 1 día *y* la palabra **vuelve dentro de la misma sesión** (se reencola).
- **Clasifica el dominio:** `nueva → aprendiendo → más o menos → dominada` según el intervalo.
- **Detecta temas débiles:** `weak_topics()` agrupa los fallos por tema/regla y los ordena por tasa de error.
- **Refuerza con tu material:** ese tema débil se pasa a `graphrag.query()`, que trae explicación + ejemplos de TUS videos/PDFs.

Probado: una palabra marcada "fácil" varias veces se vuelve *dominada* y desaparece del estudio; las falladas se concentran como tema débil para reforzar.

---

## 7. Gestión de modelos y validación
- **Nada se descarga al arrancar** (carga perezosa de `torch`/`nemo`/`faster_whisper`).
- **Selector de modelos** en el front: LLM (descarga con botón) y lista ordenada de ASR a probar.
- **Validación:** subes video → transcribe → reproduce con subtítulos → ✅ guardar / ❌ probar otro modelo.

---

## 8. Instalación

```bash
python -m venv venv && source venv/bin/activate

pip install --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cu128

pip install streamlit ollama faster-whisper "nemo_toolkit[asr]" \
    sentence-transformers networkx numpy spacy pymupdf pdfplumber argostranslate
python -m spacy download en_core_web_sm

sudo apt install ffmpeg        # Windows: choco install ffmpeg
# Instala Ollama desde https://ollama.com (los modelos se bajan desde el front)
```

---

## 9. Cómo ejecutar

```bash
streamlit run app_validacion.py   # 1) validar y guardar transcripciones
streamlit run app_graphrag.py     # 2) indexar el grafo de conocimiento
streamlit run app_estudio.py      # 3) estudiar de forma adaptativa
```

Flujo: validas un video → importas su vocabulario en «Estudiar» → estudias →
el sistema clasifica tu dominio, omite lo que sabes y, en «Progreso», te muestra
tus temas débiles con un botón para reforzarlos con GraphRAG.

---

## 10. Presupuesto de VRAM (16 GB)

| Carga | VRAM | Nota |
|---|---|---|
| Parakeet TDT v3 | ~3 GB | Rápido |
| Whisper Large v3 Turbo | ~6 GB | Respaldo |
| Qwen 3.5 9B (Q4) | ~7 GB | Cómodo |
| Embeddings bge-m3 | ~2 GB | Ligero |

No cargues ASR + LLM grande a la vez: transcribe → `free_asr()` → usa el LLM.

---

# 11. CÓDIGO COMPLETO

Los 6 módulos. Crea cada archivo con el nombre indicado.


## 11.1 `models.py`

````python
"""
models.py — Gestor de modelos 100% local con CARGA PEREZOSA.

Principios:
  * NADA se descarga ni se carga al importar este módulo.
  * Las librerías pesadas (torch, nemo, faster_whisper) se importan DENTRO de las
    funciones, así arrancar la app no consume VRAM ni dispara descargas.
  * El LLM se gestiona con Ollama: los modelos se bajan con 'pull' bajo demanda.
  * El ASR (Parakeet / Whisper) se baja de HuggingFace en el PRIMER uso.
  * Solo se mantiene UN modelo ASR en memoria a la vez (se libera al cambiar).
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess

# ───────────────────────── Catálogos curados ─────────────────────────
# Esto es solo metadata. No descarga nada. El front lo muestra como opciones.

LLM_CATALOG = {
    "qwen3.5:9b":        {"label": "Qwen 3.5 9B — multilingüe + multimodal (recomendado)", "vram_gb": 7},
    "qwen3.5:14b":       {"label": "Qwen 3.5 14B — más calidad",                           "vram_gb": 11},
    "gpt-oss:20b":       {"label": "GPT-OSS 20B — generalista fuerte",                      "vram_gb": 13},
    "mistral-small:24b": {"label": "Mistral Small 24B (Q4) — calidad alta",                "vram_gb": 14},
}

ASR_CATALOG = {
    "parakeet-tdt-0.6b-v3": {
        "label":   "NVIDIA Parakeet TDT v3 — rápido, no alucina (EN + europeos)",
        "backend": "parakeet",
        "ref":     "nvidia/parakeet-tdt-0.6b-v3",   # verifica el id exacto en HF
    },
    "whisper-large-v3-turbo": {
        "label":   "Whisper Large v3 Turbo — multilingüe (respaldo)",
        "backend": "whisper",
        "ref":     "large-v3-turbo",
    },
    "whisper-large-v3": {
        "label":   "Whisper Large v3 — máxima cobertura de idiomas",
        "backend": "whisper",
        "ref":     "large-v3",
    },
}


@dataclass
class Segment:
    start: float   # segundos
    end: float     # segundos
    text: str


# ───────────────────────── LLM (Ollama, perezoso) ─────────────────────────
def llm_installed() -> list[str]:
    """Modelos LLM ya descargados. No descarga nada."""
    try:
        import ollama
        return [m.get("model", m.get("name", "")) for m in ollama.list().get("models", [])]
    except Exception:
        return []


def llm_pull(model: str):
    """Descarga un LLM BAJO DEMANDA. Generador con progreso para la barra del front."""
    import ollama
    for chunk in ollama.pull(model, stream=True):
        yield chunk  # dict con status / completed / total


def llm_chat(model: str, prompt: str, system: str = "") -> str:
    """Una respuesta del LLM elegido."""
    import ollama
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    return ollama.chat(model=model, messages=msgs)["message"]["content"]


# ───────────────────────── ASR (perezoso, 1 en memoria) ─────────────────────────
_ASR_CACHE: dict = {"key": None, "model": None}


def free_asr():
    """Libera el modelo ASR actual de la VRAM."""
    _ASR_CACHE["model"] = None
    _ASR_CACHE["key"] = None
    try:
        import torch, gc
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        pass


def _load_whisper(ref: str):
    from faster_whisper import WhisperModel   # import perezoso
    # device="cuda", float16 en tu 5070 Ti. Descarga el peso en el primer uso.
    return WhisperModel(ref, device="cuda", compute_type="float16")


def _load_parakeet(ref: str):
    import nemo.collections.asr as nemo_asr   # import perezoso
    return nemo_asr.models.ASRModel.from_pretrained(ref)


def _get_asr(asr_key: str):
    """Devuelve el modelo ASR cargándolo solo si hace falta (y libera el anterior)."""
    if _ASR_CACHE["key"] == asr_key and _ASR_CACHE["model"] is not None:
        return _ASR_CACHE["model"]
    free_asr()  # nunca tener 2 modelos en VRAM a la vez (clave en 16 GB)
    info = ASR_CATALOG[asr_key]
    model = _load_parakeet(info["ref"]) if info["backend"] == "parakeet" else _load_whisper(info["ref"])
    _ASR_CACHE.update(key=asr_key, model=model)
    return model


# ───────────────────────── Transcripción ─────────────────────────
def extract_audio(media_path: str) -> str:
    """Saca audio 16 kHz mono de un video/audio con ffmpeg."""
    out = str(Path(media_path).with_suffix(".wav"))
    subprocess.run(
        ["ffmpeg", "-y", "-i", media_path, "-ar", "16000", "-ac", "1", out],
        check=True, capture_output=True,
    )
    return out


def _whisper_segments(model, audio_path: str, language: str) -> list[Segment]:
    segs, _ = model.transcribe(audio_path, language=language, vad_filter=True)
    return [Segment(float(s.start), float(s.end), s.text.strip()) for s in segs]


def _parakeet_segments(model, audio_path: str) -> list[Segment]:
    out = model.transcribe([audio_path], timestamps=True)
    hyp = out[0]
    ts = getattr(hyp, "timestamp", None) or {}
    segs = [
        Segment(float(s["start"]), float(s["end"]), s.get("segment", s.get("text", "")).strip())
        for s in ts.get("segment", [])
    ]
    if not segs:  # fallback sin tiempos (versión de NeMo distinta)
        text = getattr(hyp, "text", "") or str(hyp)
        segs = [Segment(0.0, 0.0, text.strip())]
    return segs


def transcribe_media(media_path: str, asr_key: str, language: str = "en") -> list[Segment]:
    """Extrae audio (si es video) y transcribe con el modelo elegido."""
    audio = extract_audio(media_path)
    info = ASR_CATALOG[asr_key]
    model = _get_asr(asr_key)
    if info["backend"] == "parakeet":
        return _parakeet_segments(model, audio)
    return _whisper_segments(model, audio, language)


# ───────────────────────── Subtítulos ─────────────────────────
def _fmt(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def to_vtt(segments: list[Segment]) -> str:
    """Genera subtítulos WebVTT (lo que entiende st.video)."""
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines += [f"{_fmt(seg.start)} --> {_fmt(seg.end)}", seg.text, ""]
    return "\n".join(lines)


def write_vtt(segments: list[Segment], path: str) -> str:
    Path(path).write_text(to_vtt(segments), encoding="utf-8")
    return path
````

## 11.2 `learning.py`

````python
"""
learning.py — Motor adaptativo (el "cerebro que te conoce a TI").

Hace exactamente lo que pediste:
  * Recuerda qué dominas y qué fallas (algoritmo SM-2 sobre SQLite).
  * NO repite lo dominado (sus repasos se agendan muy lejos en el tiempo).
  * Refuerza lo que fallas (vuelve a salir pronto).
  * Decide QUÉ estudiar hoy (prioriza fallos y palabras nuevas, omite dominado).
  * Detecta TEMAS débiles agrupando fallos -> para reforzar con GraphRAG.

Solo usa sqlite3 (stdlib). spaCy es opcional (import perezoso) para extraer vocabulario.
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path

DB = Path("data/ingles.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY,
    lemma       TEXT UNIQUE NOT NULL,
    word        TEXT,
    pos         TEXT,
    topic       TEXT,                 -- regla/tema (para detectar puntos débiles)
    translation TEXT,
    example_en  TEXT,
    example_es  TEXT,
    ease        REAL DEFAULT 2.5,     -- factor de facilidad (SM-2)
    interval    INTEGER DEFAULT 0,    -- días hasta el próximo repaso
    reps        INTEGER DEFAULT 0,
    lapses      INTEGER DEFAULT 0,
    due         TEXT,                 -- fecha ISO del próximo repaso
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    word_id INTEGER REFERENCES words(id),
    rating INTEGER,                   -- 1=fallé 2=difícil 3=bien 4=fácil
    reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Umbrales de dominio (en días de intervalo)
LEARNING_MAX = 7      # < 7 días -> "aprendiendo"
KNOWN_MIN = 30        # >= 30 días -> "dominada"


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.executescript(SCHEMA)


def status_of(interval: int, reps: int) -> str:
    if reps == 0:
        return "nueva"
    if interval < LEARNING_MAX:
        return "aprendiendo"
    if interval < KNOWN_MIN:
        return "mas_o_menos"
    return "dominada"


# ───────────────────────── SM-2 (clasifica dominio) ─────────────────────────
def _sm2(ease: float, interval: int, reps: int, rating: int):
    """Devuelve (nuevo_ease, nuevo_interval, nuevos_reps, hubo_fallo)."""
    q = {1: 1, 2: 3, 3: 4, 4: 5}[rating]   # 1..4 -> calidad SM-2
    lapse = q < 3
    if lapse:
        reps, interval = 0, 1              # fallaste -> vuelve mañana
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    ease = max(1.3, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    return ease, interval, reps, lapse


# ───────────────────────── Altas de vocabulario ─────────────────────────
def add_word(lemma: str, translation: str = "", topic: str = "",
             pos: str = "", word: str = "", example_en: str = "", example_es: str = ""):
    """Inserta una palabra nueva (si no existe). due=hoy para que entre al estudio."""
    with connect() as con:
        con.execute(
            """INSERT OR IGNORE INTO words
               (lemma, word, pos, topic, translation, example_en, example_es, due)
               VALUES (?,?,?,?,?,?,?,?)""",
            (lemma.lower().strip(), word or lemma, pos, topic, translation,
             example_en, example_es, date.today().isoformat()),
        )


def add_words_from_text(text_en: str, topic: str = "", min_len: int = 3):
    """Extrae lemas de contenido con spaCy (import perezoso) y los da de alta."""
    import spacy
    nlp = spacy.load("en_core_web_sm")
    seen = set()
    for tok in nlp(text_en):
        if tok.is_alpha and not tok.is_stop and tok.pos_ in {"NOUN", "VERB", "ADJ", "ADV"}:
            lemma = tok.lemma_.lower()
            if len(lemma) >= min_len and lemma not in seen:
                seen.add(lemma)
                add_word(lemma, pos=tok.pos_, topic=topic, word=tok.text)
    return len(seen)


# ───────────────────────── Registrar respuestas ─────────────────────────
def review_word(word_id: int, rating: int):
    """Tras responder en un test: actualiza el dominio con SM-2 y reagenda."""
    with connect() as con:
        w = con.execute("SELECT ease, interval, reps, lapses FROM words WHERE id=?",
                        (word_id,)).fetchone()
        if not w:
            return
        ease, interval, reps, lapse = _sm2(w["ease"], w["interval"], w["reps"], rating)
        lapses = w["lapses"] + (1 if lapse else 0)
        due = (date.today() + timedelta(days=interval)).isoformat()
        con.execute(
            "UPDATE words SET ease=?, interval=?, reps=?, lapses=?, due=? WHERE id=?",
            (ease, interval, reps, lapses, due, word_id),
        )
        con.execute("INSERT INTO reviews (word_id, rating) VALUES (?,?)", (word_id, rating))


# ───────────────────────── Qué estudiar hoy ─────────────────────────
def due_today(limit: int = 20) -> list[dict]:
    """Palabras a estudiar: vencidas o nuevas. Las dominadas quedan fuera porque
    su 'due' está a 30+ días vista. Prioriza fallos recientes y novedades."""
    today = date.today().isoformat()
    with connect() as con:
        rows = con.execute(
            """SELECT * FROM words
               WHERE due IS NULL OR due <= ?
               ORDER BY (reps = 0) DESC,        -- nuevas primero
                        lapses DESC,            -- las que más fallas
                        interval ASC            -- las más frágiles
               LIMIT ?""",
            (today, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def status_counts() -> dict:
    """Conteo por nivel de dominio (para el panel)."""
    out = {"nueva": 0, "aprendiendo": 0, "mas_o_menos": 0, "dominada": 0}
    with connect() as con:
        for r in con.execute("SELECT interval, reps FROM words"):
            out[status_of(r["interval"], r["reps"])] += 1
    return out


# ───────────────────────── Temas débiles (para GraphRAG) ─────────────────────────
def weak_topics(limit: int = 5) -> list[dict]:
    """Temas/reglas donde más fallas, para reforzar con material del grafo."""
    with connect() as con:
        rows = con.execute(
            """SELECT COALESCE(NULLIF(w.topic,''), w.pos, 'sin_tema') AS tema,
                      SUM(CASE WHEN r.rating = 1 THEN 1 ELSE 0 END) AS fallos,
                      COUNT(*) AS intentos
               FROM reviews r JOIN words w ON w.id = r.word_id
               GROUP BY tema
               HAVING intentos > 0
               ORDER BY fallos DESC, (CAST(SUM(CASE WHEN r.rating=1 THEN 1 ELSE 0 END) AS REAL)/COUNT(*)) DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
````

## 11.3 `graphrag.py`

````python
"""
graphrag.py — GraphRAG 100% local para el sistema de aprendizaje de inglés.

En vez de (o además de) un RAG vectorial, construye un GRAFO DE CONOCIMIENTO a partir
de las transcripciones. Nodos = entidades (WORD / GRAMMAR / TOPIC / PHRASE).
Aristas = relaciones entre ellas. Para responder: busca los nodos relevantes a la
pregunta, recorre sus conexiones (vecindario) y sintetiza la respuesta con el LLM local.

Todo local y perezoso (nada se descarga/carga al importar):
  * Extracción de entidades/relaciones -> LLM vía Ollama (el modelo elegido en el front)
  * Grafo -> networkx en memoria, persistido a JSON
  * Enlace pregunta->nodos -> embeddings (sentence-transformers, bge-m3)
"""

from __future__ import annotations
import json
import re
from pathlib import Path

import networkx as nx
import models as M   # reutiliza el LLM perezoso (Ollama)

GRAPH_PATH = Path("data/graph.json")
EMB_PATH = Path("data/graph_embeddings.json")

# ───────────────────────── Embeddings (perezosos) ─────────────────────────
_EMB = {"model": None}


def _embedder():
    if _EMB["model"] is None:
        from sentence_transformers import SentenceTransformer
        _EMB["model"] = SentenceTransformer("BAAI/bge-m3")   # multilingüe EN+ES
    return _EMB["model"]


def _embed(texts: list[str]) -> list[list[float]]:
    return _embedder().encode(texts, normalize_embeddings=True).tolist()


# ───────────────────────── Extracción con el LLM ─────────────────────────
EXTRACT_PROMPT = """Eres un extractor de conocimiento para aprender inglés.
Del TEXTO en inglés extrae entidades y relaciones.

Tipos de entidad:
- WORD: palabra/vocabulario clave en inglés, en forma base.
- GRAMMAR: regla o estructura (p.ej. "present perfect", "phrasal verb").
- TOPIC: tema del que trata el texto.
- PHRASE: expresión o colocación útil.

Devuelve SOLO JSON válido, sin texto extra, con esta forma exacta:
{{"entities":[{{"name":"...","type":"WORD|GRAMMAR|TOPIC|PHRASE","description":"breve en español"}}],
"relations":[{{"source":"...","target":"...","description":"cómo se relacionan"}}]}}

TEXTO:
\"\"\"{chunk}\"\"\"
JSON:"""


def chunk_text(text: str, size: int = 220, overlap: int = 40) -> list[str]:
    """Trocea por palabras; chunks pequeños = mejor extracción de entidades."""
    words = text.split()
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + size]))
        i += size - overlap
    return out


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, re.S)   # primer objeto JSON
    return json.loads(m.group(0) if m else raw)


def _norm(name: str) -> str:
    return name.strip().lower()


# ───────────────────────── Construcción del grafo ─────────────────────────
def build_graph(text: str, source: str, llm_model: str, g: nx.Graph | None = None) -> nx.Graph:
    """Añade entidades/relaciones de 'text' al grafo. 'source' = nombre del material."""
    g = g if g is not None else nx.Graph()
    for chunk in chunk_text(text):
        try:
            raw = M.llm_chat(llm_model, EXTRACT_PROMPT.format(chunk=chunk),
                             system="Responde únicamente con JSON válido.")
            data = _parse_json(raw)
        except Exception:
            continue  # si un chunk falla, seguimos con el resto

        for e in data.get("entities", []):
            name = e.get("name", "").strip()
            if not name:
                continue
            key = _norm(name)
            if key in g:
                g.nodes[key]["sources"].add(source)
            else:
                g.add_node(key, name=name, type=e.get("type", "WORD"),
                           description=e.get("description", ""), sources={source})

        for r in data.get("relations", []):
            s, t = _norm(r.get("source", "")), _norm(r.get("target", ""))
            if s in g and t in g and s != t:
                g.add_edge(s, t, description=r.get("description", "relacionado"))
    return g


# ───────────────────────── Persistencia (robusta entre versiones) ─────────────────────────
def save_graph(g: nx.Graph):
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "nodes": [
            {"id": n, **{k: (sorted(v) if isinstance(v, set) else v) for k, v in d.items()}}
            for n, d in g.nodes(data=True)
        ],
        "edges": [{"source": u, "target": v, **d} for u, v, d in g.edges(data=True)],
    }
    GRAPH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_graph() -> nx.Graph:
    if not GRAPH_PATH.exists():
        return nx.Graph()
    data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    g = nx.Graph()
    for n in data["nodes"]:
        n = dict(n)
        nid = n.pop("id")
        if "sources" in n:
            n["sources"] = set(n["sources"])
        g.add_node(nid, **n)
    for e in data["edges"]:
        e = dict(e)
        g.add_edge(e.pop("source"), e.pop("target"), **e)
    return g


def build_node_embeddings(g: nx.Graph):
    """Embebe cada nodo (nombre + descripción) para enlazar preguntas con el grafo."""
    nodes = list(g.nodes())
    if not nodes:
        return
    texts = [f"{g.nodes[n]['name']}: {g.nodes[n].get('description', '')}" for n in nodes]
    EMB_PATH.write_text(json.dumps({"nodes": nodes, "vecs": _embed(texts)}), encoding="utf-8")


def index_material(text: str, source: str, llm_model: str):
    """Pipeline completo de indexado: grafo + embeddings, persistido."""
    g = build_graph(text, source, llm_model, g=load_graph())
    save_graph(g)
    build_node_embeddings(g)
    return g.number_of_nodes(), g.number_of_edges()


# ───────────────────────── Consulta (GraphRAG) ─────────────────────────
def query(question: str, llm_model: str, hops: int = 1, top_k: int = 5) -> str:
    g = load_graph()
    if g.number_of_nodes() == 0:
        return "El grafo está vacío. Indexa material primero."
    if not EMB_PATH.exists():
        build_node_embeddings(g)

    import numpy as np
    idx = json.loads(EMB_PATH.read_text(encoding="utf-8"))
    vecs = np.array(idx["vecs"])
    q = np.array(_embed([question])[0])
    sims = vecs @ q   # coseno (vectores normalizados)
    order = sims.argsort()[::-1]
    seeds = [idx["nodes"][i] for i in order[:top_k] if idx["nodes"][i] in g]

    # Vecindario: nodos a 'hops' saltos de cada semilla
    sub = set(seeds)
    for s in seeds:
        sub |= set(nx.ego_graph(g, s, radius=hops).nodes())

    lines = ["ENTIDADES:"]
    for n in sub:
        d = g.nodes[n]
        lines.append(f"- {d['name']} ({d.get('type', '')}): {d.get('description', '')}")
    lines.append("\nRELACIONES:")
    for u, v, d in g.subgraph(sub).edges(data=True):
        lines.append(f"- {g.nodes[u]['name']} —[{d.get('description', 'rel')}]— {g.nodes[v]['name']}")
    context = "\n".join(lines)

    prompt = f"""Usa SOLO este grafo de conocimiento para responder en español,
explicando con ejemplos claros para un estudiante de inglés.

{context}

PREGUNTA: {question}
RESPUESTA:"""
    return M.llm_chat(llm_model, prompt)
````

## 11.4 `app_validacion.py`

````python
"""
app_validacion.py — Front local (Streamlit).

Flujo pedido:
  1) El usuario elige el LLM y los modelos ASR (nada se descarga hasta que pulsa).
  2) Sube un video.
  3) Se transcribe con el 1er modelo ASR de la lista.
  4) Se REPRODUCE el video con la transcripción como subtítulos para validar.
  5) Si está bien -> Guardar. Si está mal -> descartar y reintentar con el siguiente modelo.

Ejecutar:  streamlit run app_validacion.py
Requiere Ollama corriendo y ffmpeg instalado.
"""

import json
import tempfile
from pathlib import Path

import streamlit as st
import models as M

st.set_page_config(page_title="Inglés local — Validar transcripción", layout="wide")
st.title("🎬 Subir video → validar transcripción → guardar")

# Carpetas de salida
OUT = Path("data/transcripts"); OUT.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.gettempdir())

# Estado de sesión
ss = st.session_state
ss.setdefault("attempt", 0)          # índice del modelo ASR que estamos probando
ss.setdefault("result", None)        # dict con segments, vtt_path, asr_key
ss.setdefault("video_path", None)

# ════════════════════ SIDEBAR: selección de modelos ════════════════════
with st.sidebar:
    st.header("⚙️ Modelos (no se descarga nada hasta pulsar)")

    # ---- LLM ----
    st.subheader("LLM")
    installed = M.llm_installed()
    llm_choice = st.selectbox(
        "Modelo activo",
        options=list(M.LLM_CATALOG.keys()),
        format_func=lambda k: M.LLM_CATALOG[k]["label"] + (" ✅" if k in installed else " (no descargado)"),
    )
    ss["llm"] = llm_choice
    if llm_choice not in installed:
        if st.button(f"⬇️ Descargar {llm_choice}"):
            bar = st.progress(0.0, text="Descargando…")
            for ch in M.llm_pull(llm_choice):
                tot, done = ch.get("total"), ch.get("completed")
                if tot:
                    bar.progress(min(done / tot, 1.0), text=ch.get("status", "Descargando…"))
            bar.progress(1.0, text="Listo")
            st.rerun()

    st.divider()

    # ---- ASR: lista ORDENADA de modelos a probar ----
    st.subheader("ASR — orden de prueba")
    asr_order = st.multiselect(
        "Se probarán en este orden cuando descartes una transcripción:",
        options=list(M.ASR_CATALOG.keys()),
        default=["parakeet-tdt-0.6b-v3", "whisper-large-v3-turbo"],
        format_func=lambda k: M.ASR_CATALOG[k]["label"],
    )
    st.caption("El peso de cada ASR se descarga de HuggingFace en su primer uso.")
    if st.button("🧹 Liberar VRAM (descargar modelo de memoria)"):
        M.free_asr()
        st.toast("VRAM liberada")

# ════════════════════ MAIN: subir y validar ════════════════════
up = st.file_uploader("Sube un video", type=["mp4", "mkv", "mov", "webm", "avi", "m4v"])

if up and not asr_order:
    st.warning("Elige al menos un modelo ASR en la barra lateral.")

if up and asr_order:
    # Guardar el video subido a un archivo temporal (una sola vez)
    if ss["video_path"] is None or Path(ss["video_path"]).name != up.name:
        vid = TMP / up.name
        vid.write_bytes(up.getbuffer())
        ss["video_path"] = str(vid)
        ss["attempt"] = 0
        ss["result"] = None

    # Modelo ASR del intento actual
    if ss["attempt"] >= len(asr_order):
        st.error("Se acabaron los modelos de la lista y ninguna transcripción te convenció. "
                 "Añade otro modelo ASR o sube otro video.")
    else:
        asr_key = asr_order[ss["attempt"]]
        st.info(f"Intento {ss['attempt'] + 1}/{len(asr_order)} · Modelo: **{M.ASR_CATALOG[asr_key]['label']}**")

        # Botón para transcribir (descarga/carga el ASR solo aquí)
        if ss["result"] is None or ss["result"]["asr_key"] != asr_key:
            if st.button("📝 Transcribir con este modelo"):
                with st.spinner("Transcribiendo… (la 1ª vez descarga el modelo)"):
                    segs = M.transcribe_media(ss["video_path"], asr_key, language="en")
                    vtt = M.write_vtt(segs, str(TMP / f"{Path(up.name).stem}.{asr_key}.vtt"))
                    ss["result"] = {"segments": segs, "vtt_path": vtt, "asr_key": asr_key}
                st.rerun()

        # Reproducir video + subtítulos para VALIDAR
        if ss["result"] and ss["result"]["asr_key"] == asr_key:
            st.video(ss["video_path"], subtitles={"Inglés (transcripción)": ss["result"]["vtt_path"]})

            with st.expander("Ver texto transcrito"):
                st.write(" ".join(s.text for s in ss["result"]["segments"]))

            st.markdown("**¿La transcripción es correcta?**")
            c1, c2 = st.columns(2)

            if c1.button("✅ Está bien — Guardar", use_container_width=True):
                segs = ss["result"]["segments"]
                payload = {
                    "source": up.name,
                    "asr_model": asr_key,
                    "text_en": " ".join(s.text for s in segs),
                    "segments": [s.__dict__ for s in segs],
                    # text_es se rellena luego con el LLM elegido (M.llm_chat)
                }
                out_file = OUT / f"{Path(up.name).stem}.json"
                out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                st.success(f"Guardado en {out_file}")
                # listo para el siguiente video
                ss["result"] = None; ss["video_path"] = None; ss["attempt"] = 0

            if c2.button("❌ Mal — Probar otro modelo", use_container_width=True):
                ss["attempt"] += 1
                ss["result"] = None
                M.free_asr()  # libera el modelo rechazado antes de cargar el siguiente
                st.rerun()
````

## 11.5 `app_estudio.py`

````python
"""
app_estudio.py — Front del motor adaptativo (estudiar + progreso + refuerzo).

Cierra el bucle que pediste:
  Estudias -> el sistema clasifica tu dominio -> no repite lo dominado ->
  detecta tus temas débiles -> GraphRAG te trae material para reforzarlos.

Ejecutar:  streamlit run app_estudio.py
"""

import streamlit as st
import learning as L
import models as M
import graphrag as G

st.set_page_config(page_title="Estudiar inglés (adaptativo)", layout="wide")
L.init_db()

ss = st.session_state
ss.setdefault("queue", [])     # palabras pendientes de la sesión
ss.setdefault("revealed", False)

installed = M.llm_installed()
llm = st.sidebar.selectbox(
    "LLM activo",
    options=list(M.LLM_CATALOG.keys()),
    format_func=lambda k: M.LLM_CATALOG[k]["label"] + (" ✅" if k in installed else " (no descargado)"),
)

tab_study, tab_progress, tab_import = st.tabs(["📚 Estudiar hoy", "📊 Progreso", "➕ Importar vocabulario"])

# ───────────────── Estudiar (flashcards adaptativas) ─────────────────
with tab_study:
    if st.button("🎯 Empezar sesión (solo lo pendiente, omite lo dominado)"):
        ss["queue"] = L.due_today(limit=20)
        ss["revealed"] = False

    if not ss["queue"]:
        st.info("Pulsa «Empezar sesión». Si no aparece nada, no tienes nada que repasar hoy "
                "(¡o aún no importaste vocabulario!).")
    else:
        card = ss["queue"][0]
        st.caption(f"Quedan {len(ss['queue'])} · tema: {card.get('topic') or card.get('pos') or '—'} · "
                   f"fallos previos: {card['lapses']}")
        st.markdown(f"## {card['word'] or card['lemma']}")

        if not ss["revealed"]:
            if st.button("Mostrar significado"):
                ss["revealed"] = True
                st.rerun()
        else:
            st.markdown(f"**Traducción:** {card['translation'] or '(sin traducir aún)'}")
            if card["example_en"]:
                st.markdown(f"*{card['example_en']}*")
            st.markdown("**¿Qué tal lo sabías?**")
            c1, c2, c3, c4 = st.columns(4)
            ratings = [("❌ Fallé", 1), ("😬 Difícil", 2), ("🙂 Bien", 3), ("😎 Fácil", 4)]
            cols = [c1, c2, c3, c4]
            for col, (label, rating) in zip(cols, ratings):
                if col.button(label, use_container_width=True):
                    L.review_word(card["id"], rating)   # actualiza dominio (SM-2)
                    failed = ss["queue"].pop(0)
                    if rating == 1:                     # lo que fallas vuelve en esta misma sesión
                        ss["queue"].append(failed)
                    ss["revealed"] = False
                    st.rerun()

# ───────────────── Progreso + temas débiles ─────────────────
with tab_progress:
    counts = L.status_counts()
    c = st.columns(4)
    c[0].metric("Nuevas", counts["nueva"])
    c[1].metric("Aprendiendo", counts["aprendiendo"])
    c[2].metric("Más o menos", counts["mas_o_menos"])
    c[3].metric("Dominadas", counts["dominada"])
    st.bar_chart(counts)

    st.subheader("Tus temas más débiles")
    weak = L.weak_topics()
    if not weak:
        st.caption("Aún no hay suficientes respuestas para detectar puntos débiles.")
    for w in weak:
        ratio = (w["fallos"] / w["intentos"]) if w["intentos"] else 0
        st.write(f"**{w['tema']}** — {w['fallos']}/{w['intentos']} fallos ({ratio:.0%})")
        if st.button(f"📖 Reforzar «{w['tema']}» con mi material", key=f"r_{w['tema']}"):
            with st.spinner("Buscando ejemplos en tu grafo de conocimiento…"):
                ans = G.query(f"Explícame y dame ejemplos del tema: {w['tema']}", llm)
            st.markdown(ans)

# ───────────────── Importar vocabulario desde transcripciones ─────────────────
with tab_import:
    import json
    from pathlib import Path
    tdir = Path("data/transcripts")
    files = sorted(tdir.glob("*.json")) if tdir.exists() else []
    if not files:
        st.info("No hay transcripciones. Valida y guarda un video primero (app_validacion.py).")
    else:
        name = st.selectbox("Transcripción", [f.name for f in files])
        topic = st.text_input("Etiqueta de tema (opcional, p.ej. 'viajes', 'present perfect')")
        if st.button("Extraer e importar vocabulario (spaCy)"):
            data = json.loads((tdir / name).read_text(encoding="utf-8"))
            with st.spinner("Lematizando y dando de alta palabras nuevas…"):
                n = L.add_words_from_text(data.get("text_en", ""), topic=topic)
            st.success(f"{n} palabras procesadas. Ve a «Estudiar hoy».")
````

## 11.6 `app_graphrag.py`

````python
"""
app_graphrag.py — Front local para GraphRAG (indexar + chatear).

Ejecutar:  streamlit run app_graphrag.py
Requiere Ollama corriendo. Usa el LLM elegido (mismo catálogo que models.py).
"""

import json
from pathlib import Path

import streamlit as st
import models as M
import graphrag as G

st.set_page_config(page_title="GraphRAG local", layout="wide")
st.title("🕸️ GraphRAG — grafo de conocimiento de tu inglés")

ss = st.session_state
installed = M.llm_installed()
llm = st.sidebar.selectbox(
    "LLM activo",
    options=list(M.LLM_CATALOG.keys()),
    format_func=lambda k: M.LLM_CATALOG[k]["label"] + (" ✅" if k in installed else " (no descargado)"),
)

tab_index, tab_chat = st.tabs(["📥 Indexar material", "💬 Preguntar"])

# ───── Indexar transcripciones ya guardadas ─────
with tab_index:
    st.caption("Toma las transcripciones guardadas en data/transcripts/ y las añade al grafo.")
    tdir = Path("data/transcripts")
    files = sorted(tdir.glob("*.json")) if tdir.exists() else []
    if not files:
        st.info("No hay transcripciones aún. Valida y guarda un video primero.")
    else:
        pick = st.multiselect("Material a indexar", [f.name for f in files], default=[f.name for f in files])
        if st.button("🔨 Construir/actualizar grafo"):
            prog = st.progress(0.0)
            for i, name in enumerate(pick, 1):
                data = json.loads((tdir / name).read_text(encoding="utf-8"))
                with st.spinner(f"Indexando {name}…"):
                    n, e = G.index_material(data.get("text_en", ""), name, llm)
                prog.progress(i / len(pick))
            st.success(f"Grafo: {n} nodos, {e} relaciones.")

    g = G.load_graph()
    st.metric("Nodos en el grafo", g.number_of_nodes())
    st.metric("Relaciones", g.number_of_edges())

# ───── Chatear sobre el grafo ─────
with tab_chat:
    hops = st.slider("Saltos de vecindario", 1, 3, 1)
    q = st.text_input("Pregunta (ej.: '¿qué sé sobre phrasal verbs?', 'conecta la palabra run con otros temas')")
    if st.button("Responder") and q:
        with st.spinner("Recorriendo el grafo…"):
            ans = G.query(q, llm, hops=hops)
        st.markdown(ans)
````

---

Con esto tienes el plan final completo en un solo documento: la arquitectura de los tres cerebros (motor adaptativo, GraphRAG y Obsidian opcional), el bucle de aprendizaje y el código de los 6 módulos, todo 100% local y probado a nivel de sintaxis y lógica del motor adaptativo.
