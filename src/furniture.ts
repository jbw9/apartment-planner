import * as THREE from 'three';
import { IN, Rect, fmt, overlap, wallRects, fixtureRects, swingRects, roomAt } from './plan';

export type Shape = 'box' | 'sofa' | 'bed' | 'table' | 'chair' | 'shelf' | 'cabinet' | 'rug' | 'tv';

export interface Item {
  id: string;
  name: string;
  shape: Shape;
  w: number; // inches, left-right when facing the piece
  d: number; // inches, front-back
  h: number; // inches
  u: number; // centre
  v: number;
  rot: number; // degrees, 0 = front faces the entry (+v)
  color: string;
  photo?: string; // data URL shown on the front face
}

export const PRESETS: { name: string; shape: Shape; w: number; d: number; h: number; color: string }[] = [
  { name: 'Sofa (3-seat)', shape: 'sofa', w: 84, d: 36, h: 33, color: '#8b8f8a' },
  { name: 'Loveseat', shape: 'sofa', w: 60, d: 35, h: 33, color: '#8b8f8a' },
  { name: 'Armchair', shape: 'sofa', w: 32, d: 34, h: 32, color: '#9a8468' },
  { name: 'Queen bed', shape: 'bed', w: 62, d: 84, h: 24, color: '#d9d4c8' },
  { name: 'Full bed', shape: 'bed', w: 56, d: 79, h: 24, color: '#d9d4c8' },
  { name: 'King bed', shape: 'bed', w: 78, d: 84, h: 24, color: '#d9d4c8' },
  { name: 'Nightstand', shape: 'cabinet', w: 20, d: 16, h: 24, color: '#a98a62' },
  { name: 'Dresser', shape: 'cabinet', w: 60, d: 18, h: 32, color: '#a98a62' },
  { name: 'Desk', shape: 'table', w: 48, d: 24, h: 30, color: '#b79a72' },
  { name: 'Dining table', shape: 'table', w: 48, d: 30, h: 30, color: '#8a6a48' },
  { name: 'Coffee table', shape: 'table', w: 44, d: 22, h: 16, color: '#6f5236' },
  { name: 'Chair', shape: 'chair', w: 18, d: 20, h: 33, color: '#3a3a3c' },
  { name: 'Bookshelf', shape: 'shelf', w: 31, d: 12, h: 72, color: '#e8e4dc' },
  { name: 'TV stand', shape: 'cabinet', w: 60, d: 16, h: 20, color: '#55504a' },
  { name: 'TV 55"', shape: 'tv', w: 49, d: 3, h: 30, color: '#111113' },
  { name: 'Rug 5×8', shape: 'rug', w: 96, d: 60, h: 0.5, color: '#b9b2a4' },
];

const KEY = 'apartment.layout.v1';
const texLoader = new THREE.TextureLoader();

function shadowTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d')!;
  g.fillStyle = '#fff';
  g.fillRect(0, 0, 128, 128);
  g.filter = 'blur(9px)';
  g.fillStyle = '#000';
  g.fillRect(22, 22, 84, 84);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Builds the 3D model for an item, centred on its footprint, sitting on y = 0, front toward +z. */
function buildModel(it: Item, shadowTex: THREE.Texture): THREE.Group {
  const g = new THREE.Group();
  const W = it.w * IN, D = it.d * IN, H = it.h * IN;
  const main = new THREE.MeshStandardMaterial({ color: it.color, roughness: 0.85 });
  const dark = new THREE.MeshStandardMaterial({ color: new THREE.Color(it.color).multiplyScalar(0.55), roughness: 0.7 });
  const add = (w: number, h: number, d: number, x: number, y: number, z: number, m: THREE.Material = main) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    mesh.position.set(x, y + h / 2, z);
    g.add(mesh);
    return mesh;
  };
  const i = (n: number) => n * IN;
  switch (it.shape) {
    case 'sofa': {
      const arm = Math.min(i(8), W * 0.14), back = Math.min(i(9), D * 0.28), seat = H * 0.52, leg = i(3);
      add(W, seat - leg - i(5), D, 0, leg, 0);
      add(W - 2 * arm, i(5), D - back, 0, seat - i(5), back / 2, new THREE.MeshStandardMaterial({ color: new THREE.Color(it.color).multiplyScalar(1.08), roughness: 0.95 }));
      add(W, H - leg, back, 0, leg, -D / 2 + back / 2);
      add(arm, H * 0.72 - leg, D, -W / 2 + arm / 2, leg, 0);
      add(arm, H * 0.72 - leg, D, W / 2 - arm / 2, leg, 0);
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) add(i(2), leg, i(2), sx * (W / 2 - i(2.5)), 0, sz * (D / 2 - i(2.5)), dark);
      break;
    }
    case 'bed': {
      const frame = new THREE.MeshStandardMaterial({ color: '#7d6a55', roughness: 0.8 });
      const linen = new THREE.MeshStandardMaterial({ color: '#f1efe9', roughness: 0.95 });
      add(W, H * 0.45, D, 0, i(2), 0, frame);
      add(W - i(1), H * 0.5, D - i(3), 0, H * 0.48, i(0.5), linen);
      add(W - i(0.6), H * 0.3, D * 0.62, 0, H * 0.72, D * 0.19 - i(0.2));
      add(W, H + i(22), i(2.5), 0, 0, -D / 2 + i(1.25), frame);
      const pw = W > i(50) ? (W - i(10)) / 2 : W - i(10);
      for (const px of W > i(50) ? [-1, 1] : [0]) add(pw, i(5), i(16), px * (pw / 2 + i(1.5)), H * 0.98, -D / 2 + i(13), linen);
      break;
    }
    case 'table': {
      const top = i(1.5), leg = Math.min(i(2.2), W * 0.08);
      add(W, top, D, 0, H - top, 0);
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) add(leg, H - top, leg, sx * (W / 2 - leg), 0, sz * (D / 2 - leg), dark);
      break;
    }
    case 'chair': {
      const seat = Math.min(i(18), H * 0.55), leg = i(1.4);
      add(W, i(2), D, 0, seat - i(2), 0);
      add(W, H - seat, i(1.6), 0, seat, -D / 2 + i(0.8));
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) add(leg, seat - i(2), leg, sx * (W / 2 - leg), 0, sz * (D / 2 - leg), dark);
      break;
    }
    case 'shelf': {
      const t = i(0.75);
      add(t, H, D, -W / 2 + t / 2, 0, 0); add(t, H, D, W / 2 - t / 2, 0, 0);
      add(W - 2 * t, H, i(0.3), 0, 0, -D / 2 + i(0.15), dark);
      const n = Math.max(2, Math.round(it.h / 14));
      for (let k = 0; k <= n; k++) add(W - 2 * t, t, D, 0, (k * (H - t)) / n, 0);
      break;
    }
    case 'cabinet': {
      const leg = it.h > 18 ? i(3) : i(1);
      add(W, H - leg, D - i(0.75), 0, leg, -i(0.375));
      const rows = Math.max(1, Math.round((it.h - 3) / 9)), cols = it.w > 40 ? 2 : 1;
      const fw = (W - i(0.5)) / cols, fh = (H - leg - i(0.5)) / rows;
      const frontMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(it.color).multiplyScalar(1.06), roughness: 0.7 });
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        add(fw - i(0.25), fh - i(0.25), i(0.75), -W / 2 + i(0.25) + fw * (c + 0.5), leg + i(0.25) + fh * r, D / 2 - i(0.375), frontMat);
        add(i(4), i(0.4), i(0.6), -W / 2 + i(0.25) + fw * (c + 0.5), leg + fh * (r + 0.7), D / 2 + i(0.3), dark);
      }
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) add(i(1.5), leg, i(1.5), sx * (W / 2 - i(1.5)), 0, sz * (D / 2 - i(1.5)), dark);
      break;
    }
    case 'rug':
      add(W, Math.max(H, i(0.3)), D, 0, 0, 0, new THREE.MeshStandardMaterial({ color: it.color, roughness: 1 }));
      break;
    case 'tv': {
      const scr = new THREE.MeshStandardMaterial({ color: '#050506', roughness: 0.15 });
      add(W, H, i(1.2), 0, 0, 0, scr);
      break;
    }
    default:
      add(W, H, D, 0, 0, 0);
  }
  if (it.photo) {
    const tex = texLoader.load(it.photo);
    tex.colorSpace = THREE.SRGBColorSpace;
    const card = new THREE.Mesh(new THREE.PlaneGeometry(W, H), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.8 }));
    card.position.set(0, H / 2, D / 2 + 0.002);
    g.add(card);
  }
  if (it.shape !== 'rug') {
    const sh = new THREE.Mesh(
      new THREE.PlaneGeometry(W * 1.5, D * 1.5),
      new THREE.MeshBasicMaterial({ map: shadowTex, blending: THREE.MultiplyBlending, transparent: true, depthWrite: false, premultipliedAlpha: true, toneMapped: false }),
    );
    sh.rotation.x = -Math.PI / 2;
    sh.position.y = 0.012;
    sh.renderOrder = 2;
    sh.userData.shadow = true;
    g.add(sh);
  }
  return g;
}

export interface EditorHost {
  scene: THREE.Scene;
  camera: () => THREE.Camera;
  dom: HTMLElement;
  panel: HTMLElement;
  labels: HTMLElement;
  lockCamera: (locked: boolean) => void;
  envFor: (room: string | null) => THREE.Texture | null;
  changed: () => void;
}

export class Editor {
  items: Item[] = [];
  selected: Item | null = null;
  private groups = new Map<string, THREE.Group>();
  private shadowTex = shadowTexture();
  private ray = new THREE.Raycaster();
  private drag: { du: number; dv: number; moved: boolean } | null = null;
  private outline = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x4da3ff, depthTest: false }));
  private dims = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.9 }));
  private dimLabels: { el: HTMLElement; pos: THREE.Vector3 }[] = [];

  constructor(private host: EditorHost) {
    this.outline.renderOrder = 10;
    this.dims.renderOrder = 10;
    this.outline.visible = this.dims.visible = false;
    this.outline.frustumCulled = this.dims.frustumCulled = false;
    host.scene.add(this.outline, this.dims);
    this.load();
    this.bind();
    this.renderPanel();
  }

  // ------------------------------------------------------------ state
  private load() {
    try {
      this.items = JSON.parse(localStorage.getItem(KEY) || '[]');
    } catch {
      this.items = [];
    }
    for (const it of this.items) this.rebuild(it);
  }
  private save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(this.items));
    } catch {
      /* storage full or unavailable: layout stays in memory */
    }
    this.host.changed();
  }
  refreshEnv() {
    for (const it of this.items) this.applyEnv(it);
  }
  private applyEnv(it: Item) {
    const env = this.host.envFor(roomAt(it.u, it.v));
    this.groups.get(it.id)?.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (m && 'envMap' in m && !o.userData.shadow) { m.envMap = env; m.envMapIntensity = 1; m.needsUpdate = true; }
    });
  }
  private rebuild(it: Item) {
    const old = this.groups.get(it.id);
    if (old) this.host.scene.remove(old);
    const g = buildModel(it, this.shadowTex);
    g.userData.item = it;
    this.groups.set(it.id, g);
    this.host.scene.add(g);
    this.place(it);
  }
  private place(it: Item) {
    const g = this.groups.get(it.id)!;
    g.position.set(it.u * IN, it.shape === 'rug' ? 0.002 : 0, it.v * IN);
    g.rotation.y = (-it.rot * Math.PI) / 180;
    this.applyEnv(it);
    if (this.selected === it) this.updateOverlay();
  }

  add(p: Partial<Item> & { name: string; shape: Shape; w: number; d: number; h: number; color: string }, at?: { u: number; v: number }) {
    const it: Item = { id: Math.random().toString(36).slice(2, 9), rot: 0, u: at?.u ?? 189, v: at?.v ?? 70, ...p };
    this.items.push(it);
    this.rebuild(it);
    this.select(it);
    this.save();
    return it;
  }
  remove(it: Item) {
    this.host.scene.remove(this.groups.get(it.id)!);
    this.groups.delete(it.id);
    this.items = this.items.filter((x) => x !== it);
    if (this.selected === it) this.select(null);
    this.save();
  }
  select(it: Item | null) {
    this.selected = it;
    this.updateOverlay();
    this.renderPanel();
  }

  // ------------------------------------------------------------ geometry helpers
  footprint(it: Item, u = it.u, v = it.v): Rect {
    const a = (it.rot * Math.PI) / 180;
    const c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
    const hw = (it.w * c + it.d * s) / 2, hd = (it.w * s + it.d * c) / 2;
    return { u0: u - hw, u1: u + hw, v0: v - hd, v1: v + hd };
  }
  status(it: Item): 'ok' | 'blocked' | 'door' {
    const f = this.footprint(it);
    if (wallRects.some((w) => overlap(f, w))) return 'blocked';
    if (it.shape !== 'rug') {
      if (fixtureRects.some((x) => overlap(f, x))) return 'blocked';
      if (this.items.some((o) => o !== it && o.shape !== 'rug' && overlap(f, this.footprint(o)))) return 'blocked';
      if (swingRects.some((x) => overlap(f, x))) return 'door';
    }
    return 'ok';
  }
  private snap(it: Item, u: number, v: number) {
    if (it.rot % 90 !== 0) return { u, v };
    const T = 3;
    const f = this.footprint(it, u, v);
    const obstacles: Rect[] = [...wallRects, ...fixtureRects];
    let du = 0, dv = 0, bu = T, bv = T;
    for (const o of obstacles) {
      if (f.v0 < o.v1 && f.v1 > o.v0) {
        for (const g of [o.u1 - f.u0, o.u0 - f.u1]) if (Math.abs(g) < bu) { bu = Math.abs(g); du = g; }
      }
      if (f.u0 < o.u1 && f.u1 > o.u0) {
        for (const g of [o.v1 - f.v0, o.v0 - f.v1]) if (Math.abs(g) < bv) { bv = Math.abs(g); dv = g; }
      }
    }
    return { u: u + du, v: v + dv };
  }
  /** Clear distance from each side of the footprint to the nearest wall / fixture / other furniture. */
  private clearances(it: Item) {
    const f = this.footprint(it);
    const obs: Rect[] = [...wallRects, ...fixtureRects, ...this.items.filter((o) => o !== it && o.shape !== 'rug').map((o) => this.footprint(o))];
    const res = { left: Infinity, right: Infinity, back: Infinity, front: Infinity };
    for (const o of obs) {
      if (f.v0 < o.v1 - 0.1 && f.v1 > o.v0 + 0.1) {
        if (o.u1 <= f.u0 + 0.1) res.left = Math.min(res.left, f.u0 - o.u1);
        if (o.u0 >= f.u1 - 0.1) res.right = Math.min(res.right, o.u0 - f.u1);
      }
      if (f.u0 < o.u1 - 0.1 && f.u1 > o.u0 + 0.1) {
        if (o.v1 <= f.v0 + 0.1) res.back = Math.min(res.back, f.v0 - o.v1);
        if (o.v0 >= f.v1 - 0.1) res.front = Math.min(res.front, o.v0 - f.v1);
      }
    }
    return { f, res };
  }

  private updateOverlay() {
    const it = this.selected;
    this.host.labels.querySelectorAll('.dim').forEach((e) => e.remove());
    this.dimLabels = [];
    this.outline.visible = this.dims.visible = !!it;
    if (!it) return;
    const st = this.status(it);
    (this.outline.material as THREE.LineBasicMaterial).color.set(st === 'ok' ? 0x4da3ff : st === 'door' ? 0xffb020 : 0xff4d4d);
    const box = new THREE.BoxGeometry(it.w * IN, Math.max(it.h, 1) * IN, it.d * IN);
    this.outline.geometry.dispose();
    this.outline.geometry = new THREE.EdgesGeometry(box);
    this.outline.position.set(it.u * IN, (Math.max(it.h, 1) * IN) / 2, it.v * IN);
    this.outline.rotation.y = (-it.rot * Math.PI) / 180;
    const { f, res } = this.clearances(it);
    const pts: number[] = [];
    const y = 0.03, cu = (f.u0 + f.u1) / 2, cv = (f.v0 + f.v1) / 2;
    const seg = (u0: number, v0: number, u1: number, v1: number, len: number) => {
      if (!isFinite(len) || len < 0.5) return;
      pts.push(u0 * IN, y, v0 * IN, u1 * IN, y, v1 * IN);
      const el = document.createElement('div');
      el.className = 'dim';
      el.textContent = fmt(len);
      this.host.labels.appendChild(el);
      this.dimLabels.push({ el, pos: new THREE.Vector3(((u0 + u1) / 2) * IN, y, ((v0 + v1) / 2) * IN) });
    };
    seg(f.u0, cv, f.u0 - res.left, cv, res.left);
    seg(f.u1, cv, f.u1 + res.right, cv, res.right);
    seg(cu, f.v0, cu, f.v0 - res.back, res.back);
    seg(cu, f.v1, cu, f.v1 + res.front, res.front);
    this.dims.geometry.dispose();
    this.dims.geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  }

  /** Call every frame: keeps the clearance labels glued to their 3D positions. */
  frame(w: number, h: number) {
    const cam = this.host.camera();
    for (const { el, pos } of this.dimLabels) {
      const p = pos.clone().project(cam);
      const vis = p.z < 1 && p.z > -1;
      el.style.display = vis ? '' : 'none';
      el.style.transform = `translate(-50%,-50%) translate(${((p.x + 1) / 2) * w}px,${((1 - p.y) / 2) * h}px)`;
    }
  }

  // ------------------------------------------------------------ input
  private pick(e: PointerEvent): { item: Item | null; floor: THREE.Vector3 | null } {
    const r = this.host.dom.getBoundingClientRect();
    const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(ndc, this.host.camera());
    const hits = this.ray.intersectObjects([...this.groups.values()], true).filter((h) => !h.object.userData.shadow);
    let item: Item | null = null;
    if (hits.length) {
      let o: THREE.Object3D | null = hits[0].object;
      while (o && !o.userData.item) o = o.parent;
      item = o?.userData.item ?? null;
    }
    const floor = new THREE.Vector3();
    const ok = this.ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), floor);
    return { item, floor: ok ? floor : null };
  }
  private bind() {
    const dom = this.host.dom;
    dom.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const { item, floor } = this.pick(e);
      if (item && floor) {
        if (this.selected !== item) this.select(item);
        this.drag = { du: item.u - floor.x / IN, dv: item.v - floor.z / IN, moved: false };
        this.host.lockCamera(true);
        dom.setPointerCapture(e.pointerId);
        e.stopImmediatePropagation();
      }
    }, true);
    dom.addEventListener('pointermove', (e) => {
      if (!this.drag || !this.selected) return;
      const { floor } = this.pick(e);
      if (!floor) return;
      const it = this.selected;
      let u = floor.x / IN + this.drag.du, v = floor.z / IN + this.drag.dv;
      if (!e.altKey) ({ u, v } = this.snap(it, u, v));
      it.u = Math.round(u * 4) / 4;
      it.v = Math.round(v * 4) / 4;
      this.drag.moved = true;
      this.place(it);
      this.syncFields();
      e.stopImmediatePropagation();
    }, true);
    const end = () => {
      if (!this.drag) return;
      this.drag = null;
      this.host.lockCamera(false);
      this.save();
    };
    dom.addEventListener('pointerup', end, true);
    dom.addEventListener('pointercancel', end, true);
    window.addEventListener('keydown', (e) => {
      const it = this.selected;
      if (!it || (e.target as HTMLElement).closest('input,textarea,select')) return;
      const k = e.key.toLowerCase();
      if (k === 'r') it.rot = (it.rot + 90) % 360;
      else if (k === '[') it.rot = (it.rot + 345) % 360;
      else if (k === ']') it.rot = (it.rot + 15) % 360;
      else if (k === 'delete' || k === 'backspace') return this.remove(it);
      else if (k === 'escape') return this.select(null);
      else return;
      this.place(it);
      this.syncFields();
      this.save();
    });
  }

  // ------------------------------------------------------------ panel UI
  private syncFields() {
    const it = this.selected;
    if (!it) return;
    const set = (id: string, val: string) => {
      const el = this.host.panel.querySelector<HTMLInputElement>('#' + id);
      if (el && document.activeElement !== el) el.value = val;
    };
    set('f-rot', String(it.rot));
    const st = this.status(it);
    const el = this.host.panel.querySelector('#f-status');
    if (el) {
      el.className = 'status ' + st;
      el.textContent = st === 'ok' ? 'Fits here' : st === 'door' ? 'In a door swing' : 'Overlaps a wall, fixture or furniture';
    }
    const room = this.host.panel.querySelector('#f-room');
    if (room) room.textContent = roomAt(it.u, it.v) ?? 'outside';
  }

  renderPanel() {
    const p = this.host.panel;
    const it = this.selected;
    const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
    p.innerHTML = `
      <h2>Furniture</h2>
      <div class="row"><select id="preset">${PRESETS.map((x, i) => `<option value="${i}">${x.name} — ${x.w}×${x.d}×${x.h}"</option>`).join('')}</select>
      <button id="add-preset" class="primary">Add</button></div>
      <details id="custom"><summary>Custom piece from dimensions / photo</summary>
        <label>Name<input id="c-name" value="My piece"></label>
        <div class="grid3"><label>Width"<input id="c-w" type="number" value="72" min="1"></label>
        <label>Depth"<input id="c-d" type="number" value="34" min="1"></label>
        <label>Height"<input id="c-h" type="number" value="32" min="0.5"></label></div>
        <div class="row"><label class="grow">Shape<select id="c-shape">${['box', 'sofa', 'bed', 'table', 'chair', 'shelf', 'cabinet', 'rug', 'tv'].map((s) => `<option>${s}</option>`).join('')}</select></label>
        <label>Color<input id="c-color" type="color" value="#9a8f80"></label></div>
        <label>Photo (shown on the front)<input id="c-photo" type="file" accept="image/*"></label>
        <button id="add-custom" class="primary wide">Add custom piece</button>
      </details>
      ${it ? `
      <div class="sel">
        <h3>${esc(it.name)}</h3>
        <div class="status" id="f-status"></div>
        <div class="grid3"><label>Width"<input id="f-w" type="number" value="${it.w}"></label>
        <label>Depth"<input id="f-d" type="number" value="${it.d}"></label>
        <label>Height"<input id="f-h" type="number" value="${it.h}"></label></div>
        <div class="row"><label class="grow">Rotation°<input id="f-rot" type="number" step="15" value="${it.rot}"></label>
        <label>Color<input id="f-color" type="color" value="${it.color}"></label></div>
        <div class="meta">In: <b id="f-room"></b> · drag to move · <kbd>R</kbd> rotate · <kbd>Del</kbd> remove</div>
        <div class="row"><button id="f-dup">Duplicate</button><button id="f-del" class="danger">Remove</button></div>
      </div>` : `<p class="hint">Click a piece to select it, then drag it across the floor. It snaps to walls; hold <kbd>Alt</kbd> to place freely.</p>`}
      <div class="list">${this.items.map((x) => `<button class="item${x === it ? ' on' : ''}" data-id="${x.id}"><span>${esc(x.name)}</span><em>${x.w}×${x.d}×${x.h}"</em></button>`).join('')}</div>
      <div class="row foot"><button id="exp">Export</button><button id="imp">Import</button><button id="clr" class="danger">Clear all</button></div>`;
    const $ = <T extends HTMLElement>(s: string) => p.querySelector<T>(s)!;
    const num = (s: string, d: number) => Math.max(0.25, parseFloat($<HTMLInputElement>(s).value) || d);
    $('#add-preset').onclick = () => this.add({ ...PRESETS[+$<HTMLSelectElement>('#preset').value] });
    $('#add-custom').onclick = async () => {
      const file = $<HTMLInputElement>('#c-photo').files?.[0];
      const photo = file ? await downscale(file) : undefined;
      this.add({ name: $<HTMLInputElement>('#c-name').value || 'Custom', shape: $<HTMLSelectElement>('#c-shape').value as Shape,
        w: num('#c-w', 36), d: num('#c-d', 24), h: num('#c-h', 30), color: $<HTMLInputElement>('#c-color').value, photo });
    };
    p.querySelectorAll<HTMLElement>('.item').forEach((b) => (b.onclick = () => this.select(this.items.find((x) => x.id === b.dataset.id) ?? null)));
    $('#exp').onclick = () => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([JSON.stringify(this.items, null, 1)], { type: 'application/json' }));
      a.download = 'apartment-layout.json';
      a.click();
    };
    $('#imp').onclick = () => {
      const inp = document.createElement('input');
      inp.type = 'file';
      inp.accept = 'application/json';
      inp.onchange = async () => {
        const data = JSON.parse(await inp.files![0].text());
        if (!Array.isArray(data)) return;
        for (const x of [...this.items]) this.remove(x);
        this.items = data;
        for (const x of this.items) this.rebuild(x);
        this.save();
        this.renderPanel();
      };
      inp.click();
    };
    $('#clr').onclick = () => { for (const x of [...this.items]) this.remove(x); this.renderPanel(); };
    if (it) {
      const upd = (rebuild: boolean) => {
        it.w = num('#f-w', it.w); it.d = num('#f-d', it.d); it.h = num('#f-h', it.h);
        it.rot = ((parseFloat($<HTMLInputElement>('#f-rot').value) || 0) % 360 + 360) % 360;
        it.color = $<HTMLInputElement>('#f-color').value;
        if (rebuild) this.rebuild(it); else this.place(it);
        this.syncFields();
        this.save();
      };
      for (const id of ['#f-w', '#f-d', '#f-h', '#f-color']) $(id).onchange = () => upd(true);
      $('#f-rot').onchange = () => upd(false);
      $('#f-del').onclick = () => this.remove(it);
      $('#f-dup').onclick = () => this.add({ ...it, id: undefined } as never, { u: it.u + 12, v: it.v + 12 });
      this.syncFields();
    }
  }
}

function downscale(file: File): Promise<string> {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(1, 1024 / Math.max(img.width, img.height));
      const c = document.createElement('canvas');
      c.width = Math.round(img.width * s);
      c.height = Math.round(img.height * s);
      c.getContext('2d')!.drawImage(img, 0, 0, c.width, c.height);
      res(c.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = rej;
    img.src = URL.createObjectURL(file);
  });
}
