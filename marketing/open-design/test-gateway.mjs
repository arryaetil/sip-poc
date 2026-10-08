// Tests the studio gateway against a fake Open Design: house style for projects
// created in the studio, and entry links versus session cookies.
// Run: node marketing/open-design/test-gateway.mjs
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import os from 'node:os';
import nodePath from 'node:path';

const token = 'daemon-token';
const secret = 'handoff-secret';
const projects = [];
const uploads = [];
// The brand packages on disk, as entrypoint.sh installs them on the volume.
const dataDir = fs.mkdtempSync(nodePath.join(os.tmpdir(), 'od-'));
for (const brand of ['etil', 'ibc-group']) {
  for (const path of ['assets/images/people.jpg', 'assets/private-library/original.jpg', 'fonts/Ubuntu-Regular.ttf', 'fonts/UFL.txt', 'DESIGN.md', 'tokens.css', 'manifest.json']) {
    fs.mkdirSync(nodePath.join(dataDir, 'design-systems', brand, nodePath.dirname(path)), { recursive: true });
    fs.writeFileSync(nodePath.join(dataDir, 'design-systems', brand, path), `content of ${path}`);
  }
}

const upstream = http.createServer((req, res) => {
  if (req.headers.authorization !== `Bearer ${token}`) { res.writeHead(401); return res.end(); }
  const url = new URL(req.url, 'http://upstream');
  const chunks = [];
  req.on('data', (chunk) => chunks.push(chunk));
  req.on('end', () => {
    const body = Buffer.concat(chunks);
    // Like live Open Design: the design-system file listing is not available.
    if (url.pathname.startsWith('/api/design-systems/')) {
      res.writeHead(404, { 'content-type': 'application/json' });
      return res.end('{"error":"editable design system not found"}');
    }
    if (req.method === 'POST' && url.pathname === '/api/projects') {
      const project = JSON.parse(body.toString());
      projects.push(project);
      res.writeHead(201, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({ project: { id: project.id || `p${projects.length}` } }));
    }
    const upload = url.pathname.match(/^\/api\/projects\/([^/]+)\/files$/);
    if (req.method === 'POST' && upload) {
      const name = body.toString().match(/name="name"\r\n\r\n([^\r]+)/)?.[1];
      uploads.push(`${upload[1]}:${name}`);
      res.writeHead(200, { 'content-type': 'application/json' });
      return res.end('{}');
    }
    if (url.pathname === '/page') {
      // Like Open Design: pages are compressed when the browser allows it.
      if (String(req.headers['accept-encoding'] || '').includes('gzip')) { res.writeHead(500); return res.end('compressed'); }
      // Like Open Design: a page the browser already has is answered with 304.
      if (req.headers['if-none-match']) { res.writeHead(304, { etag: '"v1"' }); return res.end(); }
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', etag: '"v1"', 'cache-control': 'public, max-age=0' });
      return res.end('<html><head><title>OD</title></head><body>studio</body></html>');
    }
    res.writeHead(200, { 'content-type': 'text/plain' });
    res.end('upstream');
  });
});
await new Promise((resolve) => upstream.listen(0, '127.0.0.1', resolve));

const free = http.createServer();
await new Promise((resolve) => free.listen(0, '127.0.0.1', resolve));
const port = free.address().port;
await new Promise((resolve) => free.close(resolve));
const child = spawn(process.execPath, [fileURLToPath(new URL('./gateway.mjs', import.meta.url))], {
  env: { ...process.env, PORT: String(port), OD_INTERNAL_PORT: String(upstream.address().port), OD_API_TOKEN: token,
    STUDIO_HANDOFF_SECRET: secret, SIP_ORIGIN: 'https://sip.example.test', OD_DATA_DIR: dataDir },
  stdio: 'ignore',
});
const base = `http://localhost:${port}`;
for (let i = 0; i < 100; i++) {
  try { if ((await fetch(`${base}/api/health`)).status) break; } catch {}
  await new Promise((resolve) => setTimeout(resolve, 50));
}

const create = (project) => fetch(`${base}/api/projects`, {
  method: 'POST', headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: JSON.stringify(project),
});
const uploadsOf = (id) => uploads.filter((entry) => entry.startsWith(`${id}:`)).map((entry) => entry.slice(id.length + 1)).sort();

try {
  // No house style chosen: both brands with their notes, and the model asks first.
  assert.equal((await create({ id: 'free', name: 'Post' })).status, 201);
  assert.match(projects.at(-1).customInstructions, /ask the user one short question.*Etil or the ibc group house style/);
  assert.deepEqual(uploadsOf('free'), [
    'brand/etil/DESIGN.md', 'brand/etil/fonts/Ubuntu-Regular.ttf', 'brand/etil/images/people.jpg', 'brand/etil/tokens.css',
    'brand/ibc-group/DESIGN.md', 'brand/ibc-group/fonts/Ubuntu-Regular.ttf', 'brand/ibc-group/images/people.jpg', 'brand/ibc-group/tokens.css',
  ]);

  // ibc group chosen in the studio: only its files, pointing at its image catalogue.
  await create({ id: 'ibc', designSystemId: 'ibc-group', customInstructions: 'Own note.' });
  assert.match(projects.at(-1).customInstructions, /^Own note\.\n\nFollow the selected ibc-group design system/);
  assert.deepEqual(uploadsOf('ibc'), ['brand/ibc-group/fonts/Ubuntu-Regular.ttf', 'brand/ibc-group/images/people.jpg']);

  // Open Design's own name for the package, user:etil, is the same brand.
  await create({ id: 'etil', designSystemId: 'user:etil' });
  assert.match(projects.at(-1).customInstructions, /^Follow the selected etil design system/);
  assert.deepEqual(uploadsOf('etil'), ['brand/etil/fonts/Ubuntu-Regular.ttf', 'brand/etil/images/people.jpg']);

  // SIP's projects get the brand files but keep SIP's own instructions.
  await create({ id: 'sip-1', designSystemId: 'user:ibc-group', customInstructions: 'From SIP.', metadata: { source: 'sip' } });
  assert.equal(projects.at(-1).customInstructions, 'From SIP.');
  assert.deepEqual(uploadsOf('sip-1'), ['brand/ibc-group/fonts/Ubuntu-Regular.ttf', 'brand/ibc-group/images/people.jpg']);

  // Another Open Design style passes through untouched.
  await create({ id: 'other', designSystemId: 'apple' });
  assert.equal(projects.at(-1).customInstructions, undefined);
  assert.deepEqual(uploadsOf('other'), []);

  // An entry link is not a session cookie; the session cookie from the link is.
  const body = Buffer.from(JSON.stringify({ sub: 'user', exp: Math.floor(Date.now() / 1000) + 120, next: '/' })).toString('base64url');
  const link = `${body}.${crypto.createHmac('sha256', secret).update(body).digest('base64url')}`;
  assert.equal((await fetch(`${base}/`, { headers: { cookie: `sip_studio=${link}` } })).status, 401);
  const entered = await fetch(`${base}/__sip/enter?t=${link}`, { redirect: 'manual' });
  const cookie = entered.headers.get('set-cookie').split(';')[0];
  assert.equal((await fetch(`${base}/`, { headers: { cookie } })).status, 200);
  assert.equal((await fetch(`${base}/__sip/enter?t=${cookie.split('=')[1]}`, { redirect: 'manual' })).status, 401);

  // Pages get the style that hides what marketing does not need; other responses do not.
  const page = await fetch(`${base}/page`, { headers: { cookie, accept: 'text/html', 'accept-encoding': 'gzip, br', 'if-none-match': '"v1"' } });
  const pageText = await page.text();
  assert.equal(page.status, 200);
  assert.match(pageText, /<style id="sip-studio-simplify">[\s\S]*entry-nav-community[\s\S]*home-hero-prompt-examples[\s\S]*<\/script><\/head>/);
  assert.equal(Number(page.headers.get('content-length')), Buffer.byteLength(pageText));
  assert.equal(page.headers.get('cache-control'), 'no-store');
  assert.equal(page.headers.get('etag'), null);
  assert.match(pageText, /<script id="sip-studio-keep">/);
  assert.doesNotMatch(await (await fetch(`${base}/other`, { headers: { cookie } })).text(), /sip-studio-simplify/);
  console.log('studio gateway: brand files from disk, house style for studio projects, pass-through, session cookie and simplified page checks passed');
} finally {
  child.kill();
  upstream.close();
  fs.rmSync(dataDir, { recursive: true, force: true });
}
