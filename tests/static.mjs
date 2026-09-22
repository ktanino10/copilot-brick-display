import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const root = process.cwd();
const site = path.join(root, 'site');
const json = async (file) => JSON.parse(await readFile(path.join(root, file), 'utf8'));
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
const catalog = await json('design/catalog.json');
assert.deepEqual(await json('site/assets/catalog.json'), catalog);
assert.equal(catalog.units, 'mm');
assert.equal(catalog.parameters_sha256, digest(await readFile('design/parameters.json')));
const policy = await json('design/publication-policy.json');
if (policy.mode === 'generic') {
  assert.ok(['Same icon, New adventures', 'YOUR MESSAGE HERE', 'YOUR DISPLAY NAME', 'YOUR TEXT'].includes(catalog.message.lines[0]), 'Public generic first line must be an explicit placeholder/default.');
  assert.ok(catalog.message.lines[1] === 'github.com/USER', 'Public generic account line must remain a placeholder.');
  assert.equal(policy.public_text_approved, false);
} else {
  assert.equal(policy.mode, 'public_personalization');
  assert.equal(policy.public_text_approved, true, 'A public fork must explicitly approve public display values.');
}
assert.equal(catalog.message.interface_id, 'BASE-FRONT-NP3');
const required = [
  'index.html', 'guide.html', 'technical.html', 'rebuild.html', 'notices.html', 'customize.html', 'privacy.html', 'trial.html',
  'drawings/interface.svg', 'downloads/interface.pdf', 'downloads/fit-coupons.zip',
  'downloads/part-drawings.pdf', 'downloads/validation.json',
  'vendor/THREE-LICENSE.txt', 'vendor/B612-OFL.txt',
  'assembly.html', 'assembly-guide/index.html', 'assembly-guide/runtime.js', 'assembly-guide/style.css',
  'lettering.html', 'downloads/lettering.json', 'downloads/lettering-coupons.zip',
];
for (const model of catalog.models) {
  const prefix = `downloads/${model.id}/`;
  required.push(`assembly-guide/${model.id}.html`, `assembly-guide/${model.id}.mapping.json`,
    `assembly-guide/${model.id}-offline.zip`);
  const guide = await json(`site/assembly-guide/${model.id}.mapping.json`);
  assert.equal(guide.part_count, model.part_count);
  assert.equal(guide.sliced, false);
  assert.equal(guide.physical_fit_tested, false);
  assert.deepEqual(guide.placements.map(({ id, part, position, rotation }) => ({ id, part, position, rotation })),
    model.placements.map(({ id, part, position, rotation }) => ({ id, part, position, rotation })));
  for (const [key, part] of Object.entries(guide.parts)) assert.equal(part.sha256, catalog.parts[key].sha256);
  for (const filename of ['print-kit.zip', 'plates.zip', 'drawings.pdf', 'bom.csv', 'assembly.json',
    `${model.id}.FCStd`, `${model.id}.step`, `${model.id}.blend`]) required.push(prefix + filename);
  required.push(`media/${model.id}-hero.png`, `media/${model.id}-assembly.mp4`, `media/${model.id}-assembly.vtt`);
  assert.equal(model.part_count, model.placements.length);
  assert.equal(model.part_count, model.bom.reduce((total, row) => total + row.quantity, 0));
  assert.equal(new Set(model.placements.map((item) => item.id)).size, model.part_count);
  assert.equal((await readFile(path.join(site, prefix, `${model.id}.FCStd`))).subarray(0, 2).toString(), 'PK');
  assert.match((await readFile(path.join(site, prefix, `${model.id}.step`), 'utf8')).slice(0, 60), /ISO-10303-21/);
  assert.equal((await readFile(path.join(site, prefix, `${model.id}.blend`))).subarray(0, 7).toString(), 'BLENDER');
  const movie = await readFile(path.join(site, `media/${model.id}-assembly.mp4`));
  const boxes = new Map();
  for (let offset = 0; offset + 8 <= movie.length;) {
    let size = movie.readUInt32BE(offset);
    const type = movie.toString('ascii', offset + 4, offset + 8);
    if (size === 1) size = Number(movie.readBigUInt64BE(offset + 8));
    if (size === 0) size = movie.length - offset;
    assert.ok(size >= 8 && offset + size <= movie.length, 'Invalid MP4 box');
    boxes.set(type, offset);
    offset += size;
  }
  assert.ok(boxes.get('moov') < boxes.get('mdat'), `${model.id} must be faststart`);
  for (const step of model.steps) required.push(`drawings/${model.id}/step-${String(step.number).padStart(2, '0')}.svg`);
}
for (const part of Object.values(catalog.parts)) {
  const buffer = await readFile(path.join(site, 'downloads', part.stl));
  assert.equal(digest(buffer), part.sha256, part.id);
  assert.equal(buffer.length, 84 + buffer.readUInt32LE(80) * 50, part.id);
  assert.ok(part.volume_mm3 > 0 && part.bounds[0][2] >= 0, part.id);
  required.push(`drawings/parts/${part.id}.svg`);
}
const invariants = await json('design/public-template-invariants.json');
for (const [part, expected] of Object.entries(invariants.unchanged_nontext_stl_sha256)) {
  assert.equal(catalog.parts[part].sha256, expected, `Non-text mechanical master changed: ${part}`);
}
for (const file of required) assert.ok((await stat(path.join(site, file))).size > 0, file);

async function walk(folder) {
  const all = [];
  for (const entry of await readdir(folder, { withFileTypes: true })) {
    const filename = path.join(folder, entry.name);
    if (entry.isDirectory()) all.push(...await walk(filename));
    else all.push(filename);
  }
  return all;
}
let links = 0;
for (const filename of await walk(site)) {
  const relative = path.relative(site, filename);
  const content = await readFile(filename);
  assert.ok(!/\/Users\/[A-Za-z][^\0\n<>" ]*/.test(content.toString('latin1')), `Private absolute path: ${relative}`);
  if (/\.(html|css|js|json|svg|txt|vtt|csv)$/.test(filename)) {
    assert.ok(!content.includes(Buffer.from('.copilot/attachments')), relative);
    assert.ok(!content.includes(Buffer.from('session-state/')), relative);
  }
  if (!filename.endsWith('.html')) continue;
  const html = content.toString('utf8');
  for (const match of html.matchAll(/\b(?:src|href|poster)=["']([^"']+)["']/g)) {
    const ref = match[1].replaceAll('&amp;', '&');
    if (/^(https?:|mailto:|data:|blob:)/.test(ref)) continue;
    assert.ok(!ref.startsWith('/'), `Root-absolute URL breaks repository prefix: ${relative} -> ${ref}`);
    const url = new URL(ref, `https://local.invalid/${relative}`);
    let target = path.join(site, decodeURIComponent(url.pathname));
    if ((await stat(target)).isDirectory()) target = path.join(target, 'index.html');
    assert.ok((await stat(target)).isFile(), `${relative} -> ${ref}`);
    if (url.hash && target.endsWith('.html')) {
      const targetHtml = await readFile(target, 'utf8');
      assert.ok(targetHtml.includes(`id="${url.hash.slice(1)}"`), `${relative} -> ${ref}`);
    }
    links += 1;
  }
}
const evidence = await json('site/downloads/validation.json');
assert.equal(evidence.parameters_sha256, catalog.parameters_sha256);
assert.equal(evidence.physical_testing, 'NOT_PERFORMED');
assert.ok(evidence.digital_checks_passed);
const withheldFiles = await walk(path.join(site, 'tribute'));
assert.deepEqual(withheldFiles.map((file) => path.relative(path.join(site, 'tribute'), file)), ['index.html']);
assert.match(await readFile(path.join(site, 'tribute/index.html'), 'utf8'), /公開配布していません/);
assert.equal(evidence.publication_mode, policy.mode);
console.log(`PASS: ${catalog.models.length} models, ${Object.keys(catalog.parts).length} unique STL hashes, ${links} static links, native signatures, MP4 containers, and privacy scan.`);
