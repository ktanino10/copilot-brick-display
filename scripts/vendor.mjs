import { mkdir, copyFile } from 'node:fs/promises';

await mkdir('site/vendor', { recursive: true });
for (const [source, destination] of [
  ['node_modules/three/build/three.module.js', 'three.module.js'],
  ['node_modules/three/build/three.core.js', 'three.core.js'],
  ['node_modules/three/examples/jsm/controls/OrbitControls.js', 'OrbitControls.js'],
  ['node_modules/three/examples/jsm/loaders/STLLoader.js', 'STLLoader.js'],
  ['node_modules/three/LICENSE', 'THREE-LICENSE.txt'],
  ['resources/fonts/B612Mono-Bold.ttf', 'B612Mono-Bold.ttf'],
  ['resources/fonts/OFL.txt', 'B612-OFL.txt'],
]) {
  await copyFile(source, `site/vendor/${destination}`);
}
console.log('Vendored the pinned Three.js runtime and MIT notice (no CDN).');
