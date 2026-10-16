#!/usr/bin/env python3
"""Local editor for the octopro.pro homepage reading list.

Runs only on this Mac. Opens a page in the browser where readings can be
added, edited, reordered and removed. "Publish" writes them into
site/index.html, commits, and pushes to GitHub's main branch; Cloudflare
then publishes octopro.pro within about a minute.

Uses only the Python standard library and the Mac's existing git login.
"""
import html
import json
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "site" / "index.html"
PORT = 8790
START = re.compile(r"(<!-- READINGS:START[^>]*-->)(.*?)(<!-- READINGS:END -->)", re.S)
ITEM = re.compile(
    r'<li><h2>(.*?)</h2><p>(.*?)</p><a class="button" href="(.*?)">(.*?)</a></li>', re.S
)


def git(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def read_items():
    m = START.search(INDEX.read_text(encoding="utf-8"))
    if not m:
        raise RuntimeError("Markers READINGS:START / READINGS:END not found in site/index.html")
    return [
        {"title": html.unescape(t), "summary": html.unescape(s),
         "href": html.unescape(h), "label": html.unescape(l)}
        for t, s, h, l in ITEM.findall(m.group(2))
    ]


def render_block(items):
    if not items:
        return "\n"
    rows = "\n".join(
        '    <li><h2>{}</h2><p>{}</p><a class="button" href="{}">{}</a></li>'.format(
            html.escape(i["title"]), html.escape(i["summary"]),
            html.escape(i["href"], quote=True), html.escape(i["label"] or "Read"))
        for i in items
    )
    return '\n  <ul class="readings">\n' + rows + "\n  </ul>\n"


def render_page(items):
    page = INDEX.read_text(encoding="utf-8")
    return START.sub(lambda m: m.group(1) + render_block(items) + m.group(3), page, count=1)


def validate(items):
    out = []
    for n, i in enumerate(items, 1):
        item = {k: str(i.get(k, "")).strip() for k in ("title", "summary", "href", "label")}
        if not item["title"]:
            raise ValueError(f"Item {n}: the title is empty.")
        if not re.match(r"^(https://|/)", item["href"]):
            raise ValueError(f"Item {n}: the link must start with https:// or /")
        item["label"] = item["label"] or "Read"
        out.append(item)
    return out


def publish(items):
    code, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        raise RuntimeError(f"The repo is on branch '{branch}', not main. Nothing was published.")
    code, dirty = git("status", "--porcelain", "--", "site")
    if dirty:
        raise RuntimeError("site/ has unsaved changes made outside the editor. Nothing was published.\n" + dirty)
    code, out = git("pull", "--ff-only", "origin", "main")
    if code:
        raise RuntimeError("Could not update from GitHub first. Nothing was published.\n" + out)
    INDEX.write_text(render_page(items), encoding="utf-8")
    code, diff = git("status", "--porcelain", "--", "site/index.html")
    if not diff:
        return "No changes: the homepage already shows these readings."
    git("add", "site/index.html")
    code, out = git("commit", "-m", f"Update homepage readings ({len(items)} items)")
    if code:
        raise RuntimeError("Commit failed.\n" + out)
    code, out = git("push", "origin", "main")
    if code:
        git("reset", "--hard", "HEAD~1")
        raise RuntimeError("Push to GitHub failed; the local commit was undone. Nothing was published.\n" + out)
    return "Published. octopro.pro updates in about a minute."


EDITOR = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Edit homepage readings</title>
<style>
:root{--ink:#1c1c1c;--soft:#5c5c5c;--rule:#d9d9d9;--yellow:#f9cd57}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,-apple-system,sans-serif;color:var(--ink);background:#f6f6f4}
main{max-width:760px;margin:0 auto;padding:32px 20px 120px}h1{font-size:24px;margin:0 0 6px}.hint{color:var(--soft);margin:0 0 24px}
.item{background:#fff;border:1px solid var(--rule);border-radius:10px;padding:16px;margin:0 0 14px}
.item label{display:block;font-weight:600;font-size:13px;margin:10px 0 4px}.item label:first-child{margin-top:0}
input,textarea{width:100%;font:inherit;padding:8px 10px;border:1px solid #bbb;border-radius:6px}textarea{min-height:64px;resize:vertical}
.row{display:flex;gap:8px;margin-top:12px}button{font:600 14px system-ui,sans-serif;padding:8px 14px;border-radius:10px;border:1px solid var(--ink);background:#fff;cursor:pointer}
button.main{background:var(--yellow);border-color:var(--yellow)}button.danger{color:#a00;border-color:#a00}
.bar{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--rule);padding:12px 20px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
#msg{white-space:pre-wrap;margin-top:16px;padding:12px;border-radius:8px;display:none}#msg.ok{display:block;background:#e7f6ea}#msg.err{display:block;background:#fde8e8}
</style></head><body><main>
<h1>Homepage readings</h1><p class="hint">Add, edit, reorder or remove items. Nothing changes on octopro.pro until you click <b>Publish</b>.</p>
<div id="list"></div><button onclick="add()">+ Add a reading</button><div id="msg"></div></main>
<div class="bar"><button onclick="preview()">Preview</button><button class="main" onclick="pub()">Publish to octopro.pro</button></div>
<script>
let items=[];
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
function draw(){document.getElementById('list').innerHTML=items.map((it,i)=>`<div class="item">
<label>Title</label><input value="${esc(it.title)}" oninput="items[${i}].title=this.value">
<label>Short explanation</label><textarea oninput="items[${i}].summary=this.value">${esc(it.summary)}</textarea>
<label>Link (https://... or /page/)</label><input value="${esc(it.href)}" oninput="items[${i}].href=this.value">
<label>Button text</label><input value="${esc(it.label||'Read')}" oninput="items[${i}].label=this.value">
<div class="row"><button onclick="move(${i},-1)">Up</button><button onclick="move(${i},1)">Down</button><button class="danger" onclick="del(${i})">Remove</button></div></div>`).join('')||'<p class="hint">No readings yet.</p>';}
function add(){items.push({title:'',summary:'',href:'https://',label:'Read'});draw();}
function move(i,d){const j=i+d;if(j<0||j>=items.length)return;[items[i],items[j]]=[items[j],items[i]];draw();}
function del(i){items.splice(i,1);draw();}
function say(t,ok){const m=document.getElementById('msg');m.textContent=t;m.className=ok?'ok':'err';m.scrollIntoView({block:'nearest'});}
async function call(path){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(items)});return [r.ok,await r.text()];}
async function preview(){const [ok,t]=await call('/api/preview');if(!ok)return say(t,false);window.open('/preview/','_blank');}
async function pub(){if(!confirm('Publish these readings to octopro.pro now?'))return;say('Publishing...',true);const [ok,t]=await call('/api/publish');say(t,ok);}
fetch('/api/items').then(r=>r.json()).then(d=>{items=d;draw();}).catch(e=>say('Could not load items: '+e,false));
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    draft = None

    def send(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self.send(200, EDITOR, "text/html; charset=utf-8")
        if self.path == "/api/items":
            try:
                return self.send(200, json.dumps(read_items()), "application/json")
            except Exception as e:
                return self.send(500, str(e))
        if self.path == "/preview/":
            return self.send(200, Handler.draft or render_page(read_items()), "text/html; charset=utf-8")
        if self.path.startswith("/assets/") and ".." not in self.path:
            f = REPO / "site" / self.path.lstrip("/")
            if f.is_file():
                return self.send(200, f.read_bytes(), "image/png" if f.suffix == ".png" else "application/octet-stream")
        self.send(404, "Not found")

    def do_POST(self):
        try:
            items = validate(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))))
            if self.path == "/api/preview":
                Handler.draft = render_page(items)
                return self.send(200, "ok")
            if self.path == "/api/publish":
                return self.send(200, publish(items))
            self.send(404, "Not found")
        except Exception as e:
            self.send(400, str(e))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Homepage editor running at {url}\nClose this window to stop it.")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()
