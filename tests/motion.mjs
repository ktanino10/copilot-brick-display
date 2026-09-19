import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { explosionOffset } from '../site/assembly-motion.js';

const catalog = JSON.parse(await readFile('design/catalog.json', 'utf8'));
const cases = [];
for (const model of catalog.models) {
  const card = model.placements.find((item) => item.part === 'MSG-CARD');
  const dock = model.placements.find((item) => item.part === 'MSG-DOCK');
  for (let percent = 0; percent <= 100; percent += 1) {
    const amount = percent / 100;
    const cardOffset = explosionOffset(card, model, catalog.message, amount);
    const dockOffset = explosionOffset(dock, model, catalog.message, amount);
    assert.ok(cardOffset[2] >= dockOffset[2]);
    if (percent <= 25) assert.equal(cardOffset[1], 0);
    if (percent > 25) {
      assert.ok(cardOffset[2] - dockOffset[2] >= catalog.message.slot_depth + .6 - 1e-9);
    }
    if (percent === 0) assert.deepEqual(cardOffset.map((v) => v || 0), [0, 0, 0]);
    cases.push({ model: model.id, percent, cardOffset, dockOffset });
  }
}
assert.throws(() => explosionOffset({}, {}, {}, Number.NaN), RangeError);
await mkdir('build', { recursive: true });
await writeFile('build/explosion-samples.json', JSON.stringify(cases, null, 2));
console.log(`PASS ${cases.length} actual viewer motion samples: lift card before any sideways travel.`);
