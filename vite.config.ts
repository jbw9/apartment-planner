import { defineConfig } from 'vite';

// three pages: the viewer (index), the upload form (start) and a job's progress and questions (job)
export default defineConfig({ build: { rollupOptions: { input: ['index.html', 'start.html', 'job.html'] } } });
