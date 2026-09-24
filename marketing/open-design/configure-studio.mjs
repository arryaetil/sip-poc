// Use the installed local runner in the browser; credentials stay in the gateway.
import { readFile, writeFile, chown } from 'node:fs/promises';
import path from 'node:path';

if (!process.env.STUDIO_OPENAI_API_KEY) {
  throw new Error('STUDIO_OPENAI_API_KEY is required for the SIP studio');
}
const file = path.join(process.env.OD_DATA_DIR || '/app/.od', 'app-config.json');
let config = {};
try {
  config = JSON.parse(await readFile(file, 'utf8'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
config.onboardingCompleted = true;
config.agentId = 'opencode';
config.agentModels = {
  ...config.agentModels,
  opencode: { model: process.env.STUDIO_MODEL || 'gpt-5.6-terra' },
};
await writeFile(file, JSON.stringify(config, null, 2) + '\n', { mode: 0o600 });
await chown(file, 1001, 1001);
