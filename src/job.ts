import './site.css';
import { putAll } from './put';

type Gap = { id: string; room: string; plan_px: [number, number, number, number]; ask: string; why: string };
type Job = {
  status: 'uploading' | 'surveying' | 'asking' | 'building' | 'done' | 'failed';
  title: string; furniture: boolean; gaps?: Gap[]; plan_url?: string; stills?: string[];
  metrics?: Record<string, { minutes: number; usd: number; status?: string }>; error?: string;
};

const id = new URLSearchParams(location.search).get('id') ?? '';
const root = document.querySelector<HTMLElement>('#job')!;
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
const pretty = (s: string) => s.replace(/^room_/, '').replace(/_/g, ' ');
let shown = '';

function steps(job: Job) {
  const m = job.metrics ?? {}, rooms = Object.keys(m).filter((k) => k.startsWith('room_'));
  const order = ['surveying', 'asking', 'building', 'done'].indexOf(job.status);
  const row = (label: string, state: 'done' | 'now' | '', note = '') => `<li class="${state}">${label}<small>${note}</small></li>`;
  const mins = (k: string) => (m[k] ? `${m[k].minutes} min` : '');
  return `<ul class="steps">
    ${row('Studying your floor plan and photos', order > 0 || m.survey ? 'done' : 'now', mins('survey') || 'about 15 minutes')}
    ${row('Walls, doors and windows', m.shell?.status ? 'done' : order >= 2 ? 'now' : '', mins('shell'))}
    ${row(`Rooms${rooms.length ? ': ' + rooms.map(pretty).join(', ') : ''}`, m.check ? 'done' : rooms.length ? 'now' : '', rooms.length ? `${rooms.filter((r) => m[r].status).length} of ${rooms.length}` : '')}
    ${row('Checking the details', m.check?.status ? 'done' : m.check ? 'now' : '', mins('check'))}
    ${row('Lighting', m.bake ? 'done' : m.check?.status ? 'now' : '', mins('bake'))}
  </ul>`;
}

function ask(job: Job) {
  const gaps = job.gaps ?? [];
  root.innerHTML = `<h1>A few things we couldn't see</h1>
    <p class="lede">These parts of the unit are not in what you uploaded. A photo of each makes the model right; if you can't get one, we will build what such a unit normally has there and mark it as a guess.</p>
    <div class="planwrap"><img id="planimg" src="${job.plan_url}" alt="Your floor plan with the unseen areas marked" /></div>
    ${gaps.map((g, i) => `<div class="gap" data-id="${esc(g.id)}"><h3><span>${i + 1}</span>${esc(pretty(g.room))}</h3><p>${esc(g.ask)}</p>
      <input type="file" accept="image/*,video/*" multiple />
      <label><input type="checkbox" /> I can't get this — make your best guess</label></div>`).join('')}
    <button class="primary big" id="continue">Continue</button><p id="msg" role="status"></p>`;
  const img = root.querySelector<HTMLImageElement>('#planimg')!;
  img.onload = () => gaps.forEach((g, i) => {
    const b = document.createElement('i');
    const [x, y, w, h] = g.plan_px;
    Object.assign(b.style, { left: `${(x / img.naturalWidth) * 100}%`, top: `${(y / img.naturalHeight) * 100}%`, width: `${(w / img.naturalWidth) * 100}%`, height: `${(h / img.naturalHeight) * 100}%` });
    b.innerHTML = `<b>${i + 1}</b>`;
    img.parentElement!.appendChild(b);
  });
  const msg = root.querySelector<HTMLElement>('#msg')!;
  root.querySelector<HTMLButtonElement>('#continue')!.onclick = async (e) => {
    const btn = e.currentTarget as HTMLButtonElement;
    btn.disabled = true;
    msg.className = '';
    try {
      const answers: Record<string, string> = {}, files: File[] = [], meta: { name: string; gap: string }[] = [];
      for (const el of root.querySelectorAll<HTMLElement>('.gap')) {
        const picked = [...el.querySelector<HTMLInputElement>('input[type=file]')!.files!];
        // nothing chosen counts as a guess too, so Continue always moves on
        answers[el.dataset.id!] = picked.length && !el.querySelector<HTMLInputElement>('input[type=checkbox]')!.checked ? 'provided' : 'guess';
        if (answers[el.dataset.id!] === 'provided') for (const f of picked) { files.push(f); meta.push({ name: f.name, gap: el.dataset.id! }); }
      }
      if (files.length) {
        const r = await fetch(`api/jobs/${id}/files`, { method: 'POST', body: JSON.stringify({ files: meta }) });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error);
        await putAll(files, j.uploads.map((u: { url: string }) => u.url), (f) => (msg.textContent = `Uploading… ${Math.round(f * 100)}%`));
      }
      const r = await fetch(`api/jobs/${id}/answers`, { method: 'POST', body: JSON.stringify({ answers }) });
      if (!r.ok) throw new Error((await r.json()).error);
      shown = '';
      poll();
    } catch (err) {
      msg.className = 'bad';
      msg.textContent = (err as Error).message || 'Something went wrong.';
      btn.disabled = false;
    }
  };
}

function render(job: Job) {
  document.title = job.title;
  if (job.status === 'asking') {
    if (shown !== 'asking') ask(job);   // drawn once: redrawing would clear the files the person has chosen
    shown = 'asking';
    return;
  }
  shown = job.status;
  const total = Object.values(job.metrics ?? {});
  const stills = (job.stills ?? []).map((s) => `<img loading="lazy" src="units/${id}/stills/${s}.jpg" alt="${esc(pretty(s))}" />`).join('');
  if (job.status === 'done') {
    root.innerHTML = `<h1>${esc(job.title)} is ready</h1>
      <p class="lede">Built in ${Math.round(total.reduce((a, m) => a + m.minutes, 0))} minutes. Anything we had to guess can be highlighted with “Guessed areas” in the model.</p>
      <p><a class="primary" href="index.html?unit=units/${id}">Walk through it</a></p><h2>Stills</h2><div class="stills">${stills}</div>`;
  } else if (job.status === 'failed') {
    root.innerHTML = `<h1>Something went wrong</h1><p class="lede">The build stopped before it finished. Nothing more will be charged for it.</p><p class="bad">${esc(job.error ?? '')}</p>${steps(job)}`;
  } else {
    root.innerHTML = `<h1>Building ${esc(job.title)}</h1>
      <p class="lede">This takes about an hour. You can close this page and come back to the same link.</p>${steps(job)}
      ${stills ? `<h2>First looks</h2><div class="stills">${stills}</div>` : ''}`;
  }
}

async function poll() {
  try {
    const r = await fetch(`api/jobs/${id}`);
    const job = await r.json();
    if (!r.ok) { root.innerHTML = `<h1>Not found</h1><p class="lede">${esc(job.error ?? '')}</p>`; return; }
    render(job);
    if (job.status === 'done' || job.status === 'failed') return;
  } catch { /* a dropped request: try again on the next tick */ }
  setTimeout(poll, shown === 'asking' ? 15000 : 6000);
}
poll();
