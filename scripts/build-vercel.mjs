import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, '.vercel/output');
const staticDir = path.join(output, 'static');
const rawBackend = process.env.LATENCY_BACKEND_URL?.trim();
let backend;
if (rawBackend) {
  const url = new URL(rawBackend);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('LATENCY_BACKEND_URL must be an HTTPS origin without credentials, a path, or query parameters.');
  }
  backend = url.origin;
}

await mkdir(path.join(staticDir, 'static'), { recursive: true });
for (const name of ['app.js', 'styles.css', 'favicon.svg']) {
  await copyFile(path.join(root, 'frontend', name), path.join(staticDir, 'static', name));
}
// Pin the same Plotly version used by the checked-in historical dashboard.
const html = (await readFile(path.join(root, 'frontend/index.html'), 'utf8'))
  .replace('/assets/plotly.min.js', 'https://cdn.plot.ly/plotly-2.35.2.min.js')
  .replace('<script defer src="/static/app.js"></script>',
    `<script>window.LATENCY_BACKEND_CONFIGURED = ${Boolean(backend)};</script>\n  <script defer src="/static/app.js"></script>`);
await writeFile(path.join(staticDir, 'index.html'), html);
await copyFile(path.join(root, 'dashboard/index.html'), path.join(staticDir, 'benchmarks.html'));
await writeFile(path.join(staticDir, 'offline.json'), JSON.stringify({
  detail: 'Live inference is offline. The model server has not been connected.',
}));
await writeFile(path.join(staticDir, 'offline.html'),
  '<!doctype html><html lang="en"><meta charset="utf-8"><title>Inference offline</title><h1>Inference offline</h1><p>The model server has not been connected yet.</p><a href="/">Back to Latency Lab</a></html>');

const endpoints = ['health', 'ready', 'generate', 'generate-stream', 'docs', 'openapi.json', 'redoc'];
const routes = endpoints.map((endpoint) => ({
  src: `/${endpoint.replaceAll('.', '\\.')}/?`,
  ...(backend
    ? { dest: `${backend}/${endpoint}`, headers: { 'Cache-Control': 'no-store' } }
    : { dest: ['docs', 'redoc'].includes(endpoint) ? '/offline.html' : '/offline.json', status: 503,
        headers: { 'Cache-Control': 'no-store' } }),
}));
routes.push({ src: '/benchmarks/?', dest: '/benchmarks.html' }, { handle: 'filesystem' });
await writeFile(path.join(output, 'config.json'), JSON.stringify({ version: 3, routes }, null, 2));
console.log(`Static frontend built. Python functions: 0. Inference backend: ${backend ? 'connected in routing configuration' : 'not configured (offline state)'}.`);
