#!/usr/bin/env python3
"""Local editor for the octopro.pro homepage reading list.

Runs only on this Mac. Opens the real homepage design in the browser in edit mode: click any
text to change it; readings can be added, reordered and removed. "Publish" writes them into
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
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}
START = re.compile(r"(<!-- READINGS:START[^>]*-->)(.*?)(<!-- READINGS:END -->)", re.S)
NAME = re.compile(r'(<span class="owner-name">)(.*?)(</span>)', re.S)
ITEM = re.compile(
    r'<li><h2>(.*?)</h2><p>(.*?)</p><a class="button" href="(.*?)">(.*?)</a></li>', re.S
)


def git(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def read_state():
    page = INDEX.read_text(encoding="utf-8")
    n = NAME.search(page)
    return {"name": html.unescape(n.group(2)) if n else "", "items": read_items(page)}


def read_items(page=None):
    m = START.search(page or INDEX.read_text(encoding="utf-8"))
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


def render_page(items, name=None):
    page = INDEX.read_text(encoding="utf-8")
    page = START.sub(lambda m: m.group(1) + render_block(items) + m.group(3), page, count=1)
    if name is not None:
        page = NAME.sub(lambda m: m.group(1) + html.escape(name) + m.group(3), page, count=1)
    return page


def validate(state):
    if not isinstance(state, dict):
        raise ValueError("Unexpected data from the editor page.")
    name = str(state.get("name", "")).strip()
    if not name:
        raise ValueError("The name in the top bar is empty.")
    return {"name": name, "items": validate_items(state.get("items", []))}


def validate_items(items):
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


def publish(state):
    items, name = state["items"], state["name"]
    code, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        raise RuntimeError(f"The repo is on branch '{branch}', not main. Nothing was published.")
    code, dirty = git("status", "--porcelain", "--", "site")
    if dirty:
        raise RuntimeError("site/ has unsaved changes made outside the editor. Nothing was published.\n" + dirty)
    code, out = git("pull", "--ff-only", "origin", "main")
    if code:
        raise RuntimeError("Could not update from GitHub first. Nothing was published.\n" + out)
    INDEX.write_text(render_page(items, name), encoding="utf-8")
    code, diff = git("status", "--porcelain", "--", "site/index.html")
    if not diff:
        return "No changes: the homepage already shows these readings."
    git("add", "site/index.html")
    code, out = git("commit", "-m", f"Update homepage ({len(items)} readings)")
    if code:
        raise RuntimeError("Commit failed.\n" + out)
    code, out = git("push", "origin", "main")
    if code:
        git("reset", "--hard", "HEAD~1")
        raise RuntimeError("Push to GitHub failed; the local commit was undone. Nothing was published.\n" + out)
    return "Published. octopro.pro updates in about a minute."


EDIT_MODE = r"""
<style>
body{padding-bottom:110px}
.em-note{background:#1c1c1c;color:#fff;font:600 14px system-ui,sans-serif;padding:10px 24px;text-align:center}
[contenteditable]{outline:1px dashed transparent;outline-offset:4px;border-radius:2px}
[contenteditable]:hover{outline-color:#bbb}[contenteditable]:focus{outline:2px dashed #1c1c1c}
[contenteditable]:empty::before{content:attr(data-ph);color:#aaa}
.em-link{display:flex;gap:8px;align-items:center;margin-top:12px;font:13px system-ui,sans-serif;color:#5c5c5c}
.em-link input{flex:1;font:13px system-ui,sans-serif;padding:6px 8px;border:1px solid #ccc;border-radius:6px}
.em-ctrls{display:flex;gap:6px;margin-top:10px}
.em-ctrls button,.em-bar button{font:600 13px system-ui,sans-serif;padding:6px 12px;border-radius:8px;border:1px solid #1c1c1c;background:#fff;cursor:pointer}
.em-ctrls .rm{color:#a00;border-color:#a00}
.em-bar{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid #d9d9d9;padding:12px 24px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap}
.em-bar .pub{background:#f9cd57;border-color:#f9cd57;font-size:15px;padding:9px 18px}
#em-msg{font:14px system-ui,sans-serif;white-space:pre-wrap;max-width:520px}
#em-msg.err{color:#a00}#em-msg.ok{color:#176b2c}
</style>
<script>
(function(){
  document.body.insertAdjacentHTML('afterbegin','<div class="em-note">EDIT MODE. Click your name or any reading to type. + Add a reading is at the bottom. Nothing goes live until you click Publish.</div>');
  document.body.insertAdjacentHTML('beforeend','<div class="em-bar"><button id="em-add">+ Add a reading</button><button class="pub" id="em-pub">Publish to octopro.pro</button><span id="em-msg"></span></div>');
  const col=document.querySelector('main .col');
  const ul=document.createElement('ul');ul.className='readings';col.appendChild(ul);
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  let items=[];const nameEl=document.querySelector('.owner-name');nameEl.setAttribute('contenteditable','plaintext-only');nameEl.dataset.ph='Your name';
  function grab(){items=[...ul.children].map(li=>({
    title:li.querySelector('h2').textContent.trim(),
    summary:li.querySelector('p').textContent.trim(),
    label:li.querySelector('.button').textContent.trim()||'Read',
    href:li.querySelector('.em-link input').value.trim()}));}
  function draw(){ul.innerHTML=items.map((it,i)=>'<li>'+
    '<h2 contenteditable="plaintext-only" data-ph="Title">'+esc(it.title)+'</h2>'+
    '<p contenteditable="plaintext-only" data-ph="Short explanation">'+esc(it.summary)+'</p>'+
    '<span class="button" contenteditable="plaintext-only" data-ph="Read">'+esc(it.label)+'</span>'+
    '<div class="em-link">Button opens: <input value="'+esc(it.href)+'" placeholder="https://... or /page/"></div>'+
    '<div class="em-ctrls"><button data-a="up" data-i="'+i+'">Up</button><button data-a="down" data-i="'+i+'">Down</button><button class="rm" data-a="rm" data-i="'+i+'">Remove</button></div>'+
    '</li>').join('');}
  ul.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;grab();const i=+b.dataset.i;
    if(b.dataset.a==='rm')items.splice(i,1);
    if(b.dataset.a==='up'&&i>0)[items[i-1],items[i]]=[items[i],items[i-1]];
    if(b.dataset.a==='down'&&i<items.length-1)[items[i+1],items[i]]=[items[i],items[i+1]];
    draw();});
  const say=(t,ok)=>{const m=document.getElementById('em-msg');m.textContent=t;m.className=ok?'ok':'err';};
  document.getElementById('em-add').onclick=()=>{grab();items.push({title:'',summary:'',label:'Read',href:'https://'});draw();ul.lastElementChild.querySelector('h2').focus();};
  document.getElementById('em-pub').onclick=async()=>{grab();if(!confirm('Publish '+items.length+' reading(s) to octopro.pro now?'))return;say('Publishing...',true);
    const r=await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nameEl.textContent.trim(),items})});say(await r.text(),r.ok);};
  fetch('/api/items').then(r=>r.json()).then(d=>{items=d.items;nameEl.textContent=d.name;draw();}).catch(e=>say('Could not load: '+e,false));
})();
</script>
"""


class Handler(BaseHTTPRequestHandler):
    draft = None

    def send(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def host_ok(self):
        # Refuse requests addressed to any other host name (blocks DNS-rebinding attacks).
        if self.headers.get("Host") in ALLOWED_HOSTS:
            return True
        self.send(403, "Forbidden")
        return False

    def do_GET(self):
        if not self.host_ok():
            return
        if self.path == "/":
            page = render_page([]).replace("</body>", EDIT_MODE + "</body>", 1)
            return self.send(200, page, "text/html; charset=utf-8")
        if self.path == "/api/items":
            try:
                return self.send(200, json.dumps(read_state()), "application/json")
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
        # Only this editor's own page may save or publish. A browser always sends
        # Origin on POST, so a request from any other website is refused here.
        if not self.host_ok():
            return
        if self.headers.get("Origin") not in ALLOWED_ORIGINS:
            return self.send(403, "Forbidden: request did not come from the editor page.")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.send(415, "Expected JSON.")
        try:
            state = validate(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))))
            if self.path == "/api/preview":
                Handler.draft = render_page(state["items"], state["name"])
                return self.send(200, "ok")
            if self.path == "/api/publish":
                return self.send(200, publish(state))
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
