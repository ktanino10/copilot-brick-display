import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { STLLoader } from './vendor/STLLoader.js';
import { explosionOffset } from './assembly-motion.js?rev=3.0-five-course-front';

const $ = (selector) => document.querySelector(selector);
const REVISION = $('meta[name="design-revision"]').content;
const asset = (relative) => `${relative}?rev=${encodeURIComponent(REVISION)}`;
const format = (values) => values.map((n) => Number(n.toFixed(2))).join(' × ');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const state = { catalog: null, model: null, token: 0, stage: 0, explosion: 0, playing: false, selected: null };
const geometryCache = new Map();
let viewer;

function showError(message) {
  $('#loading').hidden = true;
  $('#viewer-error').hidden = false;
  $('#viewer-error').textContent = message;
  $('#viewport').classList.remove('viewer-ready');
}

async function getGeometry(part) {
  if (!geometryCache.has(part.id)) {
    const promise = new STLLoader().loadAsync(asset(`downloads/${part.stl}`)).then((geometry) => {
      geometry.computeBoundingBox();
      if (!Number.isFinite(geometry.boundingBox.max.x) || geometry.boundingBox.isEmpty()) {
        throw new Error(`空の形状: ${part.id}`);
      }
      return geometry;
    }).catch((error) => {
      geometryCache.delete(part.id);
      throw error;
    });
    geometryCache.set(part.id, promise);
  }
  return geometryCache.get(part.id);
}

class PortraitViewer {
  constructor() {
    this.canvas = $('#scene');
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: true, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-200, 200, 200, -200, .1, 5000);
    this.camera.up.set(0, 0, 1);
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enableDamping = !reducedMotion;
    this.controls.dampingFactor = .11;
    this.controls.minZoom = .35;
    this.controls.maxZoom = 5;
    this.controls.maxPolarAngle = Math.PI * .96;
    this.lastCameraRotation = new THREE.Quaternion();
    this.controls.addEventListener('change', () => {
      if (this.lastCameraRotation.angleTo(this.camera.quaternion) > .00001) {
        this.projectionDirty = true;
        this.lastCameraRotation.copy(this.camera.quaternion);
      }
      this.dirty = true;
    });
    this.scene.add(new THREE.HemisphereLight(0xe5f4ff, 0x657283, 2.3));
    const key = new THREE.DirectionalLight(0xffffff, 3.2);
    key.position.set(-220, -350, 550);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -350, right: 350, top: 350, bottom: -350, near: 1, far: 1200 });
    key.shadow.bias = -.00015;
    key.shadow.normalBias = .3;
    this.scene.add(key);
    this.scene.add(key.target);
    const fill = new THREE.DirectionalLight(0xaddaf7, 1.5);
    fill.position.set(280, 120, 280);
    this.scene.add(fill);
    this.content = new THREE.Group();
    this.scene.add(this.content);
    this.selection = new THREE.Box3Helper(new THREE.Box3(), 0xc42eaa);
    this.selection.visible = false;
    this.scene.add(this.selection);
    this.raycaster = new THREE.Raycaster();
    this.materials = new Map();
    this.meshes = [];
    this.visibleBounds = new THREE.Box3();
    this.lastFitCenter = null;
    this.cornerScratch = new THREE.Vector3();
    this.dirty = true;
    this.lastStageTime = 0;
    new ResizeObserver(() => this.resize()).observe($('#viewport'));
    this.canvas.addEventListener('pointerdown', (event) => {
      this.pointerStart = [event.clientX, event.clientY];
    });
    this.canvas.addEventListener('pointerup', (event) => {
      if (!this.pointerStart || Math.hypot(event.clientX - this.pointerStart[0], event.clientY - this.pointerStart[1]) > 6) return;
      const rect = this.canvas.getBoundingClientRect();
      this.raycaster.setFromCamera(new THREE.Vector2(
        (event.clientX - rect.left) / rect.width * 2 - 1,
        -(event.clientY - rect.top) / rect.height * 2 + 1,
      ), this.camera);
      const picked = this.raycaster.intersectObjects(this.meshes.filter((mesh) => mesh.visible), false)[0];
      if (picked) selectPart(picked.object.userData.instance.id);
    });
    this.canvas.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const offset = this.camera.position.clone().sub(this.controls.target);
      offset.applyAxisAngle(new THREE.Vector3(0, 0, 1), event.key === 'ArrowLeft' ? -.12 : .12);
      this.camera.position.copy(this.controls.target).add(offset);
      this.controls.update();
      this.dirty = true;
    });
    this.canvas.addEventListener('webglcontextlost', (event) => {
      event.preventDefault();
      showError('3D表示が停止しました。ページを再読込してください。完成画像・図面・印刷ファイルは引き続き利用できます。');
    });
    requestAnimationFrame((time) => this.frame(time));
  }

  clear() {
    for (const child of [...this.content.children]) {
      this.content.remove(child);
      if (child.userData.disposable) {
        child.geometry?.dispose();
        child.material?.dispose();
      }
    }
    this.meshes = [];
    this.selection.visible = false;
  }

  material(color) {
    if (!this.materials.has(color)) {
      this.materials.set(color, new THREE.MeshStandardMaterial({
        color: state.catalog.colors[color].hex, roughness: .4, metalness: .03,
      }));
    }
    return this.materials.get(color);
  }

  setModel(model, geometries) {
    this.clear();
    for (const instance of model.placements) {
      const geometry = geometries.get(instance.part);
      let material = this.material(instance.color);
      const partSpec = state.catalog.parts[instance.part];
      if (partSpec.kind === 'front_plaque' || partSpec.kind === 'front_logo') {
        if (!geometry.getAttribute('color')) {
          const colors = new Float32Array(geometry.getAttribute('position').count * 3);
          const light = new THREE.Color(state.catalog.colors[partSpec.letter_color].hex);
          const black = new THREE.Color(state.catalog.colors.black.hex);
          const position = geometry.getAttribute('position');
          for (let triangle = 0; triangle < position.count; triangle += 3) {
            const middle = (position.getZ(triangle) + position.getZ(triangle + 1) + position.getZ(triangle + 2)) / 3;
            const color = middle > partSpec.optional_color_change_z + .001 ? light : black;
            for (let vertex = triangle; vertex < triangle + 3; vertex++) color.toArray(colors, vertex * 3);
          }
          geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        }
        if (!this.cardMaterial) this.cardMaterial = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .45 });
        material = this.cardMaterial;
      }
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = instance.id;
      mesh.position.fromArray(instance.position);
      mesh.rotation.set(...instance.rotation.map(THREE.MathUtils.degToRad));
      mesh.updateMatrix();
      mesh.userData.rotatedBounds = geometry.boundingBox.clone().applyMatrix4(
        new THREE.Matrix4().makeRotationFromEuler(mesh.rotation),
      );
      mesh.userData.displayBounds = new THREE.Box3();
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.instance = instance;
      this.content.add(mesh);
      this.meshes.push(mesh);
    }
    const [w, d] = model.actual_mm;
    const gridSize = Math.ceil(Math.max(w, d) * 1.6 / 8) * 8;
    const grid = new THREE.GridHelper(gridSize, gridSize / 8, 0xa5bcd2, 0xc6d6e4);
    grid.rotation.x = Math.PI / 2;
    grid.position.set(w / 2, d / 2, -.2);
    grid.material.transparent = true;
    grid.material.opacity = .46;
    grid.userData.disposable = true;
    this.grid = grid;
    this.content.add(grid);
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(gridSize * 2, gridSize * 2),
      new THREE.ShadowMaterial({ color: 0x526b80, opacity: .17 }),
    );
    floor.position.set(w / 2, d / 2, -.3);
    floor.receiveShadow = true;
    floor.userData.disposable = true;
    this.floor = floor;
    this.content.add(floor);
    this.bounds = new THREE.Box3Helper(
      new THREE.Box3(new THREE.Vector3(...model.bounds[0]), new THREE.Vector3(...model.bounds[1])),
      0x2952a6,
    );
    this.bounds.visible = $('#bounds').checked;
    this.bounds.userData.disposable = true;
    this.content.add(this.bounds);
    this.update();
    this.view('iso');
    $('#viewport').dataset.instances = String(this.meshes.length);
    $('#viewport').dataset.model = model.id;
  }

  view(name) {
    if (!state.model) return;
    this.currentView = name;
    const [w, , h] = state.model.actual_mm;
    const center = this.visibleBounds.isEmpty()
      ? new THREE.Vector3(...state.model.bounds[0]).add(new THREE.Vector3(...state.model.bounds[1])).multiplyScalar(.5)
      : this.visibleBounds.getCenter(new THREE.Vector3());
    const offsets = {
      iso: new THREE.Vector3(.7, -1.8, .85),
      front: new THREE.Vector3(0, -2, 0),
      side: new THREE.Vector3(2, 0, 0),
      top: new THREE.Vector3(0, -.0001, 2),
    };
    this.controls.target.copy(center);
    this.lastFitCenter = center.clone();
    this.camera.position.copy(center).add(offsets[name].multiplyScalar(Math.max(w, h) * 2));
    this.camera.zoom = 1;
    this.camera.lookAt(center);
    this.controls.update();
    this.resize();
    for (const button of document.querySelectorAll('[data-view]')) button.setAttribute('aria-pressed', String(button.dataset.view === name));
  }

  resize() {
    const { width, height } = $('#viewport').getBoundingClientRect();
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.fitProjection();
    this.dirty = true;
  }

  fitProjection() {
    if (this.visibleBounds.isEmpty()) return;
    const { width, height } = $('#viewport').getBoundingClientRect();
    if (!width || !height) return;
    this.camera.updateMatrixWorld(true);
    let horizontal = 0;
    let vertical = 0;
    for (const x of [this.visibleBounds.min.x, this.visibleBounds.max.x]) {
      for (const y of [this.visibleBounds.min.y, this.visibleBounds.max.y]) {
        for (const z of [this.visibleBounds.min.z, this.visibleBounds.max.z]) {
          this.cornerScratch.set(x, y, z).applyMatrix4(this.camera.matrixWorldInverse);
          horizontal = Math.max(horizontal, Math.abs(this.cornerScratch.x));
          vertical = Math.max(vertical, Math.abs(this.cornerScratch.y));
        }
      }
    }
    const halfHeight = Math.max(vertical, horizontal * height / width, 15) * 1.22;
    this.camera.left = -halfHeight * width / height;
    this.camera.right = halfHeight * width / height;
    this.camera.top = halfHeight;
    this.camera.bottom = -halfHeight;
    this.camera.updateProjectionMatrix();
    this.projectionDirty = false;
    $('#viewport').dataset.displayBounds = JSON.stringify([this.visibleBounds.min.toArray(), this.visibleBounds.max.toArray()]);
    $('#viewport').dataset.cameraTarget = JSON.stringify(this.controls.target.toArray());
    $('#viewport').dataset.cameraDirection = JSON.stringify(this.camera.getWorldDirection(new THREE.Vector3()).toArray());
    let maxClip = 0;
    for (const x of [this.visibleBounds.min.x, this.visibleBounds.max.x]) {
      for (const y of [this.visibleBounds.min.y, this.visibleBounds.max.y]) {
        for (const z of [this.visibleBounds.min.z, this.visibleBounds.max.z]) {
          this.cornerScratch.set(x, y, z).project(this.camera);
          maxClip = Math.max(maxClip, Math.abs(this.cornerScratch.x), Math.abs(this.cornerScratch.y), Math.abs(this.cornerScratch.z));
        }
      }
    }
    $('#viewport').dataset.maxClipCoordinate = String(maxClip);
    this.dirty = true;
  }

  update() {
    this.visibleBounds.makeEmpty();
    const layers = new Map();
    let zeroError = 0;
    const moduleBounds = {};
    let lowestOffset = Infinity;
    let highestOffset = -Infinity;
    for (const mesh of this.meshes) {
      const item = mesh.userData.instance;
      mesh.visible = item.step <= state.stage;
      mesh.position.fromArray(item.position);
      const offset = explosionOffset(item, state.model, state.catalog.message, state.explosion);
      mesh.position.add(new THREE.Vector3(...offset));
      mesh.userData.displayBounds.copy(mesh.userData.rotatedBounds).translate(mesh.position);
      if (mesh.visible) this.visibleBounds.union(mesh.userData.displayBounds);
      zeroError = Math.max(zeroError, ...mesh.position.toArray().map((value, axis) => Math.abs(value - item.position[axis])));
      if (mesh.visible && (item.role === 'face' || item.role === 'base_course')) {
        const layer = Math.round(item.position[2] / 9.6);
        const range = layers.get(layer) || [Infinity, -Infinity];
        layers.set(layer, [Math.min(range[0], mesh.userData.displayBounds.min.z),
          Math.max(range[1], mesh.userData.displayBounds.max.z)]);
        lowestOffset = Math.min(lowestOffset, offset[2]);
        highestOffset = Math.max(highestOffset, offset[2]);
      }
      if (item.role === 'front_module') {
        moduleBounds[item.module] = [mesh.userData.displayBounds.min.toArray(), mesh.userData.displayBounds.max.toArray()];
      }
    }
    const selected = this.meshes.find((mesh) => mesh.name === state.selected);
    this.selection.visible = !!selected?.visible;
    if (selected?.visible) this.selection.box.copy(selected.userData.displayBounds);
    if (this.bounds) {
      this.bounds.visible = $('#bounds').checked && !this.visibleBounds.isEmpty();
      this.bounds.box.copy(this.visibleBounds);
    }
    if (this.grid) this.grid.visible = state.explosion === 0 && state.stage > 0;
    if (this.floor) this.floor.visible = state.explosion === 0 && state.stage > 0;
    if (!this.visibleBounds.isEmpty()) {
      const center = this.visibleBounds.getCenter(new THREE.Vector3());
      if (this.lastFitCenter) {
        const delta = center.clone().sub(this.lastFitCenter);
        this.controls.target.add(delta);
        this.camera.position.add(delta);
      }
      this.lastFitCenter = center;
      const diagonal = this.visibleBounds.getSize(new THREE.Vector3()).length();
      const direction = this.camera.position.clone().sub(this.controls.target).normalize();
      const distance = Math.max(this.camera.position.distanceTo(this.controls.target), diagonal * 2 + 100);
      this.camera.position.copy(this.controls.target).addScaledVector(direction, distance);
      this.camera.near = Math.max(.1, distance - diagonal * 2);
      this.camera.far = distance + diagonal * 3 + 100;
      this.controls.update();
      this.fitProjection();
    }
    $('#viewport').dataset.visibleInstances = String(this.meshes.filter((mesh) => mesh.visible).length);
    const courseKeys = [...layers.keys()].sort((a, b) => a - b);
    const gaps = courseKeys.slice(1).filter((layer) => layers.has(layer - 1))
      .map((layer) => layers.get(layer)[0] - layers.get(layer - 1)[1]);
    $('#viewport').dataset.courseGapMm = String(gaps.length ? Math.min(...gaps) : 0);
    $('#viewport').dataset.zeroPoseError = String(zeroError);
    $('#viewport').dataset.frontModuleBounds = JSON.stringify(moduleBounds);
    $('#viewport').dataset.verticalOffsets = JSON.stringify([Number.isFinite(lowestOffset) ? lowestOffset : 0,
      Number.isFinite(highestOffset) ? highestOffset : 0]);
    this.dirty = true;
  }

  frame(time) {
    requestAnimationFrame((next) => this.frame(next));
    if (state.playing && time - this.lastStageTime > 650) {
      this.lastStageTime = time;
      setStage(state.stage + 1);
      if (state.stage >= state.model.steps.length) setPlaying(false);
    }
    this.controls.update();
    if (this.projectionDirty) this.fitProjection();
    if (this.dirty) {
      this.renderer.render(this.scene, this.camera);
      this.dirty = false;
    }
  }
}

function updateLinks(model) {
  const id = model.id;
  $('.model-print-link').href = asset(`downloads/${id}/print-kit.zip`);
  $('.model-print-link').innerHTML = `${id}の印刷セット <span>↓</span>`;
  $('.model-guide-link').href = `guide.html?model=${id}&rev=${encodeURIComponent(REVISION)}`;
  $('#download-model').textContent = `${id} / ${model.name}`;
  const files = ['print-kit.zip', `${id}.FCStd`, `${id}.step`, 'drawings.pdf', 'bom.csv', 'plates.zip'];
  [...$('#download-links').children].forEach((link, index) => { link.href = asset(`downloads/${id}/${files[index]}`); });
  const video = $('#assembly-video');
  video.pause();
  video.poster = asset(`media/${id}-hero.png`);
  video.querySelector('source').src = asset(`media/${id}-assembly.mp4`);
  video.querySelector('track').src = asset(`media/${id}-assembly.vtt`);
  $('#base-front-preview').src = asset(`media/${id}-base-front.png`);
  video.load();
  $('#film-model').textContent = id;
  $('#video-download').href = asset(`media/${id}-assembly.mp4`);
  $('#blend-download').href = asset(`downloads/${id}/${id}.blend`);
}

function setPlaying(value) {
  state.playing = value;
  $('#play').textContent = value ? 'Ⅱ' : '▶';
  $('#play').setAttribute('aria-label', value ? '組立を一時停止' : '組立を再生');
}

function setStage(value) {
  state.stage = Math.min(state.model.steps.length, Math.max(0, value));
  $('#assembly').value = String(state.stage);
  const completed = state.stage === state.model.steps.length;
  $('#assembly-value').textContent = completed ? '完成' : `${state.stage} / ${state.model.steps.length}`;
  const title = state.stage ? state.model.steps[state.stage - 1].title : '部品をまだ置いていない状態です。';
  $('#assembly').setAttribute('aria-valuetext', title);
  $('#step-caption').textContent = completed ? '完成形。部品をクリックして寸法と印刷ファイルを確認できます。' : `${String(state.stage).padStart(2, '0')} — ${title}`;
  viewer?.update();
}

function selectPart(id) {
  state.selected = id || null;
  $('#part-select').value = id || '';
  const item = state.model.placements.find((part) => part.id === id);
  $('#part-drawing').hidden = !item;
  $('#part-empty').hidden = !!item;
  const details = $('#part-details');
  details.replaceChildren();
  if (item) {
    const part = state.catalog.parts[item.part];
    const quantity = state.model.bom.find((row) => row.part === item.part && row.color === item.color).quantity;
    const dimensions = part.bounds[1].map((value, axis) => value - part.bounds[0][axis]);
    const title = document.createElement('h3');
    title.textContent = `${item.id} / ${item.part}`;
    details.append(title);
    const dl = document.createElement('dl');
    for (const [label, value] of [
      ['色', state.catalog.colors[item.color].name_ja],
      ['印刷外形', `${format(dimensions)} mm`],
      ['必要数', `この色・形状で ${quantity} 点`],
      ['組立工程', `${item.step} / ${state.model.steps.length}`],
      ['配置 / mm', `[${item.position.join(', ')}]`],
    ]) {
      const dt = document.createElement('dt');
      dt.textContent = label;
      const dd = document.createElement('dd');
      dd.textContent = value;
      dl.append(dt, dd);
    }
    details.append(dl);
    const note = document.createElement('p');
    note.className = 'fine';
    note.textContent = part.optional_color_change_z
      ? `黒い前面モジュール。${part.optional_color_change_z} mm層後に白へ手動色替え。5段台座の正面内に収まります。`
      : '外形はスタッド込み。形状IDのHはスタッドを除く本体高さです。';
    details.append(note);
    for (const [label, href] of [
      ['STLを保存 ↓', `downloads/${part.stl}`],
      ['寸法図を開く ↗', `drawings/parts/${item.part}.svg`],
      ['この工程の配置図 ↗', `drawings/${state.model.id}/step-${String(item.step).padStart(2, '0')}.svg`],
    ]) {
      const link = document.createElement('a');
      link.href = asset(href);
      link.textContent = label;
      details.append(link);
    }
    $('#part-drawing').src = asset(`drawings/parts/${item.part}.svg`);
    $('#part-drawing').alt = `${item.part}のCAD由来の三面図と印刷外形寸法`;
  } else {
    details.textContent = '選んだ部品の形状ID・色・寸法・三面図がここに表示されます。';
  }
  viewer?.update();
}

async function chooseModel(id) {
  const model = state.catalog.models.find((value) => value.id === id);
  if (!model) throw new Error(`未知のモデル: ${id}`);
  const token = ++state.token;
  state.model = model;
  state.explosion = 0;
  $('#explode').value = '0';
  $('#explode-value').textContent = '0%';
  setPlaying(false);
  for (const button of document.querySelectorAll('button[data-model]')) {
    button.classList.toggle('active', button.dataset.model === id);
    button.setAttribute('aria-pressed', String(button.dataset.model === id));
  }
  $('#model-description').textContent = model.description_ja;
  $('#model-dimensions').innerHTML = `${format(model.actual_mm)} <span>mm</span>`;
  $('#part-count').innerHTML = `${model.part_count} <span>点</span>`;
  $('#step-count').innerHTML = `${model.steps.length} <span>工程</span>`;
  $('#target-dimensions').textContent = `黒い台座は5段・本体高48 mm。顔は同じ形状のまま38.4 mm上へ。完成高は最上部スタッド込みです。`;
  $('#viewer-model').textContent = id;
  $('#viewer-fallback').src = asset(`media/${id}-hero.png`);
  $('#viewer-fallback').alt = `${id}の完成形。実Blenderレンダー。`;
  $('#assembly').max = String(model.steps.length);
  const select = $('#part-select');
  select.replaceChildren(new Option('3Dの部品をクリック、またはここから選択', ''));
  for (const part of model.placements) {
    select.add(new Option(`${part.id} · ${state.catalog.colors[part.color].name_ja} · ${part.part}`, part.id));
  }
  selectPart('');
  updateLinks(model);
  setStage(model.steps.length);
  const url = new URL(location.href);
  url.searchParams.set('model', id);
  history.replaceState(null, '', url);
  if (!viewer) return;
  $('#loading').hidden = false;
  $('#viewer-error').hidden = true;
  $('#viewport').setAttribute('aria-busy', 'true');
  $('#viewport').classList.remove('viewer-ready');
  const keys = [...new Set(model.placements.map((item) => item.part))];
  let complete = 0;
  try {
    const geometries = new Map(await Promise.all(keys.map(async (key) => {
      const geometry = await getGeometry(state.catalog.parts[key]);
      complete += 1;
      if (token === state.token) $('#loading p').textContent = `印刷形状を読み込み中 ${complete} / ${keys.length}`;
      return [key, geometry];
    })));
    if (token !== state.token) return;
    viewer.setModel(model, geometries);
    $('#loading').hidden = true;
    $('#viewport').classList.add('viewer-ready');
    $('#viewport').setAttribute('aria-busy', 'false');
  } catch (error) {
    if (token !== state.token) return;
    showError(`形状を読み込めませんでした。再読込するか、印刷セット・図面をご利用ください。${error.message}`);
    $('#viewport').setAttribute('aria-busy', 'false');
  }
}

async function boot() {
  const response = await fetch(asset('assets/catalog.json'));
  if (!response.ok) throw new Error(`設計データ HTTP ${response.status}`);
  state.catalog = await response.json();
  if (state.catalog.revision !== REVISION) throw new Error('公開revisionと設計データが一致しません。キャッシュを更新して再読込してください。');
  try {
    viewer = new PortraitViewer();
  } catch (error) {
    showError(`この環境では3D表示を開始できません。完成画像と図面を表示します。${error.message}`);
  }
  document.querySelectorAll('button[data-model]').forEach((button) => {
    button.addEventListener('click', () => chooseModel(button.dataset.model));
  });
  document.querySelectorAll('[data-switch]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      chooseModel(link.dataset.switch);
      $('#workbench').scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth' });
    });
  });
  document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => viewer?.view(button.dataset.view)));
  $('#explode').addEventListener('input', (event) => {
    const previous = state.explosion;
    state.explosion = Number(event.target.value) / 100;
    $('#explode-value').textContent = `${event.target.value}%`;
    if (viewer) {
      if (previous === 0 && state.explosion > 0) viewer.restZoom = viewer.camera.zoom;
      viewer.camera.zoom = state.explosion === 0 ? viewer.restZoom || 1 : 1;
    }
    viewer?.update();
    viewer?.resize();
  });
  $('#assembly').addEventListener('input', (event) => {
    setPlaying(false);
    setStage(Number(event.target.value));
  });
  $('#play').addEventListener('click', () => {
    if (!viewer) return;
    if (!state.playing && state.stage === state.model.steps.length) setStage(0);
    setPlaying(!state.playing);
  });
  $('#bounds').addEventListener('change', () => viewer?.update());
  $('#part-select').addEventListener('change', (event) => selectPart(event.target.value));
  const requested = new URLSearchParams(location.search).get('model');
  await chooseModel(['A', 'B', 'C'].includes(requested) ? requested : 'B');
}

boot().catch((error) => showError(`設計データを読み込めませんでした。下の直接ダウンロードをご利用ください。${error.message}`));
