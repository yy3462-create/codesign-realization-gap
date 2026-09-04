// ICOS realization-gap viewer: loads a per-morphology GLB (bodies animated by MuJoCo FK,
// Z-up already baked to Y-up) and the matching terrain, with orbit/drag controls.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const ENVS = ['flat', 'rubble', 'ice', 'stones'];
const ENV_LABEL = { flat: 'Flat ground', rubble: 'Rubble · 30 mm', ice: 'Ice · μ 0.05–0.2', stones: 'Stepping stones' };
const $ = (s) => document.querySelector(s);
const EMBED = window.__EMBED || null;
// index.html loads us as viewer.js?v=<stamp>; pass the same stamp to everything we fetch, so a
// browser can never pair a cached viewer.js with a newer models/index.json (or the reverse).
const V = new URL(import.meta.url).searchParams.get('v');
const bust = (p) => V ? `${p}${p.includes('?') ? '&' : '?'}v=${V}` : p;
const getJSON = async (p) => (EMBED && EMBED[p]) ? EMBED[p] : (await fetch(bust(p))).json();
const assetURL = (p) => (EMBED && EMBED[p]) ? EMBED[p] : bust(p);

// ---------------------------------------------------------------- scene
const viewport = $('#viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
viewport.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.02, 200);
camera.position.set(0.9, 0.55, 1.1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.minDistance = 0.25; controls.maxDistance = 25; controls.maxPolarAngle = Math.PI * 0.49;
controls.target.set(0, 0.1, 0);

const hemi = new THREE.HemisphereLight(0xdfe7f2, 0x2a2f36, 0.9);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(2.5, 4, 1.5); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 0.1; sun.shadow.camera.far = 20;
sun.shadow.camera.left = sun.shadow.camera.bottom = -2.2;
sun.shadow.camera.right = sun.shadow.camera.top = 2.2;
sun.shadow.bias = -0.0005;
scene.add(sun); scene.add(sun.target);
const fill = new THREE.DirectionalLight(0x9fb6d0, 0.5); fill.position.set(-3, 2, -2); scene.add(fill);

function themeDark() {
  const t = document.documentElement.getAttribute('data-theme');
  if (t) return t === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}
function applyTheme() {
  const dark = themeDark();
  const bg = new THREE.Color(dark ? 0x0a0d11 : 0x0f1216);
  scene.background = bg;
  scene.fog = new THREE.Fog(bg, 6, 30);
}
applyTheme();
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);

// ---------------------------------------------------------------- terrain
const terrainCache = {};
let terrainGroup = null;
const GROUND_MAT = {
  flat: () => new THREE.MeshStandardMaterial({ color: 0x3b434d, roughness: 0.95, metalness: 0.0 }),
  ice: () => new THREE.MeshStandardMaterial({ color: 0x4f7ea8, roughness: 0.3, metalness: 0.05 }),
  rubble: () => new THREE.MeshStandardMaterial({ color: 0x7d7468, roughness: 1.0, metalness: 0.0, flatShading: true, side: THREE.DoubleSide }),
  stones: () => new THREE.MeshStandardMaterial({ color: 0x8a8d94, roughness: 0.95, metalness: 0.0, flatShading: true, side: THREE.DoubleSide }),
};

async function loadTerrain(kind) {
  if (terrainCache[kind]) return terrainCache[kind];
  terrainCache[kind] = await getJSON(`models/terrain_${kind}.json`);
  return terrainCache[kind];
}

// heightfield -> "stepped" mesh: one flat quad per cell plus vertical walls where neighbours differ.
// hf is row-major z[ix][iy] (MuJoCo x, y); glTF/three: x -> x, y -> -z, z -> y.
function stepMesh(t, bbox, material) {
  const { n, hs, origin } = t;
  const z = (ix, iy) => t.z_mm[ix * n + iy] / 1000;
  const ix0 = Math.max(0, Math.floor((bbox.xmin - origin) / hs)), ix1 = Math.min(n - 1, Math.ceil((bbox.xmax - origin) / hs));
  const iy0 = Math.max(0, Math.floor((bbox.ymin - origin) / hs)), iy1 = Math.min(n - 1, Math.ceil((bbox.ymax - origin) / hs));
  const pos = [], nor = [];
  const quad = (a, b, c, d, nx, ny, nz) => { // two triangles, CCW as seen from the normal
    pos.push(...a, ...b, ...c, ...a, ...c, ...d);
    for (let k = 0; k < 6; k++) nor.push(nx, ny, nz);
  };
  const X = (ix) => origin + ix * hs, Y = (iy) => origin + iy * hs;
  for (let ix = ix0; ix <= ix1; ix++) for (let iy = iy0; iy <= iy1; iy++) {
    const h = z(ix, iy), x0 = X(ix), x1 = X(ix + 1), y0 = Y(iy), y1 = Y(iy + 1);
    // top (three coords: x, h, -y); order chosen so the normal points +y
    quad([x0, h, -y0], [x0, h, -y1], [x1, h, -y1], [x1, h, -y0], 0, 1, 0);
    // walls to +x and +y neighbours
    if (ix < n - 1) { const h2 = z(ix + 1, iy); if (Math.abs(h2 - h) > 0.0015) {
      const lo = Math.min(h, h2), hi = Math.max(h, h2);
      if (h > h2) quad([x1, hi, -y0], [x1, hi, -y1], [x1, lo, -y1], [x1, lo, -y0], 1, 0, 0);
      else quad([x1, hi, -y1], [x1, hi, -y0], [x1, lo, -y0], [x1, lo, -y1], -1, 0, 0);
    } }
    if (iy < n - 1) { const h2 = z(ix, iy + 1); if (Math.abs(h2 - h) > 0.0015) {
      const lo = Math.min(h, h2), hi = Math.max(h, h2);
      if (h > h2) quad([x0, hi, -y1], [x1, hi, -y1], [x1, lo, -y1], [x0, lo, -y1], 0, 0, -1);
      else quad([x1, hi, -y1], [x0, hi, -y1], [x0, lo, -y1], [x1, lo, -y1], 0, 0, 1);
    } }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  const m = new THREE.Mesh(g, material); m.receiveShadow = true; m.castShadow = false;
  return m;
}

function flatGround(kind) {
  const g = new THREE.Group();
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), GROUND_MAT[kind]());
  plane.rotation.x = -Math.PI / 2; plane.position.y = 0; plane.receiveShadow = true;
  g.add(plane);
  const grid = new THREE.GridHelper(80, 80, 0x5a6470, kind === 'ice' ? 0x86a7c4 : 0x3f4650);
  grid.material.opacity = 0.35; grid.material.transparent = true; grid.position.y = 0.002;
  g.add(grid);
  return g;
}

async function setTerrain(kind, pathXY) {
  if (terrainGroup) { scene.remove(terrainGroup); terrainGroup.traverse((o) => { if (o.geometry) o.geometry.dispose(); }); }
  terrainGroup = new THREE.Group();
  if (kind === 'rubble' || kind === 'stones') {
    const t = await loadTerrain(kind);
    let xmin = 1e9, xmax = -1e9, ymin = 1e9, ymax = -1e9;
    for (const [x, y] of pathXY) { xmin = Math.min(xmin, x); xmax = Math.max(xmax, x); ymin = Math.min(ymin, y); ymax = Math.max(ymax, y); }
    const m = 6.0;
    terrainGroup.add(stepMesh(t, { xmin: xmin - m, xmax: xmax + m, ymin: ymin - m, ymax: ymax + m }, GROUND_MAT[kind]()));
    // the fallback plane below the field (z = -0.5 for stones, hidden under rubble)
    const base = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: 0x1d2229, roughness: 1 }));
    base.rotation.x = -Math.PI / 2; base.position.y = kind === 'stones' ? -0.5 : 0.0; base.receiveShadow = true;
    terrainGroup.add(base);
  } else {
    terrainGroup.add(flatGround(kind));
  }
  scene.add(terrainGroup);
}

// ---------------------------------------------------------------- robot + animation
const loader = new GLTFLoader();
const tmp = new THREE.Vector3(), prev = new THREE.Vector3();
let robot = null, mixer = null, action = null, baseNode = null, meta = null, clipLen = 0;
let pathLine = null, startMarker = null;
const state = { morph: null, space: 'abstract', env: 'flat', playing: true, speed: 1, follow: true };
const index = await getJSON('models/index.json');
const results = await getJSON('data/results.json');
const byId = Object.fromEntries(results.rows.map((r) => [r.id, r]));

async function loadRobot(morph, space) {
  const entry = index.morphologies.find((m) => m.id === morph);
  const sp = entry.spaces[space];
  $('#loading').hidden = false;
  const [gltf, m] = await Promise.all([
    loader.loadAsync(assetURL(`models/${sp.glb}`)),
    getJSON(`models/${sp.meta}`),
  ]);
  if (robot) { scene.remove(robot); mixer = null; action = null; }
  robot = gltf.scene; meta = m;
  robot.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  baseNode = robot.getObjectByName('body');
  scene.add(robot);
  mixer = new THREE.AnimationMixer(robot);
  robot.userData.clips = gltf.animations;
  $('#loading').hidden = true;
  return entry;
}

function groundHeight(kind, x, y) {
  const t = terrainCache[kind];
  if (!t) return 0.0;
  const ix = Math.min(t.n - 1, Math.max(0, Math.floor((x - t.origin) / t.hs)));
  const iy = Math.min(t.n - 1, Math.max(0, Math.floor((y - t.origin) / t.hs)));
  return t.z_mm[ix * t.n + iy] / 1000;
}

function setPath(pathXY, kind) {
  if (pathLine) { scene.remove(pathLine); scene.remove(startMarker); }
  const lift = (kind === 'rubble' || kind === 'stones') ? 0.006 : 0.004;
  const pts = pathXY.map(([x, y]) => new THREE.Vector3(x, groundHeight(kind, x, y) + lift, -y));
  const g = new THREE.BufferGeometry().setFromPoints(pts);
  pathLine = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xe8a23a, transparent: true, opacity: 0.85 }));
  scene.add(pathLine);
  startMarker = new THREE.Mesh(new THREE.RingGeometry(0.16, 0.19, 48), new THREE.MeshBasicMaterial({ color: 0xe8a23a, side: THREE.DoubleSide, transparent: true, opacity: 0.6 }));
  startMarker.rotation.x = -Math.PI / 2; startMarker.position.set(pts[0].x, pts[0].y, pts[0].z);
  scene.add(startMarker);
}

function selectClip(env) {
  const clip = robot.userData.clips.find((c) => c.name === env);
  if (action) action.stop();
  if (!clip) { action = null; clipLen = 0; return false; }
  action = mixer.clipAction(clip);
  action.setLoop(THREE.LoopRepeat); action.play();
  clipLen = clip.duration;
  return true;
}

async function show(morph, space, env, keepCamera = false) {
  state.morph = morph; state.space = space;
  const entry = await loadRobot(morph, space);
  const available = Object.keys(entry.spaces[space].clips);
  const hasEnv = available.includes(env);
  state.env = hasEnv ? env : (available[0] || env);
  const ok = selectClip(state.env);
  const clipMeta = meta.clips[state.env];
  const pathXY = clipMeta ? clipMeta.path_xy : [[0, 0]];
  await setTerrain(state.env, pathXY);
  if (clipMeta) setPath(pathXY, state.env); else if (pathLine) { scene.remove(pathLine); scene.remove(startMarker); pathLine = null; }
  if (mixer) mixer.update(0);          // pose the robot at t = 0 of the new clip before anchoring
  updateUI(entry, available, ok);
  if (!keepCamera) resetCamera(); else anchorCamera();
  if (!ok) { $('#ro-time').textContent = '—'; $('#ro-disp').textContent = '—'; scrub.value = 0; }
}

// move the camera with the robot while keeping the current orbit offset (env / space switches)
function anchorCamera() {
  const p = new THREE.Vector3(); (baseNode || robot).getWorldPosition(p);
  const off = camera.position.clone().sub(controls.target);
  controls.target.copy(p); camera.position.copy(p).add(off); prev.copy(p);
  controls.update();
}

function resetCamera() {
  const p = new THREE.Vector3(); (baseNode || robot).getWorldPosition(p);
  controls.target.copy(p);
  camera.position.copy(p).add(new THREE.Vector3(0.95, 0.5, 1.05));
  prev.copy(p);
  controls.update();
}

// ---------------------------------------------------------------- UI
const morphSel = $('#morph');
for (const m of index.morphologies) {
  const o = document.createElement('option');
  o.value = m.id; o.textContent = `${m.label} · ${m.species} · ${m.legs} legs`;
  morphSel.appendChild(o);
}
morphSel.addEventListener('change', () => show(morphSel.value, state.space, state.env));
$('#prev').addEventListener('click', () => step(-1));
$('#next').addEventListener('click', () => step(1));
function step(d) {
  const ids = index.morphologies.map((m) => m.id);
  const i = (ids.indexOf(state.morph) + d + ids.length) % ids.length;
  morphSel.value = ids[i]; show(ids[i], state.space, state.env);
}
document.querySelectorAll('.controls [data-space]').forEach((b) => b.addEventListener('click', () => {
  if (b.disabled) return;          // fabricable-space clips are pending the current hardware build
  document.querySelectorAll('.controls [data-space]').forEach((x) => x.setAttribute('aria-pressed', x === b));
  show(state.morph, b.dataset.space, state.env, true);
}));
document.querySelectorAll('[data-env]').forEach((b) => b.addEventListener('click', () => {
  if (b.disabled) return;
  show(state.morph, state.space, b.dataset.env, true);
}));
$('#play').addEventListener('click', () => { state.playing = !state.playing; $('#play').textContent = state.playing ? 'Pause' : 'Play'; $('#play').setAttribute('aria-pressed', state.playing); });
$('#follow').addEventListener('click', () => { state.follow = !state.follow; $('#follow').setAttribute('aria-pressed', state.follow); });
$('#reset').addEventListener('click', resetCamera);
document.querySelectorAll('[data-speed]').forEach((b) => b.addEventListener('click', () => {
  state.speed = parseFloat(b.dataset.speed);
  document.querySelectorAll('[data-speed]').forEach((x) => x.setAttribute('aria-pressed', x === b));
}));
const scrub = $('#scrub');
let scrubbing = false;
scrub.addEventListener('input', () => { scrubbing = true; if (action) { action.time = parseFloat(scrub.value) * clipLen; mixer.update(0); } });
scrub.addEventListener('change', () => { scrubbing = false; });

function updateUI(entry, available, ok) {
  const row = byId[entry.id];
  $('#hud-name').textContent = `${entry.label} · ${entry.species}`;
  const src = meta.clips[state.env] ? meta.clips[state.env].npz.replace('_traj.npz', '') : '—';
  $('#hud-tag').innerHTML = `${state.space === 'fabricable' ? '<b>fabricable</b>' : '<b>abstract</b>'} space · ${ENV_LABEL[state.env] || state.env} · ${entry.legs} legs`;
  $('#hud-tag').title = `training run ${src}`;
  document.querySelectorAll('.card[data-morph]').forEach((c) => c.classList.toggle('active', c.dataset.morph === entry.id));
  document.querySelectorAll('.half[data-morph]').forEach((h) => h.classList.toggle('active', h.dataset.morph === entry.id && h.dataset.space === state.space));
  document.querySelectorAll('[data-env]').forEach((b) => {
    b.disabled = !available.includes(b.dataset.env);
    b.setAttribute('aria-pressed', b.dataset.env === state.env);
    b.title = b.disabled ? 'No trajectory recorded yet for this environment' : '';
  });
  const finalD = meta.clips[state.env] ? meta.clips[state.env].displacement_final_m.toFixed(2) + ' m' : '—';
  const roFinal = $('#ro-final'); if (roFinal) roFinal.textContent = finalD;
  $('#ro-paper').textContent = row ? `${row[state.space === 'fabricable' ? (state.env === 'flat' ? 'flat' : state.env) : 'abstract'].toFixed(2)} m` : '—';
  $('#viewer-note').textContent = ok ? '' : 'No trajectory recorded for this environment yet; showing the rest pose.';
  if (state.env === 'stones') $('#viewer-note').textContent += ' Stepping-stone layout is illustrative (same stone size and gaps; the training run’s random offsets are not recoverable).';
}

// ---------------------------------------------------------------- loop
const clock = new THREE.Clock();
function resize() {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewport); resize();

function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  if (mixer && action && state.playing && !scrubbing) mixer.update(dt * state.speed);
  if (action && clipLen > 0) {
    const t = action.time % clipLen;
    if (!scrubbing) scrub.value = (t / clipLen).toFixed(4);
    $('#ro-time').textContent = t.toFixed(2) + ' s';
    const cm = meta.clips[state.env];
    if (cm) { const i = Math.min(cm.displacement_curve.length - 1, Math.floor(t / cm.seconds * cm.displacement_curve.length)); $('#ro-disp').textContent = cm.displacement_curve[i].toFixed(2) + ' m'; }
  }
  if (baseNode) {
    baseNode.getWorldPosition(tmp);
    if (state.follow) {           // keep the orbit offset, teleport with the robot (also across loop wraps)
      const delta = tmp.clone().sub(controls.target);
      controls.target.add(delta); camera.position.add(delta);
    }
    prev.copy(tmp);
    sun.position.set(tmp.x + 2.5, 4, tmp.z + 1.5); sun.target.position.copy(tmp);
  }
  controls.update();
  renderer.render(scene, camera);
}
const first = new URLSearchParams(location.search);
morphSel.value = first.get('m') || 'quadruped';
await show(morphSel.value, 'abstract', first.get('env') || 'flat');
animate();
window.__viewer = { camera, controls, get base() { return baseNode; }, state, get prev() { return prev; }, V3: THREE.Vector3 };

// gallery cards -> viewer: each half of a card is one (morphology, design space)
document.querySelectorAll('.half[data-morph]').forEach((h) => h.addEventListener('click', () => {
  const space = (h.dataset.space && index.morphologies.find((m) => m.id === h.dataset.morph).spaces[h.dataset.space]) ? h.dataset.space : state.space;
  document.querySelectorAll('.controls [data-space]').forEach((x) => x.setAttribute('aria-pressed', x.dataset.space === space));
  morphSel.value = h.dataset.morph; show(h.dataset.morph, space, state.env);
  document.querySelector('.viewer-shell').scrollIntoView({ behavior: 'smooth', block: 'start' });
}));
