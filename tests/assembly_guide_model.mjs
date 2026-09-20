import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { indexGuide, insertionPose, stepRange } from '../web/assembly-guide/model.js';

const catalog = JSON.parse(await readFile('design/catalog.json', 'utf8'));
for (const model of catalog.models) {
  for (const placement of model.placements) {
    const motion = { module_lift_mm: 45, module_front_mm: 32, keeper_lift_mm: 16 };
    assert.deepEqual(insertionPose(placement, 1, motion), {
      position: placement.position, rotation: placement.rotation,
    });
    for (const t of [0, .14, .28, .4, .55, .8, .99, 1]) {
      const pose = insertionPose(placement, t, motion);
      assert.ok(pose.position.every(Number.isFinite) && pose.rotation.every(Number.isFinite));
      assert.ok(pose.position[2] >= placement.position[2]);
      if (placement.role === 'front_module' && t >= .55) {
        assert.equal(pose.position[1], placement.position[1]);
        assert.deepEqual(pose.rotation, placement.rotation);
      }
    }
    assert.throws(() => insertionPose(placement, -1, motion), RangeError);
    assert.throws(() => insertionPose(placement, NaN, motion), RangeError);
  }
}
assert.deepEqual(stepRange({ steps: [{ first_index: 0, end_index: 1 }] }, 0), [0, 0]);
assert.throws(() => stepRange({ steps: [] }, 1), RangeError);
assert.throws(() => indexGuide({ schema_version: 2 }), /未対応/);
console.log('PASS unchanged final poses for all A/B/C placements and staged front-module insertion.');
