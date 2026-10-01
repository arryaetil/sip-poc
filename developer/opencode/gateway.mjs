import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';

const port = Number(process.env.PORT || 8080);
const upstreamPort = Number(process.env.OPENCODE_INTERNAL_PORT || 4096);
const secret = process.env.DEVELOPER_HANDOFF_SECRET || '';
const password = process.env.OPENCODE_SERVER_PASSWORD || '';
const origin = (process.env.DEVELOPER_PUBLIC_URL || '').replace(/\/$/, '');
const nonceDir = `${process.env.DEVELOPER_DATA_DIR || '/data'}/used-links`;
const cookieName = '__Host-sip_developer';
const sessionSeconds = 12 * 60 * 60;
if (!secret || !password || !origin.startsWith('https://')) throw Error('Developer gateway settings are missing');
fs.mkdirSync(nonceDir, { recursive: true });

const b64 = value => Buffer.from(value).toString('base64url');
const sign = body => crypto.createHmac('sha256', secret).update(body).digest('base64url');
function verify(token) {
  const [body, signature, extra] = String(token || '').split('.');
  if (!body || !signature || extra) return null;
  const expected = sign(body);
  if (signature.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) return null;
  try {
    const claims = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'));
    return Number.isSafeInteger(claims.exp) && claims.exp > Math.floor(Date.now() / 1000) ? claims : null;
  } catch { return null; }
}
function cookie(req) {
  const item = String(req.headers.cookie || '').split(';').map(x => x.trim()).find(x => x.startsWith(`${cookieName}=`));
  return item ? item.slice(cookieName.length + 1) : '';
}
function deny(res, code = 401) {
  res.writeHead(code, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store', 'content-security-policy': "frame-ancestors 'none'" });
  res.end(code === 401 ? 'Open Developer vanuit SIP.' : 'Verzoek geweigerd.');
}
function safeNext(path) {
  return typeof path === 'string' && /^\/(?!\/)[^\\\r\n]*$/.test(path) && !path.startsWith('/__sip/') ? path : '/';
}
function enter(req, res, url) {
  const claims = verify(url.searchParams.get('t'));
  if (!claims || typeof claims.sub !== 'string' || !/^[a-f0-9]{32}$/.test(claims.jti || '')) return deny(res);
  try { fs.writeFileSync(`${nonceDir}/${claims.jti}`, String(claims.exp), { flag: 'wx', mode: 0o600 }); }
  catch { return deny(res); }
  const body = b64(JSON.stringify({ sub: claims.sub, exp: Math.floor(Date.now() / 1000) + sessionSeconds }));
  res.writeHead(303, {
    location: safeNext(claims.next),
    'set-cookie': `${cookieName}=${body}.${sign(body)}; Path=/; Max-Age=${sessionSeconds}; HttpOnly; Secure; SameSite=Strict`,
    'cache-control': 'no-store', 'referrer-policy': 'no-referrer',
  });
  res.end();
}
function authorised(req) { return verify(cookie(req)) !== null; }
function safeRequest(req) {
  if (req.headers.origin && req.headers.origin !== origin) return false;
  if (req.headers['sec-fetch-site'] === 'cross-site') return false;
  if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method) && req.headers.origin !== origin) return false;
  return true;
}
const hop = new Set(['host', 'cookie', 'authorization', 'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade']);
function headers(req) {
  const out = {};
  for (const [key, value] of Object.entries(req.headers)) if (!hop.has(key)) out[key] = value;
  out.authorization = `Basic ${Buffer.from(`opencode:${password}`).toString('base64')}`;
  out.host = `127.0.0.1:${upstreamPort}`;
  return out;
}
function proxy(req, res) {
  const upstream = http.request({ host: '127.0.0.1', port: upstreamPort, path: req.url, method: req.method, headers: headers(req) }, response => {
    const out = {};
    for (const [key, value] of Object.entries(response.headers)) if (!hop.has(key) && key !== 'set-cookie' && key !== 'content-security-policy' && key !== 'x-frame-options') out[key] = value;
    out['content-security-policy'] = "frame-ancestors 'none'";
    out['cache-control'] = out['cache-control'] || 'no-store';
    res.writeHead(response.statusCode || 502, out);
    response.pipe(res); // Streaming responses, including SSE, stay live.
  });
  upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
  req.pipe(upstream);
}
const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://localhost');
  if (url.pathname === '/__sip/enter') return enter(req, res, url);
  if (url.pathname === '/__sip/health') { res.writeHead(200); return res.end('ok'); }
  if (!authorised(req)) return deny(res);
  if (!safeRequest(req)) return deny(res, 403);
  proxy(req, res);
});
server.on('upgrade', (req, socket, head) => {
  if (!authorised(req) || !safeRequest(req)) { socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return; }
  const upstream = http.request({ host: '127.0.0.1', port: upstreamPort, path: req.url, headers: { ...headers(req), connection: 'Upgrade', upgrade: req.headers.upgrade }, method: req.method });
  upstream.on('upgrade', (response, upstreamSocket, upstreamHead) => {
    socket.write(`HTTP/1.1 101 Switching Protocols\r\n${Object.entries(response.headers).map(([k, v]) => `${k}: ${v}\r\n`).join('')}\r\n`);
    if (head.length) upstreamSocket.write(head);
    if (upstreamHead.length) socket.write(upstreamHead);
    socket.pipe(upstreamSocket).pipe(socket);
  });
  upstream.on('error', () => socket.destroy());
  upstream.end();
});
server.listen(port, '0.0.0.0', () => console.log('Developer gateway ready'));
