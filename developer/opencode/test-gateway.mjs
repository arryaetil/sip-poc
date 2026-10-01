import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const secret = 'test-secret';
const origin = 'https://developer.example.test';
const upstream = http.createServer((req, res) => {
  if (req.headers.authorization !== `Basic ${Buffer.from('opencode:test-password').toString('base64')}`) { res.writeHead(401); return res.end(); }
  res.writeHead(200, { 'content-type': 'text/plain' }); res.end('upstream');
});
await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve));
const upstreamPort = upstream.address().port;
const free = http.createServer();
await new Promise(resolve => free.listen(0, '127.0.0.1', resolve));
const port = free.address().port;
await new Promise(resolve => free.close(resolve));
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sip-developer-test-'));
const child = spawn(process.execPath, [fileURLToPath(new URL('./gateway.mjs', import.meta.url))], {
  env: { ...process.env, PORT: String(port), OPENCODE_INTERNAL_PORT: String(upstreamPort), DEVELOPER_DATA_DIR: dataDir,
    DEVELOPER_HANDOFF_SECRET: secret, OPENCODE_SERVER_PASSWORD: 'test-password', DEVELOPER_PUBLIC_URL: origin },
  stdio: 'ignore',
});
const base = `http://127.0.0.1:${port}`;
let ready = false;
for (let i = 0; i < 100; i++) {
  try { const response = await fetch(`${base}/__sip/health`); ready = response.status === 200; if (ready) break; } catch {}
  await new Promise(resolve => setTimeout(resolve, 50));
}
assert.ok(ready, 'gateway started');
function link(exp, jti = crypto.randomBytes(16).toString('hex')) {
  const body = Buffer.from(JSON.stringify({ sub: 'account', exp, jti, next: '/' })).toString('base64url');
  const sig = crypto.createHmac('sha256', secret).update(body).digest('base64url');
  return `${base}/__sip/enter?t=${body}.${sig}`;
}
try {
  assert.equal((await fetch(base)).status, 401);
  assert.equal((await fetch(link(Math.floor(Date.now() / 1000) - 1))).status, 401);
  const valid = link(Math.floor(Date.now() / 1000) + 120);
  assert.equal((await fetch(`${valid}altered`)).status, 401);
  const admitted = await fetch(valid, { redirect: 'manual' });
  // A page that continues from the Developer site, not a redirect (SameSite=Strict, see gateway.mjs).
  assert.equal(admitted.status, 200);
  assert.match(await admitted.text(), /http-equiv="refresh" content="0;url=\/"/);
  assert.match(admitted.headers.get('set-cookie'), /HttpOnly; Secure; SameSite=Strict/);
  assert.equal((await fetch(valid, { redirect: 'manual' })).status, 401);
  const cookie = admitted.headers.get('set-cookie').split(';')[0];
  assert.equal((await fetch(base, { headers: { cookie } })).status, 200);
  assert.equal((await fetch(base, { method: 'POST', headers: { cookie, origin: 'https://evil.example' } })).status, 403);
  assert.equal((await fetch(base, { method: 'POST', headers: { cookie, origin } })).status, 200);
  // An entry link used as a cookie is refused, used or not; a cookie is refused as a link.
  const token = new URL(link(Math.floor(Date.now() / 1000) + 120)).searchParams.get('t');
  assert.equal((await fetch(base, { headers: { cookie: `__Host-sip_developer=${token}` } })).status, 401);
  assert.equal((await fetch(`${base}/__sip/enter?t=${cookie.split('=')[1]}`, { redirect: 'manual' })).status, 401);
  console.log('gateway: unauthorised, expired, tampered, replay, link-as-cookie, cookie and origin checks passed');
} finally {
  child.kill();
  upstream.close();
  fs.rmSync(dataDir, { recursive: true, force: true });
}
