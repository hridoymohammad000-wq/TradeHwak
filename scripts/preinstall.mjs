import { rmSync } from 'node:fs';
import { resolve } from 'node:path';

const projectRoot = resolve(import.meta.dirname, '..');
for (const filename of ['package-lock.json', 'yarn.lock']) {
  rmSync(resolve(projectRoot, filename), { force: true });
}

const userAgent = process.env.npm_config_user_agent || '';
if (!userAgent.startsWith('pnpm/')) {
  console.error('Use pnpm instead of npm or yarn.');
  process.exit(1);
}
