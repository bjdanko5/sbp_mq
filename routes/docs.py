"""Просмотр Markdown-документации из docs/ через браузер.

Единый источник — файлы docs/*.md (те же, что в репозитории).
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from modules import docs_render
from modules.docs_templates import INDEX_PAGE, PAGE

router = APIRouter(prefix="/project-docs", tags=["docs"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def docs_index():
    items = docs_render.list_docs()
    if not items:
        return HTMLResponse(INDEX_PAGE.format(items="<li>Нет документов</li>"))

    rows = []
    for it in items:
        rows.append(
            f'<li><a href="/project-docs/{it["name"]}">{it["title"]}</a>'
            f'<span class="name">docs/{it["name"]}.md</span></li>'
        )
    return HTMLResponse(INDEX_PAGE.format(items="\n".join(rows)))


@router.get("/{name:path}", response_class=HTMLResponse)
async def docs_view(name: str):
    doc = docs_render.render_doc(name)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Документ не найден: {name}")

    nav_items = docs_render.list_docs()
    nav_html = []
    for it in nav_items:
        cls = "active" if it["name"] == doc["name"] else ""
        nav_html.append(
            f'<a class="{cls}" href="/project-docs/{it["name"]}">{it["title"]}</a>'
        )

    html = PAGE.format(
        title=doc["title"],
        name=doc["name"],
        body=doc["html"],
        nav="\n".join(nav_html),
        index_active="",
    )
    return HTMLResponse(html)