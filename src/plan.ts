// Floor-plan data exported by blender/build.py. Everything here is in inches (u across, v window->entry).
export const IN = 0.0254;

export type Rect = { u0: number; u1: number; v0: number; v1: number };
type Box6 = [number, number, number, number, number, number];

export interface Plan {
  ceiling: number;
  walls: Box6[];
  openings: Record<string, Box6>;
  passable: string[];
  rooms: Record<string, [number, number, number, number]>;
  fixtures: Record<string, [number, number, number, number, number]>;
  doorSwings: { name: string; hinge: [number, number]; w: number; closed: [number, number]; open: [number, number] }[];
  lights: [number, number, number, number, string][];
  sunDir: [number, number, number];
}

export let plan: Plan;
export let wallRects: Rect[] = [];
export let passRects: Rect[] = [];
export let fixtureRects: (Rect & { name: string; h: number })[] = [];
export let swingRects: (Rect & { name: string })[] = [];

const rect = (b: number[]): Rect => ({ u0: b[0], u1: b[1], v0: b[2], v1: b[3] });

export async function loadPlan() {
  plan = await (await fetch('model/plan.json')).json();
  wallRects = plan.walls.map(rect);
  passRects = plan.passable.map((n) => rect(plan.openings[n]));
  fixtureRects = Object.entries(plan.fixtures).map(([name, f]) => ({ ...rect(f), name, h: f[4] }));
  swingRects = plan.doorSwings.map((d) => {
    const [hu, hv] = d.hinge;
    const us = [hu, hu + d.closed[0] * d.w, hu + d.open[0] * d.w];
    const vs = [hv, hv + d.closed[1] * d.w, hv + d.open[1] * d.w];
    return { name: d.name, u0: Math.min(...us), u1: Math.max(...us), v0: Math.min(...vs), v1: Math.max(...vs) };
  });
}

export const overlap = (a: Rect, b: Rect, eps = 0.05) =>
  a.u0 < b.u1 - eps && a.u1 > b.u0 + eps && a.v0 < b.v1 - eps && a.v1 > b.v0 + eps;

/** Can a person (circle of radius r) stand at u,v? */
export function walkable(u: number, v: number, r = 8): boolean {
  for (const w of wallRects) {
    if (u > w.u0 - r && u < w.u1 + r && v > w.v0 - r && v < w.v1 + r) {
      // inside a wall's inflated footprint: only fine if we are in a doorway
      const inDoor = passRects.some((p) => {
        const alongV = p.u1 - p.u0 < p.v1 - p.v0;
        return alongV
          ? v > p.v0 + r * 0.6 && v < p.v1 - r * 0.6 && u > p.u0 - r - 1 && u < p.u1 + r + 1
          : u > p.u0 + r * 0.6 && u < p.u1 - r * 0.6 && v > p.v0 - r - 1 && v < p.v1 + r + 1;
      });
      if (!inDoor) return false;
    }
  }
  for (const f of fixtureRects) if (u > f.u0 - r && u < f.u1 + r && v > f.v0 - r && v < f.v1 + r) return false;
  return roomAt(u, v) !== null || passRects.some((p) => u >= p.u0 && u <= p.u1 && v >= p.v0 && v <= p.v1);
}

export function roomAt(u: number, v: number): string | null {
  for (const [name, r] of Object.entries(plan.rooms)) if (u >= r[0] && u <= r[1] && v >= r[2] && v <= r[3]) return name;
  return null;
}

export function fmt(inches: number): string {
  const t = Math.round(Math.abs(inches));
  const ft = Math.floor(t / 12);
  return (inches < 0 ? '-' : '') + (ft ? `${ft}' ${t % 12}"` : `${t}"`);
}
