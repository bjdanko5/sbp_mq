"""
Рендер Markdown-документации из docs/ в HTML.
Единый источник — файлы docs/*.md (те же, что в репозитории).

Особенности:
- Принимает name как с расширением .md, так и без — чтобы ссылки
  в .md-файлах ([x](x.md)) работали и на GitHub, и в /project-docs.
- Защита от path traversal (выход за пределы docs/).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

# Единый экземпляр рендерера
_md = (
    MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
    .enable("table")
    .use(footnote_plugin)
    .use(tasklists_plugin)
)

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def list_docs() -> list[dict]:
    """Список всех .md файлов в docs/ (рекурсивно), с заголовком."""
    if not DOCS_DIR.exists():
        return []
    items: list[dict] = []
    for p in sorted(DOCS_DIR.rglob("*.md")):
        rel = p.relative_to(DOCS_DIR).with_suffix("")
        title = _extract_title(p) or rel.as_posix()
        items.append(
            {
                "name": rel.as_posix(),      # напр. "architecture" или "modules/monitor"
                "title": title,
                "path": p,
            }
        )
    return items


def _extract_title(path: Path) -> Optional[str]:
    """Первый H1 в файле — как заголовок."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return None


def render_doc(name: str) -> Optional[dict]:
    """
    Рендерит docs/<name>.md в HTML.
    Возвращает dict {title, html, name} или None, если файл не найден
    или выходит за пределы docs/.

    Принимает name как с расширением .md, так и без — чтобы ссылки
    в .md-файлах работали и на GitHub (относительные), и в /project-docs.
    """
    # Защита от path traversal
    safe = name.strip().lstrip("/").replace("..", "")

    # Срезаем .md, если есть — чтобы [x](x.md) работало в обоих контекстах
    if safe.endswith(".md"):
        safe = safe[:-3]

    candidate = (DOCS_DIR / f"{safe}.md").resolve()

    try:
        candidate.relative_to(DOCS_DIR.resolve())
    except ValueError:
        return None

    if not candidate.is_file():
        return None

    md_text = candidate.read_text(encoding="utf-8")
    body_html = _md.render(md_text)
    title = _extract_title(candidate) or safe

    return {
        "name": safe,
        "title": title,
        "html": body_html,
    }