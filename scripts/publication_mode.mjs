import { readFile, appendFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';

let maintenance = false;
if (existsSync('site/publication-state.json')) {
  const state = JSON.parse(await readFile('site/publication-state.json', 'utf8'));
  if (!['privacy-maintenance', 'public-template'].includes(state.status)) {
    throw new Error('Unknown publication state; refusing to deploy.');
  }
  maintenance = state.status === 'privacy-maintenance';
}
console.log(maintenance ? 'Privacy maintenance publication; model distribution is withheld.' : 'Normal model publication gates required.');
if (process.env.GITHUB_OUTPUT) {
  await appendFile(process.env.GITHUB_OUTPUT, `maintenance=${maintenance}\n`);
}
