# octopro.pro

Plain static files. No framework, no build step, no packages, no server code.

- `site/` is everything that gets published. One folder per page; the folder name is the address (`site/falsify-no-validate/` is `octopro.pro/falsify-no-validate/`).
- `package.json` has no dependencies. It holds two shortcuts (`build`, `deploy`) only because Cloudflare's build settings call them by name.
- `wrangler.json` tells Cloudflare to serve `site/` as files and run nothing else. It is the only host-specific file.
- Fonts used by a page sit next to that page. Pages fetch nothing from other sites.
- The homepage (your name in the top bar and the reading list) is edited in a local editor, `tools/edit-homepage.py`. It runs in the background from the macOS LaunchAgent `~/Library/LaunchAgents/com.donato.octopro-editor.plist` at http://127.0.0.1:8790/ (log: `~/Library/Logs/octopro-editor.log`). Publish writes `site/index.html`, commits and pushes `main`. The repo must be on `main`. To stop auto-start: `launchctl bootout gui/$(id -u)/com.donato.octopro-editor` and delete the plist.
- Preview locally: `python3 -m http.server 8765 --directory site`, then open http://localhost:8765/
