"""Rewrite references only in Docker build layer, never in git-tracked upstream files."""
from pathlib import Path

ROOT = Path("/app")
OLD_ICON = "https://creazilla-store.fra1.digitaloceanspaces.com/emojis/49647/pizza-emoji-clipart-md.png"
OLD_BACKGROUND = "https://i.postimg.cc/ry3p76HY/italian-seamless-free-vector-pattern3.png"

for filename in ("static/static.py", "static/configure.py", "static/uprot.html"):
    path = ROOT / filename
    source = path.read_text(encoding="utf-8")
    source = source.replace(OLD_ICON, "/icon.png")
    source = source.replace(OLD_BACKGROUND, "/background.png")
    source = source.replace('href="/icon.png" type="image/x-icon"', 'href="/icon.png" type="image/png"')
    path.write_text(source, encoding="utf-8")

path = ROOT / "run.py"
source = path.read_text(encoding="utf-8")
import_line = "from fastapi.responses import JSONResponse,RedirectResponse,HTMLResponse"
if import_line not in source:
    raise RuntimeError("Cannot locate upstream FastAPI response import")
source = source.replace(import_line, import_line + ",FileResponse", 1)

anchor = "@app.get('/configure',response_class=HTMLResponse)"
if anchor not in source:
    raise RuntimeError("Cannot locate configure route")
routes = """@app.get('/icon.png', include_in_schema=False)
def local_icon():
    return FileResponse('/app/docker-assets/pizza.png', media_type='image/png')

@app.get('/background.png', include_in_schema=False)
def local_background():
    return FileResponse('/app/docker-assets/background.png', media_type='image/png')

"""
source = source.replace(anchor, routes + anchor, 1)

anchor = "def addon_manifest(config: str):"
if anchor not in source:
    raise RuntimeError("Cannot find upstream addon_manifest signature")
source = source.replace(anchor, "def addon_manifest(config: str, request: Request):", 1)
anchor = "    manifest_copy = MANIFEST.copy()"
if anchor not in source:
    raise RuntimeError("Cannot find manifest initialization")
injected = """    # Advertise an icon served by this instance (not an external image host).
    # Strip comma-separated proxy header values to avoid malformed URLs.
    proto = request.headers.get('x-forwarded-proto', request.url.scheme).split(',')[0].strip()
    host = request.headers.get('x-forwarded-host', request.headers.get('host', request.url.netloc)).split(',')[0].strip()
    manifest_copy['logo'] = f"{proto}://{host}/icon.png"
"""
source = source.replace(anchor, anchor + "\n" + injected.rstrip("\n"), 1)
# Prevent a stale external logo URL in the default manifest object as well.
source = source.replace(OLD_ICON, "/icon.png")
path.write_text(source, encoding="utf-8")
print("Applied build-only, self-hosted image asset patches")
