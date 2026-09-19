import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

async function files(folder) {
  const result = [];
  for (const entry of await readdir(folder, { withFileTypes: true })) {
    const target = path.join(folder, entry.name);
    if (entry.isDirectory()) result.push(...await files(target));
    else result.push(target);
  }
  return result;
}
assert.deepEqual((await files('site')).sort(), ['site/index.html', 'site/publication-state.json']);
const state = JSON.parse(await readFile('site/publication-state.json', 'utf8'));
assert.equal(state.status, 'privacy-maintenance');
assert.equal(state.model_downloads, false);
const html = await readFile('site/index.html', 'utf8');
assert.ok(html.includes('privacy-maintenance'));
assert.ok(html.includes('YOUR-USERNAME'));
assert.ok(!/\b(?:src|href|poster)=/.test(html), 'The holding page must not reference withdrawn artifacts.');
console.log('PASS maintenance-only artifact: no model, archive, image, video or private-input distribution.');
