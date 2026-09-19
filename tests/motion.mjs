import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { explosionOffset } from '../site/assembly-motion.js';

const catalog = JSON.parse(await readFile('design/catalog.json', 'utf8'));
const samples = [];
const displays = [];
assert.ok(catalog.parts['NP3-KEEPER'].bounds[1][1] <= 16);
function bounds(part, instance, offset) {
  const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  for (const x of [part.bounds[0][0], part.bounds[1][0]]) {
    for (const y of [part.bounds[0][1], part.bounds[1][1]]) {
      for (const z of [part.bounds[0][2], part.bounds[1][2]]) {
        const point = instance.rotation[0] === 90 ? [x, -z, y] : [x, y, z];
        assert.deepEqual(instance.rotation.slice(1), [0, 0]);
        point.forEach((value, axis) => {
          const world = value + instance.position[axis] + offset[axis];
          low[axis] = Math.min(low[axis], world);
          high[axis] = Math.max(high[axis], world);
        });
      }
    }
  }
  return [low, high];
}
for (const model of catalog.models) {
  const maxLayer = model.base_courses + model.body_courses;
  for (let percent = 0; percent <= 100; percent++) {
    const offsets = {};
    for (const instance of model.placements) {
      const value = explosionOffset(instance, model, catalog.message, percent / 100);
      if (percent === 0) assert.deepEqual(value, [0, 0, 0]);
      if (instance.role === 'front_module') {
        if (percent <= 15) assert.equal(value[2], 0);
        if (percent <= 30) assert.ok(Math.abs(value[1]) < 1e-9);
        if (percent > 30 && percent <= 40) assert.ok(value[2] >= 45 - 1e-8);
      }
      if (instance.role === 'keeper' && percent >= 15) {
        assert.ok(-value[1] >= 16 + model.presentation.plaque_front_clearance_mm + 2 - 1e-8);
      }
      offsets[instance.id] = value;
    }
    samples.push({ model: model.id, percent, offsets });
    if (![0, 50, 100].includes(percent)) continue;
    const lows = [Infinity, Infinity, Infinity], highs = [-Infinity, -Infinity, -Infinity];
    const layers = new Map();
    for (const instance of model.placements) {
      const box = bounds(catalog.parts[instance.part], instance, offsets[instance.id]);
      box[0].forEach((value, axis) => { lows[axis] = Math.min(lows[axis], value); });
      box[1].forEach((value, axis) => { highs[axis] = Math.max(highs[axis], value); });
      if (instance.role === 'face' || instance.role === 'base_course') {
        const layer = Math.round(instance.position[2] / 9.6);
        const prior = layers.get(layer) || [Infinity, -Infinity];
        layers.set(layer, [Math.min(prior[0], box[0][2]), Math.max(prior[1], box[1][2])]);
      }
    }
    const gaps = [...layers.keys()].sort((a, b) => a - b).slice(1)
      .map((layer) => layers.get(layer)[0] - layers.get(layer - 1)[1]);
    if (percent === 100) {
      assert.equal(layers.size, maxLayer + 1);
      assert.ok(Math.min(...gaps) >= 9.6, `${model.id}: smallest expanded course gap ${Math.min(...gaps)}`);
      const bottom = model.placements.find((item) => item.role === 'base_course' && item.course === 0);
      const top = model.placements.find((item) => Math.abs(item.position[2] / 9.6 - maxLayer) < 1e-5);
      assert.ok(offsets[bottom.id][2] < 0 && offsets[top.id][2] > 0);
    }
    displays.push({ model: model.id, percent, offsets, bounds: [lows, highs],
      minimum_course_gap_mm: Math.min(...gaps), dimension_note: 'Display displacement, not changed printable size.' });
  }
}
assert.throws(() => explosionOffset({}, {}, {}, Number.NaN), RangeError);
await mkdir('build', { recursive: true });
await writeFile('build/explosion-samples.json', JSON.stringify(samples, null, 2));
await writeFile('build/display-states.json', JSON.stringify(displays, null, 2));
console.log(`PASS ${samples.length} stages; modules release before spreading; all 100% course gaps >=9.6mm, centered up/down.`);
