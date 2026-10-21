import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'docs');
await mkdir(path.join(output, 'static'), { recursive: true });
for (const name of ['app.js', 'styles.css', 'favicon.svg', 'browser-client.js', 'browser-worker.js']) {
  await copyFile(path.join(root, 'frontend', name), path.join(output, 'static', name));
}
const html = (await readFile(path.join(root, 'frontend/index.html'), 'utf8'))
  .replaceAll('href="/static/', 'href="./static/')
  .replaceAll('src="/static/', 'src="./static/')
  .replaceAll('href="/"', 'href="./"')
  .replace('href="/benchmarks"', 'href="./benchmarks.html"')
  .replace('href="/docs">API', 'href="./about.html">About this demo')
  .replace('/assets/plotly.min.js', 'https://cdn.plot.ly/plotly-2.35.2.min.js')
  .replace('<script defer src="./static/app.js"></script>', '<script>window.LATENCY_BROWSER_MODE = true;</script>\n  <script defer src="./static/app.js"></script>')
  .replace('Checking service…', 'Browser inference')
  .replace('Server generation', 'Browser generation')
  .replace('The default model, distilgpt2, continues your text.', 'Runs on your device. The first request downloads an ONNX model (roughly 240 MB), then your browser can cache it. distilgpt2 continues your text.')
  .replace('Server timing excludes model loading, prompt tokenization, and network transit.', 'Browser timing excludes model download and tokenization; includes first-run runtime warmup. Performance depends on your device.');
await writeFile(path.join(output, 'index.html'), html);
await writeFile(path.join(output, '.nojekyll'), '');
await copyFile(path.join(root, 'dashboard/index.html'), path.join(output, 'benchmarks.html'));
await writeFile(path.join(output, 'about.html'), `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>About | Latency Lab</title><link rel="stylesheet" href="./static/styles.css"></head>
<body><main><a href="./">← Live inference</a><h1>Real inference. In your browser.</h1>
<p>This free demo runs quantized distilgpt2 through Transformers.js and ONNX Runtime in a web worker on your CPU. No paid model API or backend server is used.</p>
<p>The initial request downloads model files from Hugging Face and the runtime from jsDelivr. Downloads may take a few minutes. Your browser can cache them for later visits. Prompts are processed on your device.</p>
<p>TTFT starts immediately before model.generate and ends at its first generated token callback. Total latency ends when generation resolves. Both exclude model loading and prompt tokenization; first-run runtime warmup is included. Counts include generated special tokens.</p>
<p>These are device-dependent browser measurements. The historical benchmark dashboard records separate Python server runs and should not be compared as equivalent hardware results.</p>
<p>Stop terminates the worker. A later request reloads the model from the browser cache when available. If generation fails, retry with fewer tokens in a current desktop browser.</p>
<p>The repository also includes the original FastAPI streaming server and Docker deployment.</p>
<a href="https://github.com/SatyamPalkar/Latency-Fine-Tuning">Source and Python API documentation</a></main></body></html>`);
console.log('Built GitHub Pages site in docs/ with browser inference and repository-relative links.');
