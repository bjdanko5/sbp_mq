"""HTML-шаблон для просмотра документации. Mermaid.js — через CDN."""

PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — SBP MQ docs</title>
<style>
  :root {{
    --bg: #0f1115; --panel: #161a22; --text: #e6e6e6;
    --muted: #9aa4b2; --accent: #4ea1ff; --border: #262b36;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}
  .layout {{ display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }}
  aside {{
    background: var(--panel); border-right: 1px solid var(--border);
    padding: 20px; overflow-y: auto; position: sticky; top: 0; height: 100vh;
  }}
  aside h2 {{ font-size: 14px; color: var(--muted); margin: 0 0 12px; text-transform: uppercase; letter-spacing: .08em; }}
  aside a {{ display: block; color: var(--text); text-decoration: none; padding: 6px 8px; border-radius: 6px; font-size: 14px; }}
  aside a:hover {{ background: rgba(78,161,255,.12); }}
  aside a.active {{ background: rgba(78,161,255,.2); color: var(--accent); }}
  main {{ padding: 32px 40px; max-width: 980px; }}
  main h1, main h2, main h3 {{ border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  main a {{ color: var(--accent); }}
  main code {{ background: #1e2330; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  main pre {{ background: #1e2330; padding: 14px; border-radius: 8px; overflow-x: auto; }}
  main pre code {{ background: transparent; padding: 0; }}
  main table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  main th, main td {{ border: 1px solid var(--border); padding: 8px 10px; text-align: left; }}
  main th {{ background: #1a1f2a; }}
  main blockquote {{ border-left: 3px solid var(--accent); margin: 12px 0; padding: 4px 14px; color: var(--muted); }}
  .mermaid {{ background: #1a1f2a; border-radius: 8px; padding: 16px; margin: 16px 0; text-align: center; }}
  details {{ background: #1a1f2a; border-radius: 8px; padding: 8px 14px; margin: 12px 0; }}
  summary {{ cursor: pointer; color: var(--muted); }}
  .topbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
  .topbar .brand {{ color: var(--muted); font-size: 13px; }}
  .topbar .brand a {{ color: var(--muted); }}
</style>
</head>
<body>
<div class="layout">
  <aside>
    <h2>Документация</h2>
    <a href="/project-docs" class="{index_active}">Индекс</a>
    {nav}
  </aside>
  <main>
    <div class="topbar">
      <div class="brand"><a href="/project-docs">SBP MQ</a> / docs / {name}</div>
      <div class="brand"><a href="/health">health</a></div>
    </div>
    {body}
  </main>
</div>

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {{ primaryColor: '#4ea1ff' }}
  }});
</script>
</body>
</html>
"""


INDEX_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>SBP MQ — документация</title>
<style>
  body {{ background:#0f1115; color:#e6e6e6; font:15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 40px; }}
  h1 {{ border-bottom:1px solid #262b36; padding-bottom:8px; }}
  a {{ color:#4ea1ff; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  ul {{ list-style:none; padding:0; }}
  li {{ padding:8px 0; border-bottom:1px solid #1a1f2a; }}
  .name {{ color:#9aa4b2; font-size:13px; margin-left:8px; }}
</style>
</head>
<body>
  <h1>SBP MQ — документация</h1>
  <p>Актуально на коммит <code>2b2f5aa</code> · <a href="/health/detailed">/health/detailed</a></p>
  <ul>
    {items}
  </ul>
</body>
</html>
"""