// A release change must be explicit in the reviewed baseline and Dockerfile.
// This catches accidental floating versions; it does not prove upstream compatibility.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const read=name=>fs.readFile(new URL(name,import.meta.url),'utf8');
const baseline=JSON.parse(await read('release-lock.json'));
const pkg=JSON.parse(await read('package.json'));
const lock=JSON.parse(await read('package-lock.json'));
assert.deepEqual(pkg.dependencies,baseline.dependencies,'Dependency changes require a reviewed release baseline');
assert.deepEqual(lock.packages[''].dependencies,pkg.dependencies,'package-lock must match package.json');
for(const [name,version] of Object.entries(pkg.dependencies)){
  assert.match(version,/^\d+\.\d+\.\d+$/,'Use exact versions');
  const installed=lock.packages['node_modules/'+name];
  assert.equal(installed?.version,version,name+' lock version');
  assert.ok(installed?.integrity,name+' must have an integrity hash');
}
if(!process.argv.includes('--dependencies-only')){
  const docker=await read('Dockerfile');
  assert.match(baseline.upstreamImage,/^ghcr\.io\/nexu-io\/od@sha256:[a-f0-9]{64}$/);
  assert.equal(docker.match(/^FROM\s+(\S+)/m)?.[1],baseline.upstreamImage,'Upstream image differs from the reviewed baseline');
  assert.equal(docker.match(/npm install -g opencode-ai@([\d.]+)/)?.[1],baseline.openCodeVersion,'OpenCode differs from the reviewed baseline');
  assert.match(docker,/node check-release\.mjs &&/,'Build must check release baseline');
}
console.log('Pinned release baseline and dependency integrity verified. Upstream API/UI checks remain required.');
