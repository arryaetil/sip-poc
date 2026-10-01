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

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_PORT = Number(process.env.OD_INTERNAL_PORT || 7456);
const TOKEN = process.env.OD_API_TOKEN || '';
const SECRET = process.env.STUDIO_HANDOFF_SECRET || '';
const SIP_ORIGIN = (process.env.SIP_ORIGIN || '').replace(/\/$/, '');
const COOKIE = 'sip_studio';
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

function enter(req, res, url) {
  const claims = verify(url.searchParams.get('t'));
  if (!claims) return deny(res);
  if (claims.typ === 'session') return deny(res); // a session cookie is not an entry link
  const session = b64(JSON.stringify({ typ: 'session', sub: claims.sub, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS }));
  const next = typeof claims.next === 'string' && claims.next.startsWith('/') && !claims.next.startsWith('//') ? claims.next : '/';
  securityHeaders(res);
  res.writeHead(302, {
    Location: next,
    // Partitioned + SameSite=None lets the cookie work inside SIP's iframe.
    'Set-Cookie': `${COOKIE}=${session}.${sign(session)}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=None; Partitioned`,
    'Cache-Control': 'no-store',
  });
  res.end();
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
// A project started from the SIP chat gets its house style and brand files from
// SIP. A project created in the studio itself (Marketing studio -> new project)
// used to get nothing, so the model knew no brand and fetched stock photos. Now
// the gateway gives it the brand files under brand/<design system>/, and when no
// house style was chosen it gives both and the model asks which one first.

const BRANDS = ['etil', 'ibc-group'];
const ASSET_TYPES = /\.(png|jpe?g|svg|webp|ttf)$/i;
const NO_INVENTION = 'Never invent customers, figures, results or capabilities. Never download or hotlink photos from the internet: '
  + 'use the brand images, CSS in the brand colours, or a generated image labelled as AI-generated.';
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

async function copyBrand(projectId, brand, withNotes) {
  const listing = await upstream(`/api/design-systems/${brand}/files`);
  if (!listing.ok) throw new Error(`design system ${brand}: ${listing.status}`);
  for (const item of (await listing.json()).files || []) {
    const path = item.path || '';
    // The private source library stays in the design system: hundreds of originals per project would waste space and context.
    if (path.startsWith('assets/private-library/')) continue;
    const isAsset = /^(assets|fonts)\//.test(path) && ASSET_TYPES.test(path);
    const isNotes = withNotes && (path === 'DESIGN.md' || path === 'tokens.css');
    if (!isAsset && !isNotes) continue;
    const file = await upstream(`/api/design-systems/${brand}/static?path=${encodeURIComponent(path)}`);
    if (!file.ok) continue;
    const form = new FormData();
    form.append('name', `brand/${brand}/${path.replace(/^assets\//, '')}`);
    form.append('file', new Blob([await file.arrayBuffer()], { type: file.headers.get('content-type') || 'application/octet-stream' }), path.split('/').pop());
    const saved = await upstream(`/api/projects/${encodeURIComponent(projectId)}/files`, { method: 'POST', body: form });
    if (!saved.ok) throw new Error(`upload ${path}: ${saved.status}`);
  }
}

async function createProject(req, res, body) {
  let project;
  try { project = JSON.parse(body.toString('utf8') || '{}'); } catch { return forward(req, res, body); }
  const chosen = project.designSystemId || null;
  // SIP prepares its own projects; another of Open Design's styles was a deliberate choice.
  if (project.metadata?.source === 'sip' || (chosen && !BRANDS.includes(chosen))) return forward(req, res, body);
  project.customInstructions = [project.customInstructions, chosen ? FOLLOW_BRAND(chosen) : ASK_BRAND].filter(Boolean).join('\n\n');
  let status = 502;
  let text = '{"error":"Open Design is not reachable"}';
  let type = 'application/json';
  try {
    const created = await upstream('/api/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(project) });
    status = created.status;
    text = await created.text();
    type = created.headers.get('content-type') || type;
    if (created.ok) {
      let id = project.id;
      try { const parsed = JSON.parse(text); id = parsed.project?.id || parsed.id || id; } catch {}
      // Copied before answering, so the files are there when the first run starts.
      if (id) for (const brand of chosen ? [chosen] : BRANDS) await copyBrand(id, brand, !chosen);
    }
  } catch (error) {
    console.error('gateway: preparing the project failed', error.message);
  }
  securityHeaders(res);
  res.writeHead(status, { 'content-type': type, 'cache-control': 'no-store' });
  res.end(text);
}

function proxy(req, res) {
  const pathname = new URL(req.url || '/', 'http://gateway').pathname;
  if (req.method === 'POST' && pathname === '/api/projects') {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => createProject(req, res, Buffer.concat(chunks)));
    return;
  }
  if (req.method === 'POST' && ['/api/runs', '/api/chat'].includes(pathname)) {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => forward(req, res, withServerModel(Buffer.concat(chunks))));
    return;
  }
  forward(req, res, null);
}

function forward(req, res, body) {
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (!HOP_BY_HOP.has(key) && key !== 'cookie' && key !== 'authorization' && key !== 'host') headers[key] = value;
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
    return proxy(req, res);
  })
  .listen(PORT, '::', () => console.log(`gateway listening on ${PORT}, Open Design on 127.0.0.1:${UPSTREAM_PORT}`));
