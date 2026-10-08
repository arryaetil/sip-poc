// Gateway in front of Open Design: only SIP decides who gets in.
//
// Open Design's own auth is one shared token ("single-tenant, not user-level").
// This gateway keeps the daemon on localhost and admits a request only when
//   - it carries the daemon token itself (SIP's backend, over the private
//     network), or
//   - the browser holds a studio cookie, obtained through a short-lived link
//     that SIP signs for a signed-in user (/__sip/enter?t=...).
// It adds the daemon token upstream, so users never see it, and only lets
// SIP frame the studio.
//
// No dependencies: Node's http module and crypto only.

import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import nodePath from 'node:path';
import { currentLibrary, syncLibrary, LIBRARY_NOTE } from './sip-library.mjs';
import { exportRoute, handleExport } from './export-renderer.mjs';
import { STUDIO_EXPORT_SCRIPT } from './studio-export-script.mjs';
import { STUDIO_PREVIEW_SCRIPT } from './studio-preview-script.mjs';

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_PORT = Number(process.env.OD_INTERNAL_PORT || 7456);
const TOKEN = process.env.OD_API_TOKEN || '';
const SECRET = process.env.STUDIO_HANDOFF_SECRET || '';
const SIP_ORIGIN = (process.env.SIP_ORIGIN || '').replace(/\/$/, '');
const SIP_LIBRARY_ORIGIN = (process.env.SIP_INTERNAL_URL || SIP_ORIGIN).replace(/\/$/, '');
const COOKIE = 'sip_studio';
// Entry links are accepted once: their one-time id (jti) is recorded here, on the
// data volume, so a restart does not make an old link valid again.
const USED_LINKS = nodePath.join(process.env.OD_DATA_DIR || '/app/.od', 'sip-entry-links');
const SESSION_SECONDS = 12 * 60 * 60;

if (!TOKEN || !SECRET || !SIP_ORIGIN) {
  console.error('gateway: OD_API_TOKEN, STUDIO_HANDOFF_SECRET and SIP_ORIGIN are required');
  process.exit(1);
}

const b64 = (value) => Buffer.from(value).toString('base64url');
const sign = (payload) => crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');

function verify(token) {
  // token = base64url(json).signature
  const [body, signature] = String(token || '').split('.');
  if (!body || !signature) return null;
  const expected = sign(body);
  if (signature.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) return null;
  try {
    const claims = JSON.parse(Buffer.from(body, 'base64url').toString());
    return claims.exp > Date.now() / 1000 ? claims : null;
  } catch {
    return null;
  }
}

function cookieValue(header, name) {
  for (const part of String(header || '').split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) return rest.join('=');
  }
  return '';
}

function securityHeaders(res) {
  // SIP embeds the studio, and the studio embeds its own HTML preview.
  res.setHeader('Content-Security-Policy', `frame-ancestors 'self' ${SIP_ORIGIN}`);
}

function deny(res) {
  securityHeaders(res);
  res.writeHead(401, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`<!doctype html><meta charset="utf-8"><title>Marketing studio</title>
<body style="font-family:Ubuntu,Arial,sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#F8F9FA;color:#121212">
<div style="text-align:center"><h1 style="font-size:22px">Open the Marketing studio from SIP</h1>
<p><a href="${SIP_ORIGIN}" style="color:#0066cc">Go to SIP</a></p></div></body>`);
}

async function claimOnce(jti, exp) {
  if (!/^[a-f0-9]{32}$/.test(String(jti || ''))) return false;
  await fs.mkdir(USED_LINKS, { recursive: true });
  try {
    await fs.writeFile(nodePath.join(USED_LINKS, jti), String(exp), { flag: 'wx', mode: 0o600 });
    return true;
  } catch {
    return false; // already used
  }
}

async function forgetExpiredLinks() {
  const now = Math.floor(Date.now() / 1000);
  for (const name of await fs.readdir(USED_LINKS).catch(() => [])) {
    const exp = Number(await fs.readFile(nodePath.join(USED_LINKS, name), 'utf8').catch(() => '0'));
    if (exp < now) await fs.rm(nodePath.join(USED_LINKS, name), { force: true });
  }
}

async function enter(req, res, url) {
  const claims = verify(url.searchParams.get('t'));
  if (!claims) return deny(res);
  if (claims.typ === 'session') return deny(res); // a session cookie is not an entry link
  if (!(await claimOnce(claims.jti, claims.exp))) return deny(res);
  const session = b64(JSON.stringify({ typ: 'session', sub: claims.sub, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS }));
  const next = typeof claims.next === 'string' && /^\/(?!\/)[^\\\r\n]*$/.test(claims.next) && !claims.next.startsWith('/__sip/') ? claims.next : '/';
  securityHeaders(res);
  res.writeHead(302, {
    Location: next,
    // Partitioned + SameSite=None lets the cookie work inside SIP's iframe.
    'Set-Cookie': `${COOKIE}=${session}.${sign(session)}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=None; Partitioned`,
    'Cache-Control': 'no-store',
  });
  res.end();
}

// Requests that change something must come from the studio page itself (or from SIP's
// backend with the daemon token): a cookie alone could be sent by another site.
function sameOriginWrite(req) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return true;
  if (req.headers.authorization === `Bearer ${TOKEN}`) return true;
  const own = `https://${req.headers['x-forwarded-host'] || req.headers.host}`;
  return req.headers.origin === own;
}

function authorised(req) {
  if (req.headers.authorization === `Bearer ${TOKEN}`) return true;
  // Only a session cookie counts; an entry link set as a cookie would skip the link's purpose.
  return verify(cookieValue(req.headers.cookie, COOKIE))?.typ === 'session';
}

const HOP_BY_HOP = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade']);

// The model key lives here, not in each marketer's browser: every run is sent
// to the BYOK OpenCode runtime with the server's OpenAI key and model.
const MODEL_KEY = process.env.STUDIO_OPENAI_API_KEY || '';
const MODEL = process.env.STUDIO_MODEL || 'gpt-5.6-terra';

function withServerModel(body) {
  if (!MODEL_KEY) return body;
  try {
    const run = JSON.parse(body.toString('utf8') || '{}');
    run.agentId = 'byok-opencode';
    run.model = MODEL;
    run.byokProvider = { protocol: 'openai', apiKey: MODEL_KEY, baseUrl: 'https://api.openai.com/v1', model: MODEL };
    return Buffer.from(JSON.stringify(run));
  } catch {
    return body;
  }
}

// --- House style for projects created in the studio ----------------------------
//
// A project started from the SIP chat gets its instructions from SIP. A project
// created in the studio itself (Marketing studio -> new project) used to get
// nothing, so the model knew no brand and fetched stock photos. Now the gateway
// gives every new project the brand files under brand/<brand>/, and when no
// house style was chosen it gives both and the model asks which one first.

const BRANDS = ['etil', 'ibc-group'];
const ASSET_TYPES = /\.(png|jpe?g|svg|webp|ttf)$/i;
const NO_INVENTION = 'Never invent customers, figures, results or capabilities. Never download or hotlink photos from the internet: '
  + 'use the brand images, CSS in the brand colours, or a generated image labelled as AI-generated. '
  + 'Before you design, open the matching finished example in brand/<brand>/examples/ and look at it; before you finish, compare '
  + 'your design with it and fix every difference. In particular: place the official logo PNG for the background (the white one on dark) whole, with its colour spectrum '
  + 'bar (never a white bar, never a logo drawn in HTML), and use the AI label HTML and CSS from the design system (an outlined '
  + 'pill "AI-GENERATED VISUAL" with "provided by ibc group marketing" under it), never a plain line of text.';
const ASK_BRAND = 'This project was started in the studio without a house style. Before you design anything, ask the user one short '
  + 'question in their language: should this use the Etil or the ibc group house style? Then follow brand/etil/DESIGN.md or '
  + 'brand/ibc-group/DESIGN.md strictly (colours, Ubuntu, logo rules, tone of voice and the image catalogue) and use only the files '
  + 'in that brand folder: images, examples, logos and fonts (load Ubuntu with @font-face from brand/<brand>/fonts/). ' + NO_INVENTION;
const FOLLOW_BRAND = (brand) => `Follow the selected ${brand} design system strictly. Its images, examples, logos and fonts are in `
  + `brand/${brand}/ in this project; when the user refers to a service, topic or image motif, use the matching image from the `
  + `image catalogue of the design system. ` + NO_INVENTION;

function upstream(path, init = {}) {
  return fetch(`http://127.0.0.1:${UPSTREAM_PORT}${path}`, { ...init, headers: { ...(init.headers || {}), authorization: `Bearer ${TOKEN}` } });
}

// Read from disk, not through Open Design's API: its design-system file listing
// answers 404 for these packages, while the files are right here on the volume
// (entrypoint.sh installs them in OD_DATA_DIR/design-systems).
const DESIGN_SYSTEMS = nodePath.join(process.env.OD_DATA_DIR || '/app/.od', 'design-systems');
const MEDIA_TYPES = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp',
  '.ttf': 'font/ttf', '.md': 'text/markdown', '.css': 'text/css' };

// Open Design names the packages user:etil and user:ibc-group; the folders are etil and ibc-group.
const brandOf = (designSystemId) => String(designSystemId || '').replace(/^user:/, '');

async function brandFiles(root) {
  const found = [];
  async function walk(relative) {
    for (const entry of await fs.readdir(nodePath.join(root, relative), { withFileTypes: true })) {
      const path = `${relative}/${entry.name}`;
      // The private source library stays in the design system: hundreds of originals per project would waste space and context.
      if (path === 'assets/private-library') continue;
      if (entry.isDirectory()) await walk(path);
      else if (ASSET_TYPES.test(path)) found.push(path);
    }
  }
  for (const folder of ['assets', 'fonts']) {
    try { await walk(folder); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return found.sort();
}

async function copyBrand(projectId, brand, withNotes) {
  const root = nodePath.join(DESIGN_SYSTEMS, brand);
  const files = await brandFiles(root);
  if (!files.length) throw new Error(`design system ${brand} has no brand files in ${root}`);
  if (withNotes) files.push('DESIGN.md', 'tokens.css');
  for (const path of files) {
    let content;
    try { content = await fs.readFile(nodePath.join(root, path)); } catch { continue; }
    const form = new FormData();
    form.append('name', `brand/${brand}/${path.replace(/^assets\//, '')}`);
    form.append('file', new Blob([content], { type: MEDIA_TYPES[nodePath.extname(path).toLowerCase()] || 'application/octet-stream' }), nodePath.basename(path));
    const saved = await upstream(`/api/projects/${encodeURIComponent(projectId)}/files`, { method: 'POST', body: form });
    if (!saved.ok) throw new Error(`upload ${path}: ${saved.status}`);
  }
}

async function createProject(req, res, body) {
  let project;
  try { project = JSON.parse(body.toString('utf8') || '{}'); } catch { return forward(req, res, body); }
  const chosen = project.designSystemId ? brandOf(project.designSystemId) : null;
  // Another of Open Design's styles was a deliberate choice: leave that project alone.
  if (chosen && !BRANDS.includes(chosen)) return forward(req, res, body);
  // SIP writes its own instructions; it only needs the brand files.
  if (project.metadata?.source !== 'sip') {
    project.customInstructions = [project.customInstructions, chosen ? FOLLOW_BRAND(chosen) : ASK_BRAND].filter(Boolean).join('\n\n');
  }
  let status = 502;
  let text = '{"error":"Open Design is not reachable"}';
  let type = 'application/json';
  try {
    const library = await currentLibrary(SIP_LIBRARY_ORIGIN, SECRET);
    const created = await upstream('/api/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(project) });
    status = created.status;
    text = await created.text();
    type = created.headers.get('content-type') || type;
    if (created.ok) {
      let id = project.id;
      try { const parsed = JSON.parse(text); id = parsed.project?.id || parsed.id || id; } catch {}
      // Copied before answering, so the files are there when the first run starts.
      if (id) {
        for (const brand of chosen ? [chosen] : BRANDS) await copyBrand(id, brand, !chosen);
        await syncLibrary(id, SIP_LIBRARY_ORIGIN, SECRET, upstream, library);
      }
    }
  } catch (error) {
    console.error('gateway: preparing the project failed', error.message);
    status = 502;
    text = JSON.stringify({ error: 'De actuele SIP-kennis kon niet worden geladen. Probeer opnieuw.' });
  }
  securityHeaders(res);
  res.writeHead(status, { 'content-type': type, 'cache-control': 'no-store' });
  res.end(text);
}

function proxy(req, res) {
  const pathname = new URL(req.url || '/', 'http://gateway').pathname;
  const exportMatch = req.method === 'POST' && exportRoute(pathname);
  if (exportMatch) return handleExport(req, res, exportMatch, upstream);
  if (req.method === 'POST' && pathname === '/api/projects') {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => createProject(req, res, Buffer.concat(chunks)));
    return;
  }
  if (req.method === 'POST' && ['/api/runs', '/api/chat'].includes(pathname)) {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', async () => {
      try {
        const run = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        await syncLibrary(run.projectId, SIP_LIBRARY_ORIGIN, SECRET, upstream);
        run.message = `${LIBRARY_NOTE}\n\n${run.message || ''}`;
        forward(req, res, withServerModel(Buffer.from(JSON.stringify(run))));
      } catch (error) {
        console.error('gateway: SIP library sync failed', error.message);
        securityHeaders(res);
        res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ error: 'De actuele SIP-kennis kon niet worden geladen. Probeer opnieuw; deze opdracht is nog niet gestart.' }));
      }
    });
    return;
  }
  forward(req, res, null);
}

// The studio is for marketing colleagues making posts, one-pagers and presentations.
// Parts of Open Design they do not need (Cloud sign-in, community, plugins, design
// system editing, settings, model and working-directory pickers, example prompts)
// are hidden with one style block added to every page. Open Design itself is not
// changed, so an image update cannot break it; at worst a part shows again.
// Selectors are Open Design v0.24.0's own test ids and class names.
const STUDIO_CSS = '[data-testid="entry-nav-community"], [data-testid="entry-nav-design-systems"],'
  + ' [data-testid="entry-nav-plugins"], [data-testid="entry-settings-button"],'
  + ' .entry-nav-rail__footer, .home-hero__workdir-row, .home-hero__execution-switcher,'
  + ' [data-testid="home-hero-plugin-presets"], [data-testid="home-hero-prompt-examples"],'
  + ' [data-testid="plugins-home-section"], .home-hero [aria-label="Creation type"] { display: none !important; }'
  + ' .home-hero__title { font-size:0!important; } .home-hero__title>* { display:none!important; }'
  + ' .home-hero__title::after { content:"Wat wil je maken?";font:600 36px Ubuntu,sans-serif; }'
  + ' .home-hero__subtitle { font-size:0!important; } .home-hero__subtitle::after { content:"Beschrijf je post, carousel of presentatie. Kies de huisstijl; SIP-kennis wordt automatisch meegenomen.";font:14px Ubuntu,sans-serif; }';
// The style block, plus a few lines that put it back should the app rebuild <head>
// while it starts (React owns the whole document).
export const STUDIO_STYLE = `<style id="sip-studio-simplify">${STUDIO_CSS}</style>`
  + `<script id="sip-studio-keep">(function(){var css=${JSON.stringify(STUDIO_CSS)};`
  + `function ensure(){if(document.head&&!document.getElementById('sip-studio-simplify')){`
  + `var s=document.createElement('style');s.id='sip-studio-simplify';s.textContent=css;document.head.appendChild(s);}}`
  + `new MutationObserver(ensure).observe(document.documentElement,{childList:true,subtree:false});`
  + `document.addEventListener('DOMContentLoaded',function(){ensure();if(document.head)new MutationObserver(ensure).observe(document.head,{childList:true});});})();</script>`;

function wantsPage(req) {
  return req.method === 'GET' && String(req.headers.accept || '').includes('text/html');
}

function forward(req, res, body) {
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (!HOP_BY_HOP.has(key) && key !== 'cookie' && key !== 'authorization' && key !== 'host') headers[key] = value;
  }
  // A page is changed before it is sent on, so ask for it uncompressed.
  const page = wantsPage(req) && !new URL(req.url, 'http://gateway').pathname.startsWith('/api/');
  if (page) {
    delete headers['accept-encoding'];
    // Without these the daemon answers 304 and the browser shows its stored copy,
    // which has no style block.
    delete headers['if-none-match'];
    delete headers['if-modified-since'];
  }
  headers.authorization = `Bearer ${TOKEN}`;
  headers.host = `127.0.0.1:${UPSTREAM_PORT}`;
  if (body) headers['content-length'] = String(body.length);
  const upstream = http.request(
    { host: '127.0.0.1', port: UPSTREAM_PORT, method: req.method, path: req.url, headers },
    (response) => {
      const out = {};
      for (const [key, value] of Object.entries(response.headers)) {
        if (!HOP_BY_HOP.has(key) && key !== 'content-security-policy' && key !== 'x-frame-options') out[key] = value;
      }
      out['content-security-policy'] = `frame-ancestors 'self' ${SIP_ORIGIN}`;
      const html = String(response.headers['content-type'] || '').includes('text/html');
      if (page && html && !response.headers['content-encoding']) {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () => {
          const text = Buffer.concat(chunks).toString('utf8');
          const previewScript = STUDIO_PREVIEW_SCRIPT.replace('SIP_PARENT_ORIGIN', JSON.stringify(SIP_ORIGIN));
          const changed = Buffer.from(text.includes('</head>') ? text.replace('</head>', `${STUDIO_STYLE}${STUDIO_EXPORT_SCRIPT}${previewScript}</head>`) : text);
          delete out['etag'];
          delete out['last-modified'];
          out['cache-control'] = 'no-store';
          out['content-length'] = String(changed.length);
          res.writeHead(response.statusCode || 502, out);
          res.end(changed);
        });
        return;
      }
      res.writeHead(response.statusCode || 502, out);
      // Piping keeps Server-Sent Events streaming instead of buffering them.
      response.pipe(res);
    },
  );
  upstream.on('error', (error) => {
    console.error('gateway upstream error', error.message);
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end('Open Design is not reachable');
  });
  if (body) upstream.end(body);
  else req.pipe(upstream);
}

http
  .createServer((req, res) => {
    const url = new URL(req.url || '/', 'http://gateway');
    if (url.pathname === '/__sip/enter') return enter(req, res, url);
    if (url.pathname === '/api/health') return proxy(req, res); // Railway health check
    if (!authorised(req)) return deny(res);
    if (!sameOriginWrite(req)) {
      securityHeaders(res);
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Request refused.');
    }
    return proxy(req, res);
  })
  .listen(PORT, '::', () => console.log(`gateway listening on ${PORT}, Open Design on 127.0.0.1:${UPSTREAM_PORT}`));
forgetExpiredLinks();
setInterval(forgetExpiredLinks, 60 * 60 * 1000).unref();
