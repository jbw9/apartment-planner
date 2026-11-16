import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { EXRLoader } from 'three/addons/loaders/EXRLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { IN, plan, loadPlan, walkable, roomAt, wallRects, fixtureRects, fmt } from './plan';
import { Editor } from './furniture';
import './style.css';

const $ = <T extends HTMLElement>(s: string) => document.querySelector<T>(s)!;
const canvas = $<HTMLCanvasElement>('#view');
const QUERY = new URLSearchParams(location.search);
const DEBUG = QUERY.has('debug');
// every unit is a folder holding plan.json, the model and its lightmaps; unit 487 is the one shipped with the app
const BASE = (QUERY.get('unit') ?? 'model').replace(/\/?$/, '/');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: DEBUG });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.localClippingEnabled = false;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1b1c20);
const walkCam = new THREE.PerspectiveCamera(72, 1, 0.05, 400);
const orbitCam = new THREE.PerspectiveCamera(38, 1, 0.1, 600);
const orbit = new OrbitControls(orbitCam, canvas);
orbit.enableDamping = true;
orbit.maxPolarAngle = Math.PI * 0.49;
orbit.minDistance = 2;
orbit.maxDistance = 40;

type Mode = 'walk' | 'dollhouse';
let mode: Mode = 'walk';
const light = { day: 1, lamp: 1, exposure: 1 };
// calibration of the two baked passes against the walkthrough video (bright neutral daylight, warm pools from the cans)
const tune = { exposure: 1.35, dayGain: 3.0, lampGain: 0.55, lampTint: new THREE.Vector3(0.92, 1.0, 1.16), backdrop: 2.0, backdropRot: 1.7 };
let CUT = 87 * IN; // dollhouse section height
const clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), CUT);
const bounds = { u0: 0, u1: 0, v0: 0, v1: 0, cu: 0, cv: 0 }; // of the walls, in inches

// ------------------------------------------------------------------ textures & materials
const tl = new THREE.TextureLoader();
function tex(file: string, repeatU: number, repeatV: number, srgb = true, turned = false) {
  const t = tl.load('tex/' + file);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeatU, repeatV);
  if (turned) t.rotation = Math.PI / 2;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const m = (inches: number) => 1 / (inches * IN);

/** Lightmapped surfaces already contain baked diffuse light, so they must not also receive diffuse IBL. */
function bakedOnly(mat: THREE.MeshStandardMaterial) {
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    prev.call(mat, sh, r);
    sh.fragmentShader = sh.fragmentShader.replace(
      '#include <lights_fragment_maps>',
      THREE.ShaderChunk.lights_fragment_maps.replace('iblIrradiance += getIBLIrradiance( geometryNormal );', ''),
    );
  };
  return mat;
}

const std = (p: THREE.MeshStandardMaterialParameters) => new THREE.MeshStandardMaterial(p);

// Planar reflection for the floor: the vinyl plank picks up the window glare at grazing angles, like the real one.
const floorRefl = new Reflector(new THREE.PlaneGeometry(60, 60), { textureWidth: 1024, textureHeight: 1024, clipBias: 0.003 });
floorRefl.rotation.x = -Math.PI / 2;
floorRefl.renderOrder = -10;
floorRefl.getRenderTarget().texture.type = THREE.HalfFloatType;
Object.assign(floorRefl.material, { colorWrite: false, depthWrite: false, depthTest: false });
const reflUniforms = {
  tReflect: { value: floorRefl.getRenderTarget().texture },
  uReflMatrix: (floorRefl.material as THREE.ShaderMaterial).uniforms.textureMatrix,
  uReflStrength: { value: 1.0 },
};
function reflectiveFloor(mat: THREE.MeshStandardMaterial) {
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, reflUniforms);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nuniform mat4 uReflMatrix; varying vec4 vRefl;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvRefl = uReflMatrix * modelMatrix * vec4(transformed, 1.0);');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform sampler2D tReflect; uniform float uReflStrength; varying vec4 vRefl;')
      .replace('#include <opaque_fragment>', `{
        vec2 ruv = vRefl.xy / vRefl.w + normal.xy * 0.004;
        float spread = 0.0016 + roughnessFactor * 0.006;
        vec3 rc = vec3(0.0);
        for (int i = -3; i <= 3; i++) for (int j = -3; j <= 3; j++) rc += texture2D(tReflect, ruv + vec2(float(i), float(j) * 1.8) * spread).rgb;
        float cosT = saturate(dot(normalize(vViewPosition), normal));
        float fr = 0.035 + 0.965 * pow(1.0 - cosT, 4.0);
        outgoingLight += min(rc / 49.0, vec3(6.0)) * fr * uReflStrength * (1.0 - roughnessFactor * 0.55);
      }
      #include <opaque_fragment>`);
  };
  return mat;
}
const wallN = () => tex('wall_normal.jpg', m(10), m(10), false);
const MATS: Record<string, () => THREE.Material> = {
  wall_white: () => std({ color: 0xe9e6df, roughness: 0.92, normalMap: wallN(), normalScale: new THREE.Vector2(0.25, 0.25) }),
  wall_accent: () => std({ color: 0xbdb9ae, roughness: 0.92, normalMap: wallN(), normalScale: new THREE.Vector2(0.25, 0.25) }),
  ceiling_white: () => std({ color: 0xecebe7, roughness: 0.96 }),
  floor_lvp: () => reflectiveFloor(std({
    map: tex('floor_color.jpg', m(112), m(144)), roughnessMap: tex('floor_rough.jpg', m(112), m(144), false),
    normalMap: tex('floor_normal.jpg', m(112), m(144), false), normalScale: new THREE.Vector2(0.5, 0.5), roughness: 1, envMapIntensity: 0.25,
  })),
  trim_white: () => std({ color: 0xf0efeb, roughness: 0.45 }),
  door_white: () => std({ color: 0xf0efeb, roughness: 0.4 }),
  cab_dark: () => std({ color: 0x7a7a7c, roughness: 0.5 }),
  cab_wood: () => std({ map: tex('cab_wood.jpg', m(24), m(24)), roughness: 0.55 }),
  quartz: () => std({ color: 0xf2f1ee, roughness: 0.22 }),
  tile_marble: () => std({ map: tex('tile_marble.jpg', m(48), m(24)), roughness: 0.18 }),
  stainless: () => std({ color: 0xb4b6b8, metalness: 1, roughness: 0.34, roughnessMap: tex('brushed.jpg', m(8), m(8), false) }),
  chrome: () => std({ color: 0xdfe1e4, metalness: 1, roughness: 0.07 }),
  nickel: () => std({ color: 0xb9b6b0, metalness: 1, roughness: 0.32 }),
  black_glass: () => std({ color: 0x08080a, roughness: 0.05 }),
  appliance_dark: () => std({ color: 0x2a2a2c, roughness: 0.4 }),
  appliance_white: () => std({ color: 0xf1f1f1, roughness: 0.3 }),
  tub_white: () => std({ color: 0xf5f5f4, roughness: 0.12 }),
  porcelain: () => std({ color: 0xf7f7f5, roughness: 0.07 }),
  deck: () => std({ color: 0xb9b9b6, roughness: 0.85 }),
  rail_black: () => std({ color: 0x1b1b1d, roughness: 0.5 }),
  heater_grille: () => std({ color: 0x77777a, roughness: 0.6 }),
  exterior: () => new THREE.MeshBasicMaterial({ color: 0x3b3e44 }),
  cap: () => new THREE.MeshBasicMaterial({ color: 0x2b2d31 }),
  wire_white: () => std({ color: 0xf0f0ee, roughness: 0.5 }),
  mirror: () => std({ color: 0xffffff, metalness: 1, roughness: 0.02 }),
  light_emit: () => new THREE.MeshBasicMaterial({ color: 0xffffff }),
  led_emit: () => new THREE.MeshBasicMaterial({ color: 0xffffff }),
  glass: () => new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0, metalness: 0, transparent: true, opacity: 0.1, depthWrite: false, envMapIntensity: 1.2 }),
  glass_rail: () => new THREE.MeshPhysicalMaterial({ color: 0xdfeeee, roughness: 0, metalness: 0, transparent: true, opacity: 0.16, depthWrite: false }),
};
// Finishes of generated units: plan.json names each material's kind (the kit's vocabulary), colour and plank direction.
type Kit = (c: THREE.Color, turned: boolean) => THREE.Material;
const flat = (roughness: number, metalness = 0): Kit => (c) => std({ color: c, roughness, metalness });
const basic: Kit = (c) => new THREE.MeshBasicMaterial({ color: c });
const KIT: Record<string, Kit> = {
  wall_paint: (c) => std({ color: c, roughness: 0.92, normalMap: wallN(), normalScale: new THREE.Vector2(0.25, 0.25) }),
  ceiling_paint: flat(0.96), trim_paint: flat(0.45), door_paint: flat(0.4),
  floor_wood: (c, t) => reflectiveFloor(std({
    color: c, map: tex('floor_color.jpg', m(112), m(144), true, t), roughnessMap: tex('floor_rough.jpg', m(112), m(144), false, t),
    normalMap: tex('floor_normal.jpg', m(112), m(144), false, t), normalScale: new THREE.Vector2(0.5, 0.5), roughness: 1, envMapIntensity: 0.25,
  })),
  floor_tile: flat(0.3), carpet: flat(1), rug: flat(1),
  wall_tile: (c) => std({ color: c, map: tex('subway.jpg', m(12), m(6)), roughness: 0.14 }),
  stone_tile: (c) => std({ color: c, map: tex('tile_marble.jpg', m(48), m(24)), roughness: 0.18 }),
  ceiling_tile: (c) => std({ color: c, map: tex('ceiling_tile.jpg', m(24), m(48)), roughness: 0.95 }),
  cabinet_paint: flat(0.5), cabinet_wood: (c) => std({ color: c, map: tex('cab_wood.jpg', m(24), m(24)), roughness: 0.55 }),
  counter: flat(0.22),
  stainless: (c) => std({ color: c.multiplyScalar(1.2), metalness: 1, roughness: 0.34, roughnessMap: tex('brushed.jpg', m(8), m(8), false) }),
  black_metal: flat(0.45, 0.3), chrome: flat(0.07, 1), nickel: flat(0.32, 1), brass: flat(0.3, 1),
  black_glass: flat(0.05), appliance_white: flat(0.3), appliance_black: flat(0.4), porcelain: flat(0.07), mirror: flat(0.02, 1),
  plastic: flat(0.35), vinyl: flat(0.4), blind: flat(0.5), fabric: flat(0.95), leather: flat(0.5), wood: flat(0.55), plant: flat(0.6),
  concrete: flat(0.9), frosted_glass: flat(0.6), screen: flat(0.08),
  glass: () => MATS.glass(), emit_warm: basic, emit_cool: basic, emit_shade: basic, emit_display: basic, outside: basic,
};
function material(name: string): THREE.Material {
  const k = plan.materials?.[name];
  if (!k || !KIT[k.key]) return (MATS[name] ?? (() => std({ color: 0xff00ff })))();
  return KIT[k.key](new THREE.Color().setRGB(k.rgb[0] / 255, k.rgb[1] / 255, k.rgb[2] / 255, THREE.SRGBColorSpace), k.plank === 'v');
}
const kind = (name: string) => plan.materials?.[name]?.key ?? name;
const emitters: { mat: THREE.MeshBasicMaterial; base: THREE.Color; gain: number }[] = [];
const outsides: { mat: THREE.MeshBasicMaterial; base: THREE.Color }[] = [];
const guessed: { mat: THREE.MeshStandardMaterial; base: THREE.Color }[] = [];
let showGuess = false;

// ------------------------------------------------------------------ baked light mixing (daylight + fixtures)
class LightMix {
  rt: THREE.WebGLRenderTarget;
  private quad: THREE.Mesh;
  private cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private sc = new THREE.Scene();
  constructor(day: THREE.Texture, lamp: THREE.Texture) {
    const size = (day.image as { width: number }).width;
    this.rt = new THREE.WebGLRenderTarget(size, size, { type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false });
    this.rt.texture.channel = 1;
    this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
      uniforms: { tDay: { value: day }, tLamp: { value: lamp }, uDay: { value: 1 }, uLamp: { value: 1 }, uTint: { value: tune.lampTint } },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
      fragmentShader: `uniform sampler2D tDay, tLamp; uniform float uDay, uLamp; uniform vec3 uTint; varying vec2 vUv;
        void main(){ vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
          gl_FragColor = vec4(max(texture2D(tDay, uv).rgb, 0.0) * uDay + max(texture2D(tLamp, uv).rgb, 0.0) * uTint * uLamp, 1.0); }`,
      depthTest: false, depthWrite: false, toneMapped: false,
    }));
    this.sc.add(this.quad);
  }
  update() {
    const u = (this.quad.material as THREE.ShaderMaterial).uniforms;
    u.uDay.value = light.day * tune.dayGain;
    u.uLamp.value = light.lamp * tune.lampGain;
    const prev = renderer.getRenderTarget();
    renderer.setRenderTarget(this.rt);
    renderer.render(this.sc, this.cam);
    renderer.setRenderTarget(prev);
  }
}
const mixes: LightMix[] = [];

// ------------------------------------------------------------------ outdoors
const sky = new THREE.Mesh(new THREE.SphereGeometry(300, 24, 12), new THREE.MeshBasicMaterial({ side: THREE.BackSide, color: 0xffffff }));
const backdropMat = new THREE.MeshBasicMaterial({ side: THREE.BackSide, color: 0xffffff });
let backdropCyl: THREE.Mesh;
const ground = new THREE.Mesh(new THREE.CircleGeometry(300, 32), new THREE.MeshBasicMaterial({ color: 0x4a5040 }));
function buildOutdoors() {
  scene.add(sky);
  const t = tl.load('tex/backdrop.jpg');
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  backdropMat.map = t;
  const R = 34, H = 42;
  const cyl = (backdropCyl = new THREE.Mesh(new THREE.CylinderGeometry(R, R, H, 64, 1, true), backdropMat));
  cyl.position.set(bounds.cu * IN, 1.5 + H * 0.5 - H * 0.36, (bounds.v0 + 28) * IN);
  cyl.rotation.y = Math.PI * 0.15;
  scene.add(cyl);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -11;
  scene.add(ground);
}

// ------------------------------------------------------------------ dollhouse section caps + room labels
const caps = new THREE.Group();
function buildCaps() {
  const mat = new THREE.MeshBasicMaterial({ color: 0x24262a });
  for (const w of wallRects) {
    const g = new THREE.Mesh(new THREE.PlaneGeometry((w.u1 - w.u0) * IN, (w.v1 - w.v0) * IN), mat);
    g.rotation.x = -Math.PI / 2;
    g.position.set(((w.u0 + w.u1) / 2) * IN, CUT - 0.004, ((w.v0 + w.v1) / 2) * IN);
    caps.add(g);
  }
  caps.visible = false;
  scene.add(caps);
}
const roomLabels: { el: HTMLElement; pos: THREE.Vector3 }[] = [];
function buildRoomLabels() {
  const merged: Record<string, [number, number, number, number]> = { ...plan.rooms };
  for (const [name, r] of Object.entries(merged)) {
    if (/closet|laundry|#/i.test(name)) continue;
    const el = document.createElement('div');
    el.className = 'room';
    el.innerHTML = `<b>${name}</b><span>${fmt(r[1] - r[0])} × ${fmt(r[3] - r[2])}</span>`;
    $('#labels').appendChild(el);
    roomLabels.push({ el, pos: new THREE.Vector3(((r[0] + r[1]) / 2) * IN, 0.05, ((r[2] + r[3]) / 2) * IN) });
  }
}

// ------------------------------------------------------------------ reflection probes (one per room)
const probes = new Map<string, THREE.Texture>();
const pmrem = new THREE.PMREMGenerator(renderer);
const cubeRT = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType });
const cubeCam = new THREE.CubeCamera(0.05, 400, cubeRT);
let editor: Editor;
const mirrors: Reflector[] = [];
function captureProbes() {
  const prevClip = renderer.clippingPlanes;
  renderer.clippingPlanes = [];
  const capsVis = caps.visible;
  caps.visible = false;
  scene.environment = null;
  // reflectors re-target the renderer mid-draw, which would corrupt a cube face
  const reflVis = floorRefl.visible;
  floorRefl.visible = false;
  for (const mr of mirrors) mr.visible = false;
  const strength = reflUniforms.uReflStrength.value;
  reflUniforms.uReflStrength.value = 0;
  for (const [name, r] of Object.entries(plan.rooms)) {
    cubeCam.position.set(((r[0] + r[1]) / 2) * IN, 1.45, ((r[2] + r[3]) / 2) * IN);
    cubeCam.update(renderer, scene);
    probes.get(name)?.dispose();
    probes.set(name, pmrem.fromCubemap(cubeRT.texture).texture);
  }
  scene.environment = probes.get(mode === 'walk' ? walkRoom() : mainRoom) ?? null;
  floorRefl.visible = reflVis;
  for (const mr of mirrors) mr.visible = true;
  reflUniforms.uReflStrength.value = strength;
  renderer.clippingPlanes = prevClip;
  caps.visible = capsVis;
  editor?.refreshEnv();
}

let probeTimer = 0;
function applyLight() {
  for (const mx of mixes) mx.update();
  for (const e of emitters) e.mat.color.copy(e.base).multiplyScalar(0.05 + e.gain * light.lamp);
  for (const o of outsides) o.mat.color.copy(o.base).multiplyScalar(0.03 + 1.6 * light.day);
  for (const g of guessed) g.mat.color.copy(g.base).lerp(GUESS_TINT, showGuess ? 0.6 : 0);
  const d = light.day;
  (sky.material as THREE.MeshBasicMaterial).color.setRGB(0.06 + 1.9 * d, 0.07 + 2.05 * d, 0.1 + 2.3 * d);
  backdropMat.color.setScalar(0.03 + tune.backdrop * d);
  backdropCyl.rotation.y = tune.backdropRot;
  (ground.material as THREE.MeshBasicMaterial).color.setRGB(0.02 + 0.25 * d, 0.02 + 0.28 * d, 0.02 + 0.2 * d);
  renderer.toneMappingExposure = light.exposure * tune.exposure;
  clearTimeout(probeTimer);
  probeTimer = window.setTimeout(captureProbes, probes.size ? 120 : 0);
}

// ------------------------------------------------------------------ load
const GUESS_TINT = new THREE.Color(0xff8a3d);
let mainRoom = 'Living';

/** A real planar reflection in front of each mirror the unit lists (the two largest; each one redraws the scene). */
function buildMirrors() {
  const list = plan.mirrors ?? [[30.65, 30.65, 310.5, 346.5, 42, 80]];
  for (const [u0, u1, v0, v1, z0, z1] of [...list].sort((a, b) => (b[5] - b[4]) * (b[1] - b[0] + b[3] - b[2]) - (a[5] - a[4]) * (a[1] - a[0] + a[3] - a[2])).slice(0, 2)) {
    const alongV = v1 - v0 > u1 - u0, cu = (u0 + u1) / 2, cv = (v0 + v1) / 2;
    // it faces whichever side has a room in front of it
    const sign = roomAt(cu + (alongV ? 8 : 0), cv + (alongV ? 0 : 8)) ? 1 : -1;
    const mr = new Reflector(new THREE.PlaneGeometry((alongV ? v1 - v0 : u1 - u0) * IN, (z1 - z0) * IN), { textureWidth: 1024, textureHeight: 1024, color: 0xb8bcbc, clipBias: 0.003 });
    mr.rotation.y = alongV ? (sign * Math.PI) / 2 : sign > 0 ? 0 : Math.PI;
    mr.position.set((alongV ? (sign > 0 ? u1 : u0) + sign * 0.15 : cu) * IN, ((z0 + z1) / 2) * IN, (alongV ? cv : (sign > 0 ? v1 : v0) + sign * 0.15) * IN);
    scene.add(mr);
    mirrors.push(mr);
  }
}

async function load() {
  const status = $('#loading span');
  await loadPlan(BASE);
  Object.assign(tune, plan.tune ?? {});
  Object.assign(bounds, plan.bounds ?? {
    u0: Math.min(...wallRects.map((w) => w.u0)) - 6, u1: Math.max(...wallRects.map((w) => w.u1)) + 6,
    v0: Math.min(...wallRects.map((w) => w.v0)) - 6, v1: Math.max(...wallRects.map((w) => w.v1)) + 6,
  });
  bounds.cu = (bounds.u0 + bounds.u1) / 2;
  bounds.cv = (bounds.v0 + bounds.v1) / 2;
  CUT = clip.constant = Math.min(87, plan.ceiling - 20) * IN;
  floorRefl.position.set(bounds.cu * IN, 0, bounds.cv * IN);
  // start in the middle of the biggest room, looking toward the middle of the unit
  const [big, br] = Object.entries(plan.rooms).sort((a, b) => (b[1][1] - b[1][0]) * (b[1][3] - b[1][2]) - (a[1][1] - a[1][0]) * (a[1][3] - a[1][2]))[0];
  mainRoom = big;
  plan.start ??= [(br[0] + br[1]) / 2, (br[2] + br[3]) / 2];
  // the middle of a room is often a table or a sofa: step outward until there is floor to stand on
  for (let r = 0; r < 120 && !walkable(plan.start[0], plan.start[1]); r += 6) {
    for (let k = 0; k < 12; k++) {
      const u = (br[0] + br[1]) / 2 + r * Math.cos(k * Math.PI / 6), v = (br[2] + br[3]) / 2 + r * Math.sin(k * Math.PI / 6);
      if (walkable(u, v)) { plan.start = [u, v]; break; }
    }
  }
  walk.u = plan.start[0];
  walk.v = plan.start[1];
  look.yaw = walk.yaw = plan.start[2] ?? Math.atan2(walk.u - bounds.cu, walk.v - bounds.cv);
  if (plan.title) $('#title').textContent = plan.title;
  // the apartments published with the site; a unit opened from a job link is not in the list and keeps its plain title
  fetch('units.json').then((r) => r.json()).then((list: { unit: string; title: string }[]) => {
    const here = BASE.slice(0, -1), sel = $<HTMLSelectElement>('#unit');
    if (!list.some((u) => u.unit === here)) return;
    for (const u of list) sel.add(new Option(u.title, u.unit, false, u.unit === here));
    sel.hidden = false;
    $('#title').hidden = true;
    sel.onchange = () => { location.search = sel.value === 'model' ? '' : '?unit=' + sel.value; };
  }).catch(() => {});
  if (plan.subtitle !== undefined) $('#subtitle').textContent = plan.subtitle;
  if (plan.survey?.scale?.method === 'pixels') $('#subtitle').textContent += ' · sizes estimated from the drawing';
  const exr = new EXRLoader().setDataType(THREE.HalfFloatType);
  const lm = async (n: string) => {
    const t = await exr.loadAsync(`${BASE}lm_${n}.exr`);
    t.minFilter = t.magFilter = THREE.LinearFilter;
    t.generateMipmaps = false;
    return t;
  };
  status.textContent = 'Loading baked lighting…';
  const groups = Object.keys(plan.lightmaps ?? { A: 0, B: 0 });
  const [gltf, ...maps] = await Promise.all([new GLTFLoader().loadAsync(BASE + (plan.model ?? 'apartment.glb')), ...groups.flatMap((g) => [lm(g + '_day'), lm(g + '_lamp')])]);
  const mixOf = new Map(groups.map((g, i) => [g, new LightMix(maps[2 * i], maps[2 * i + 1])]));
  mixes.push(...mixOf.values());
  status.textContent = 'Building scene…';

  const cache = new Map<string, THREE.Material>();
  gltf.scene.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    let root: THREE.Object3D = mesh;
    while (root.parent && root.parent !== gltf.scene) root = root.parent;
    const group = root.name;
    const name = (mesh.material as THREE.Material).name;
    const key = group + '/' + name;
    let mat = cache.get(key);
    if (!mat) {
      mat = material(name);
      mat.name = name;
      // generated units name their lightmapped groups LM_<letter>[_guess]; unit 487 calls them Shell and Fixtures
      const mix = mixOf.get(group.startsWith('LM_') ? group[3] : group.startsWith('Shell') ? 'A' : group.startsWith('Fixtures') ? 'B' : '');
      if (mix && mat instanceof THREE.MeshStandardMaterial) {
        mat.lightMap = mix.rt.texture;
        mat.lightMapIntensity = Math.PI;
        bakedOnly(mat);
        if (group.endsWith('_guess')) guessed.push({ mat, base: mat.color.clone() });
      }
      const k = kind(name);
      if (k === 'light_emit' || k === 'led_emit') {
        emitters.push({ mat: mat as THREE.MeshBasicMaterial, base: new THREE.Color(k === 'led_emit' ? 0xfff2e0 : 0xffdcae), gain: k === 'led_emit' ? 5 : 9 });
      } else if (k === 'emit_warm' || k === 'emit_cool' || k === 'emit_shade') {
        emitters.push({ mat: mat as THREE.MeshBasicMaterial, base: (mat as THREE.MeshBasicMaterial).color.clone(), gain: k === 'emit_shade' ? 1.4 : 7 });
      } else if (k === 'outside') {
        outsides.push({ mat: mat as THREE.MeshBasicMaterial, base: (mat as THREE.MeshBasicMaterial).color.clone() });
      }
      mat.clippingPlanes = null;
      cache.set(key, mat);
    }
    mesh.material = mat;
    if (kind(name) === 'mirror') mesh.visible = false;
    if (kind(name) === 'glass' || name === 'glass_rail') mesh.renderOrder = 5;
  });
  scene.add(gltf.scene);

  buildMirrors();
  if (guessed.length) {
    const b = $('#toggle-guess');
    b.hidden = false;
    b.onclick = () => { showGuess = !showGuess; b.classList.toggle('on', showGuess); applyLight(); };
  }

  scene.add(floorRefl);
  buildOutdoors();
  buildCaps();
  buildRoomLabels();
  editor = new Editor({
    scene, dom: canvas, panel: $('#panel'), labels: $('#labels'),
    camera: () => (mode === 'walk' ? walkCam : orbitCam),
    lockCamera: (l) => { orbit.enabled = !l && mode === 'dollhouse'; dragLook = false; },
    envFor: (room) => probes.get(room ?? mainRoom) ?? probes.get(mainRoom) ?? null,
    changed: () => {},
  });
  applyLight();
  captureProbes();
  THREE.DefaultLoadingManager.onLoad = () => applyLight(); // re-capture reflections once every texture is in
  $('#loading').remove();
  setMode('walk');
  renderer.setAnimationLoop(frame);
  if (DEBUG) Object.assign(window, { app: { scene, renderer, walk, look, light, applyLight, setMode, editor, orbitCam, orbit, frame, tune } });
}

// ------------------------------------------------------------------ walking
const walk = { u: 0, v: 0, yaw: 0, pitch: -0.04, eye: 63 };
const keys = new Set<string>();
let glide: { u: number; v: number } | null = null;
const walkRoom = () => roomAt(walk.u, walk.v) ?? mainRoom;

let dragLook = false;
const look = { yaw: walk.yaw, pitch: walk.pitch };
canvas.addEventListener('pointerdown', (e) => {
  if (mode !== 'walk' || e.button !== 0) return;
  dragLook = true;
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener('pointermove', (e) => {
  if (!dragLook) return;
  look.yaw -= e.movementX * 0.0045;
  look.pitch = THREE.MathUtils.clamp(look.pitch - e.movementY * 0.0045, -1.2, 1.2);
});
for (const ev of ['pointerup', 'pointercancel']) canvas.addEventListener(ev, () => (dragLook = false));
canvas.addEventListener('dblclick', (e) => {
  if (mode !== 'walk') return;
  const r = canvas.getBoundingClientRect();
  const ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), walkCam);
  const p = new THREE.Vector3();
  if (ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), p) && walkable(p.x / IN, p.z / IN)) glide = { u: p.x / IN, v: p.z / IN };
});
window.addEventListener('keydown', (e) => {
  if ((e.target as HTMLElement).closest('input,textarea,select')) return;
  keys.add(e.key.toLowerCase());
  if (e.key.startsWith('Arrow') || e.key === ' ') e.preventDefault();
});
window.addEventListener('keyup', (e) => keys.delete(e.key.toLowerCase()));
window.addEventListener('blur', () => keys.clear());

const vel = { u: 0, v: 0 };
let stride = 0;
function stepWalk(dt: number) {
  const f = (keys.has('w') || keys.has('arrowup') ? 1 : 0) - (keys.has('s') || keys.has('arrowdown') ? 1 : 0);
  const s = (keys.has('d') ? 1 : 0) - (keys.has('a') ? 1 : 0);
  const turn = (keys.has('arrowleft') ? 1 : 0) - (keys.has('arrowright') ? 1 : 0);
  look.yaw += turn * dt * 1.8;
  // the head eases toward where the drag points, so the view glides instead of jerking with every mouse sample
  const ease = 1 - Math.exp(-dt * 20);
  walk.yaw += (look.yaw - walk.yaw) * ease;
  walk.pitch += (look.pitch - walk.pitch) * ease;
  let tu = 0, tv = 0;
  if (f || s) {
    glide = null;
    const sp = (keys.has('shift') ? 110 : 58) / Math.hypot(f, s);
    const sin = Math.sin(walk.yaw), cos = Math.cos(walk.yaw);
    tu = (-sin * f + cos * s) * sp;
    tv = (-cos * f - sin * s) * sp;
  } else if (glide) {
    const gu = glide.u - walk.u, gv = glide.v - walk.v, dist = Math.hypot(gu, gv);
    if (dist < 2) glide = null;
    else { const sp = Math.min(130, dist * 4); tu = (gu / dist) * sp; tv = (gv / dist) * sp; }
  }
  // ease toward the wanted velocity so starts and stops have weight instead of snapping
  const k = 1 - Math.exp(-dt * (tu || tv ? 11 : 8));
  vel.u += (tu - vel.u) * k;
  vel.v += (tv - vel.v) * k;
  const du = vel.u * dt, dv = vel.v * dt;
  if (walkable(walk.u + du, walk.v)) walk.u += du; else { vel.u = 0; glide = null; }
  if (walkable(walk.u, walk.v + dv)) walk.v += dv; else { vel.v = 0; glide = null; }
  const speed = Math.hypot(vel.u, vel.v);
  stride += speed * dt;
  const bob = Math.sin(stride * 0.105) * 0.45 * Math.min(1, speed / 58);
  const fov = 72 + 6 * THREE.MathUtils.smoothstep(speed, 62, 105);
  if (Math.abs(walkCam.fov - fov) > 0.01) { walkCam.fov += (fov - walkCam.fov) * Math.min(1, dt * 8); walkCam.updateProjectionMatrix(); }
  walkCam.position.set(walk.u * IN, (walk.eye + bob) * IN, walk.v * IN);
  walkCam.rotation.set(walk.pitch, walk.yaw, 0, 'YXZ');
}

// ------------------------------------------------------------------ modes
function setMode(next: Mode, top = false) {
  mode = next;
  const doll = mode === 'dollhouse';
  renderer.clippingPlanes = doll ? [clip] : [];
  caps.visible = doll;
  sky.visible = ground.visible = backdropCyl.visible = floorRefl.visible = !doll;
  reflUniforms.uReflStrength.value = doll ? 0 : 1; // the model floats on a plain studio backdrop
  orbit.enabled = doll;
  document.body.dataset.mode = top ? 'top' : mode;
  if (doll) {
    const cx = bounds.cu * IN, cz = bounds.cv * IN;
    orbit.target.set(cx, 0.4, cz);
    if (top) orbitCam.position.set(cx, 21, cz + 0.01);
    else orbitCam.position.set(cx + 9, 13, cz + 12);
    orbit.update();
  }
  document.querySelectorAll<HTMLElement>('#modes button').forEach((b) => b.classList.toggle('on', b.dataset.mode === document.body.dataset.mode));
}

// ------------------------------------------------------------------ minimap
const mini = $<HTMLCanvasElement>('#minimap');
const B = bounds;
function drawMinimap() {
  const dpr = Math.min(devicePixelRatio, 2);
  const W = mini.clientWidth, H = mini.clientHeight;
  if (mini.width !== W * dpr) { mini.width = W * dpr; mini.height = H * dpr; }
  const g = mini.getContext('2d')!;
  const s = Math.min(W / (B.u1 - B.u0), H / (B.v1 - B.v0)) * dpr;
  const ox = (W * dpr - (B.u1 - B.u0) * s) / 2, oy = (H * dpr - (B.v1 - B.v0) * s) / 2;
  const X = (u: number) => ox + (u - B.u0) * s, Y = (v: number) => oy + (v - B.v0) * s;
  g.clearRect(0, 0, mini.width, mini.height);
  g.fillStyle = '#f4f1ea';
  for (const r of Object.values(plan.rooms)) g.fillRect(X(r[0]), Y(r[2]), (r[1] - r[0]) * s, (r[3] - r[2]) * s);
  if (plan.balcony) {
    g.fillStyle = '#e3e6e4';
    g.fillRect(X(plan.balcony[0]), Y(plan.balcony[2]), (plan.balcony[1] - plan.balcony[0]) * s, (plan.balcony[3] - plan.balcony[2]) * s);
  }
  g.fillStyle = '#d5d0c6';
  for (const f of fixtureRects) g.fillRect(X(f.u0), Y(f.v0), (f.u1 - f.u0) * s, (f.v1 - f.v0) * s);
  g.fillStyle = '#2b2d31';
  for (const w of wallRects) g.fillRect(X(w.u0), Y(w.v0), (w.u1 - w.u0) * s, (w.v1 - w.v0) * s);
  for (const [name, o] of Object.entries(plan.openings)) {
    g.fillStyle = (plan.windows ?? ['slider', 'bed_window']).includes(name) ? '#9fd0ea' : '#f4f1ea';
    g.fillRect(X(o[0]), Y(o[2]), (o[1] - o[0]) * s, (o[3] - o[2]) * s);
  }
  g.strokeStyle = '#9a958a';
  g.lineWidth = dpr;
  for (const d of plan.doorSwings) {
    const a0 = Math.atan2(d.closed[1], d.closed[0]), a1 = Math.atan2(d.open[1], d.open[0]);
    let diff = a1 - a0;
    if (diff > Math.PI) diff -= 2 * Math.PI;
    if (diff < -Math.PI) diff += 2 * Math.PI;
    g.beginPath();
    g.arc(X(d.hinge[0]), Y(d.hinge[1]), d.w * s, a0, a0 + diff, diff < 0);
    g.lineTo(X(d.hinge[0]), Y(d.hinge[1]));
    g.stroke();
  }
  for (const it of editor.items) {
    g.save();
    g.translate(X(it.u), Y(it.v));
    g.rotate((it.rot * Math.PI) / 180);
    g.fillStyle = it === editor.selected ? '#4da3ff' : it.shape === 'rug' ? '#cfc8b8' : '#8d8674';
    g.globalAlpha = it.shape === 'rug' ? 0.7 : 0.95;
    g.fillRect((-it.w / 2) * s, (-it.d / 2) * s, it.w * s, it.d * s);
    g.restore();
  }
  if (mode === 'walk') {
    const x = X(walk.u), y = Y(walk.v);
    const a = -walk.yaw - Math.PI / 2;
    const grad = g.createRadialGradient(x, y, 0, x, y, 60 * s);
    grad.addColorStop(0, 'rgba(46,134,255,.45)');
    grad.addColorStop(1, 'rgba(46,134,255,0)');
    g.fillStyle = grad;
    g.beginPath();
    g.moveTo(x, y);
    g.arc(x, y, 60 * s, a - 0.6, a + 0.6);
    g.fill();
    g.fillStyle = '#fff';
    g.beginPath(); g.arc(x, y, 5.5 * dpr, 0, 7); g.fill();
    g.fillStyle = '#1f7bff';
    g.beginPath(); g.arc(x, y, 4 * dpr, 0, 7); g.fill();
  }
  miniXform = { s: s / dpr, ox: ox / dpr, oy: oy / dpr };
}
let miniXform = { s: 1, ox: 0, oy: 0 };
mini.addEventListener('click', (e) => {
  const r = mini.getBoundingClientRect();
  const u = (e.clientX - r.left - miniXform.ox) / miniXform.s + B.u0, v = (e.clientY - r.top - miniXform.oy) / miniXform.s + B.v0;
  if (!walkable(u, v)) return;
  walk.u = u; walk.v = v; glide = null;
  if (mode !== 'walk') setMode('walk');
});

// ------------------------------------------------------------------ frame
const clock = new THREE.Clock();
let lastRoom = '';
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) {
    renderer.setSize(w, h, false);
    for (const c of [walkCam, orbitCam]) { c.aspect = w / h; c.updateProjectionMatrix(); }
  }
  let cam: THREE.PerspectiveCamera;
  if (mode === 'walk') {
    stepWalk(dt);
    cam = walkCam;
    const room = walkRoom();
    if (room !== lastRoom) { lastRoom = room; scene.environment = probes.get(room) ?? scene.environment; $('#where').textContent = room.split('#')[0]; }
  } else {
    orbit.update();
    cam = orbitCam;
    if (lastRoom !== '*') { lastRoom = '*'; scene.environment = probes.get(mainRoom) ?? null; $('#where').textContent = 'Dollhouse'; }
  }
  renderer.render(scene, cam);
  editor.frame(w, h);
  for (const { el, pos } of roomLabels) {
    const p = pos.clone().project(cam);
    el.style.display = mode === 'dollhouse' && p.z < 1 ? '' : 'none';
    el.style.transform = `translate(-50%,-50%) translate(${((p.x + 1) / 2) * w}px,${((1 - p.y) / 2) * h}px)`;
  }
  drawMinimap();
}

// ------------------------------------------------------------------ UI wiring
document.querySelectorAll<HTMLElement>('#modes button').forEach((b) => (b.onclick = () => setMode(b.dataset.mode === 'walk' ? 'walk' : 'dollhouse', b.dataset.mode === 'top')));
for (const k of ['day', 'lamp', 'exposure'] as const) {
  $<HTMLInputElement>('#l-' + k).oninput = (e) => { light[k] = +(e.target as HTMLInputElement).value; applyLight(); };
}
document.querySelectorAll<HTMLElement>('#presets button').forEach((b) => (b.onclick = () => {
  const [d, l, x] = b.dataset.v!.split(',').map(Number);
  Object.assign(light, { day: d, lamp: l, exposure: x });
  for (const k of ['day', 'lamp', 'exposure'] as const) $<HTMLInputElement>('#l-' + k).value = String(light[k]);
  applyLight();
}));
$('#toggle-panel').onclick = () => document.body.classList.toggle('panel-closed');

load().catch((e) => { $('#loading span').textContent = 'Failed to load: ' + e.message; console.error(e); });
