import './site.css';
import { putAll } from './put';

const $ = <T extends HTMLElement>(s: string) => document.querySelector<T>(s)!;
const plan = $<HTMLInputElement>('#plan'), media = $<HTMLInputElement>('#media'), msg = $('#msg');

for (const [input, list] of [[plan, $('#plan-list')], [media, $('#media-list')]] as const) {
  const show = () => {
    const f = [...(input.files ?? [])];
    list.textContent = f.length ? `${f.length} file${f.length > 1 ? 's' : ''} · ${(f.reduce((a, x) => a + x.size, 0) / 1e6).toFixed(0)} MB` : '';
  };
  input.onchange = show;
  const drop = input.closest<HTMLElement>('.drop')!;
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer) { input.files = e.dataTransfer.files; show(); } };
}

$<HTMLFormElement>('#form').onsubmit = async (e) => {
  e.preventDefault();
  const go = $<HTMLButtonElement>('#go');
  go.disabled = true;
  msg.className = '';
  try {
    const files = [...plan.files!, ...media.files!];
    const r = await fetch('api/jobs', {
      method: 'POST',
      body: JSON.stringify({
        code: $<HTMLInputElement>('#code').value.trim(),
        title: $<HTMLInputElement>('#title').value.trim(),
        furniture: $<HTMLInputElement>('input[name=furniture]:checked').value === 'yes',
        files: files.map((f, i) => ({ name: f.name, kind: i < plan.files!.length ? 'plan' : 'media' })),
      }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    await putAll(files, j.uploads.map((u: { url: string }) => u.url), (f) => (msg.textContent = `Uploading… ${Math.round(f * 100)}%`));
    const s = await fetch(`api/jobs/${j.job_id}/start`, { method: 'POST' });
    if (!s.ok) throw new Error((await s.json()).error);
    location.href = `job.html?id=${j.job_id}`;
  } catch (err) {
    msg.className = 'bad';
    msg.textContent = (err as Error).message || 'Something went wrong.';
    go.disabled = false;
  }
};
