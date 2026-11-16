/** PUT with progress, which fetch cannot report for uploads. */
function put(url: string, file: File, onProgress: (sent: number) => void) {
  return new Promise<void>((ok, fail) => {
    const x = new XMLHttpRequest();
    x.open('PUT', url);
    x.upload.onprogress = (e) => onProgress(e.loaded);
    x.onload = () => (x.status < 300 ? ok() : fail(new Error(`Upload of ${file.name} failed (${x.status})`)));
    x.onerror = () => fail(new Error(`Upload of ${file.name} failed`));
    x.send(file);
  });
}

/** Uploads files three at a time and reports the fraction sent. */
export async function putAll(files: File[], urls: string[], onFraction: (f: number) => void) {
  const total = files.reduce((a, f) => a + f.size, 0) || 1, sent = files.map(() => 0);
  let next = 0;
  await Promise.all([0, 1, 2].map(async () => {
    while (next < files.length) {
      const i = next++;
      await put(urls[i], files[i], (n) => { sent[i] = n; onFraction(sent.reduce((a, b) => a + b, 0) / total); });
    }
  }));
}
