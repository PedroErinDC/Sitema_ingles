"""
notes.py - Exportacion simple a Markdown estilo Obsidian.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import content as C
import learning as L


def export_markdown(title: str, body: str, folder: Path | None = None) -> Path:
    C.ensure_dirs()
    out_dir = folder or C.OBSIDIAN_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{C.slugify(title)}.md"
    path = out_dir / filename
    path.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")
    return path


def build_study_snapshot(limit_words: int = 20, limit_topics: int = 10, limit_grammar: int = 10) -> str:
    due_words = L.due_today(limit=limit_words)
    weak_topics = L.weak_topics(limit=limit_topics)
    due_grammar = L.grammar_due_today(limit=limit_grammar)
    rank = L.grammar_rank_summary()

    lines = [
        "## Palabras pendientes",
        "",
    ]
    if due_words:
        for word in due_words:
            lines.append(
                f"- [[{word['lemma']}]]: {word.get('translation') or 'sin traduccion'} "
                f"(tema: {word.get('topic') or word.get('pos') or '-'})"
            )
    else:
        lines.append("- Sin palabras pendientes.")

    lines.extend(["", "## Temas debiles", ""])
    if weak_topics:
        for item in weak_topics:
            lines.append(f"- [[{item['tema']}]]: {item['fallos']}/{item['intentos']} fallos")
    else:
        lines.append("- Aun sin datos suficientes.")

    lines.extend(["", "## Gramatica pendiente", ""])
    if due_grammar:
        for item in due_grammar:
            lines.append(f"- [[{item['title']}]] ({item['level']}): {item.get('description') or 'sin descripcion'}")
    else:
        lines.append("- Sin gramatica pendiente.")

    lines.extend(
        [
            "",
            "## Rango gramatical",
            "",
            f"- Rango actual: **{rank['rank']}**",
            f"- Dominio estimado: **{rank['best_level']}**",
        ]
    )
    return "\n".join(lines)
