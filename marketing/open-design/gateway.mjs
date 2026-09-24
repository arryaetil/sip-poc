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
  // Only SIP may frame the studio.
  res.setHeader('Content-Security-Policy', `frame-ancestors ${SIP_ORIGIN}`);
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
  const session = b64(JSON.stringify({ sub: claims.sub, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS }));
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
  return verify(cookieValue(req.headers.cookie, COOKIE)) !== null;
}

const HOP_BY_HOP = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade']);

function proxy(req, res) {
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (!HOP_BY_HOP.has(key) && key !== 'cookie' && key !== 'authorization' && key !== 'host') headers[key] = value;
  }
  headers.authorization = `Bearer ${TOKEN}`;
  headers.host = `127.0.0.1:${UPSTREAM_PORT}`;
  const upstream = http.request(
    { host: '127.0.0.1', port: UPSTREAM_PORT, method: req.method, path: req.url, headers },
    (response) => {
      const out = {};
      for (const [key, value] of Object.entries(response.headers)) {
        if (!HOP_BY_HOP.has(key) && key !== 'content-security-policy' && key !== 'x-frame-options') out[key] = value;
      }
      out['content-security-policy'] = `frame-ancestors ${SIP_ORIGIN}`;
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
  req.pipe(upstream);
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
