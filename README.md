# octopro.pro

Plain static files. No framework, no build step, no packages, no server code.

- `site/` is everything that gets published. One folder per page; the folder name is the address (`site/falsify-no-validate/` is `octopro.pro/falsify-no-validate/`).
- `package.json` has no dependencies. It holds two shortcuts (`build`, `deploy`) only because Cloudflare's build settings call them by name.
- `wrangler.json` tells Cloudflare to serve `site/` as files and run nothing else. It is the only host-specific file.
- Fonts used by a page sit next to that page. Pages fetch nothing from other sites.
- Preview locally: `python3 -m http.server 8765 --directory site`, then open http://localhost:8765/
