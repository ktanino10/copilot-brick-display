import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { STLLoader } from './vendor/STLLoader.js';
import { explosionOffset } from './assembly-motion.js';

const $ = (selector) => document.querySelector(selector);
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
    const promise = new STLLoader().loadAsync(`downloads/${part.stl}`).then((geometry) => {
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
    this.controls.addEventListener('change', () => { this.dirty = true; });
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
    this.selection = new THREE.BoxHelper(new THREE.Object3D(), 0xc42eaa);
    this.selection.visible = false;
    this.scene.add(this.selection);
    this.raycaster = new THREE.Raycaster();
    this.materials = new Map();
    this.meshes = [];
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
      if (instance.part === 'MSG-CARD') {
        if (!geometry.getAttribute('color')) {
          const colors = new Float32Array(geometry.getAttribute('position').count * 3);
          const cyan = new THREE.Color(state.catalog.colors.cyan.hex);
          const black = new THREE.Color(state.catalog.colors.black.hex);
          const position = geometry.getAttribute('position');
          for (let triangle = 0; triangle < position.count; triangle += 3) {
            const middle = (position.getZ(triangle) + position.getZ(triangle + 1) + position.getZ(triangle + 2)) / 3;
            const color = middle > 2.001 ? black : cyan;
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
    this.content.add(grid);
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(gridSize * 2, gridSize * 2),
      new THREE.ShadowMaterial({ color: 0x526b80, opacity: .17 }),
    );
    floor.position.set(w / 2, d / 2, -.3);
    floor.receiveShadow = true;
    floor.userData.disposable = true;
    this.content.add(floor);
    this.bounds = new THREE.Box3Helper(
      new THREE.Box3(new THREE.Vector3(...model.bounds[0]), new THREE.Vector3(...model.bounds[1])),
      0x2952a6,
    );
    this.bounds.visible = $('#bounds').checked;
    this.bounds.userData.disposable = true;
    this.content.add(this.bounds);
    this.view('iso');
    this.update();
    $('#viewport').dataset.instances = String(this.meshes.length);
    $('#viewport').dataset.model = model.id;
  }

  view(name) {
    if (!state.model) return;
    this.currentView = name;
    const [w, d, h] = state.model.actual_mm;
    const center = new THREE.Vector3(w / 2, d / 2, h * .48);
    const offsets = {
      iso: new THREE.Vector3(.7, -1.8, .85),
      front: new THREE.Vector3(0, -2, 0),
      side: new THREE.Vector3(2, 0, 0),
      top: new THREE.Vector3(0, -.0001, 2),
    };
    this.controls.target.copy(center);
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
    const [w, d, h] = state.model?.actual_mm || [200, 100, 200];
    const expansion = state.explosion * (state.model?.steps.length || 23) * 3;
    const extent = this.currentView === 'top' ? Math.max(d * 1.7, w / (width / height) * 1.35)
      : Math.max(h * 1.28 + expansion, w / (width / height) * 1.45);
    this.camera.left = -extent * width / height / 2;
    this.camera.right = extent * width / height / 2;
    this.camera.top = extent / 2;
    this.camera.bottom = -extent / 2;
    this.camera.updateProjectionMatrix();
    this.dirty = true;
  }

  update() {
    for (const mesh of this.meshes) {
      const item = mesh.userData.instance;
      mesh.visible = item.step <= state.stage;
      mesh.position.fromArray(item.position);
      const offset = explosionOffset(item, state.model, state.catalog.message, state.explosion);
      mesh.position.add(new THREE.Vector3(...offset));
    }
    const selected = this.meshes.find((mesh) => mesh.name === state.selected);
    this.selection.visible = !!selected?.visible;
    if (selected?.visible) this.selection.setFromObject(selected);
    if (this.bounds) this.bounds.visible = $('#bounds').checked && state.explosion === 0;
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
    if (this.dirty) {
      this.renderer.render(this.scene, this.camera);
      this.dirty = false;
    }
  }
}

function updateLinks(model) {
  const id = model.id;
  $('.model-print-link').href = `downloads/${id}/print-kit.zip`;
  $('.model-print-link').innerHTML = `${id}の印刷セット <span>↓</span>`;
  $('.model-guide-link').href = `guide.html?model=${id}`;
  $('#download-model').textContent = `${id} / ${model.name}`;
  const files = ['print-kit.zip', `${id}.FCStd`, `${id}.step`, 'drawings.pdf', 'bom.csv', 'plates.zip'];
  [...$('#download-links').children].forEach((link, index) => { link.href = `downloads/${id}/${files[index]}`; });
  const video = $('#assembly-video');
  video.pause();
  video.poster = `media/${id}-hero.png`;
  video.querySelector('source').src = `media/${id}-assembly.mp4`;
  video.querySelector('track').src = `media/${id}-assembly.vtt`;
  video.load();
  $('#film-model').textContent = id;
  $('#video-download').href = `media/${id}-assembly.mp4`;
  $('#blend-download').href = `downloads/${id}/${id}.blend`;
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
    note.textContent = item.part === 'MSG-CARD' ? '文字のブラックは2.0 mm層後の任意の色替えです。単色でも使えます。'
      : '外形はスタッド込み。形状IDのHはスタッドを除く本体高さです。';
    details.append(note);
    for (const [label, href] of [
      ['STLを保存 ↓', `downloads/${part.stl}`],
      ['寸法図を開く ↗', `drawings/parts/${item.part}.svg`],
      ['この工程の配置図 ↗', `drawings/${state.model.id}/step-${String(item.step).padStart(2, '0')}.svg`],
    ]) {
      const link = document.createElement('a');
      link.href = href;
      link.textContent = label;
      details.append(link);
    }
    $('#part-drawing').src = `drawings/parts/${item.part}.svg`;
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
  for (const button of document.querySelectorAll('[data-model]')) {
    button.classList.toggle('active', button.dataset.model === id);
    button.setAttribute('aria-pressed', String(button.dataset.model === id));
  }
  $('#model-description').textContent = model.description_ja;
  $('#model-dimensions').innerHTML = `${format(model.actual_mm)} <span>mm</span>`;
  $('#part-count').innerHTML = `${model.part_count} <span>点</span>`;
  $('#step-count').innerHTML = `${model.steps.length} <span>工程</span>`;
  $('#target-dimensions').textContent = `目標：${model.target_mm[0]} × ${model.target_mm[1]} × 約${model.target_mm[2]} mm。実寸は上端のスタッドを含みます。`;
  $('#viewer-model').textContent = id;
  $('#viewer-fallback').src = `media/${id}-hero.png`;
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
  const response = await fetch('assets/catalog.json');
  if (!response.ok) throw new Error(`設計データ HTTP ${response.status}`);
  state.catalog = await response.json();
  try {
    viewer = new PortraitViewer();
  } catch (error) {
    showError(`この環境では3D表示を開始できません。完成画像と図面を表示します。${error.message}`);
  }
  document.querySelectorAll('[data-model]').forEach((button) => {
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
    state.explosion = Number(event.target.value) / 100;
    $('#explode-value').textContent = `${event.target.value}%`;
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
