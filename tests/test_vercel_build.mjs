import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { cp, mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const source = new URL('../', import.meta.url);

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'latency-vercel-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const item of ['frontend', 'dashboard', 'scripts']) {
    await cp(new URL(item, source), path.join(root, item), { recursive: true });
  }
  return {
    root,
    build(url = '') {
      return execFileSync(process.execPath, [path.join(root, 'scripts/build-vercel.mjs')], {
        env: { ...process.env, LATENCY_BACKEND_URL: url }, encoding: 'utf8', stdio: 'pipe',
      });
    },
    async config() {
      return JSON.parse(await readFile(path.join(root, '.vercel/output/config.json'), 'utf8'));
    },
  };
}

test('an unconfigured deployment emits static assets and explicit offline responses, without functions', async (t) => {
  const f = await fixture(t);
  f.build();
  const config = await f.config();
  assert.equal(config.version, 3);
  assert.equal(config.routes.find(r => r.src === '/generate-stream/?').status, 503);
  assert.equal(config.routes.find(r => r.src === '/docs/?').dest, '/offline.html');
  const output = await readdir(path.join(f.root, '.vercel/output'));
  assert.deepEqual(output.sort(), ['config.json', 'static']);
  const html = await readFile(path.join(f.root, '.vercel/output/static/index.html'), 'utf8');
  assert.match(html, /LATENCY_BACKEND_CONFIGURED = false/);
  assert.match(html, /https:\/\/cdn.plot.ly\/plotly-2.35.2.min.js/);
  assert.ok((await readFile(path.join(f.root, '.vercel/output/static/benchmarks.html'))).length);
});

test('a configured deployment proxies POST streaming, health and API documentation to the backend', async (t) => {
  const f = await fixture(t);
  f.build('https://inference.example.com/');
  const { routes } = await f.config();
  for (const endpoint of ['generate', 'generate-stream', 'health', 'ready', 'docs']) {
    const route = routes.find(r => r.src === `/${endpoint}/?`);
    assert.equal(route.dest, `https://inference.example.com/${endpoint}`);
    assert.equal(route.status, undefined);
    assert.equal(route.methods, undefined); // Do not restrict generation to GET.
    assert.equal(route.headers['Cache-Control'], 'no-store');
  }
  const html = await readFile(path.join(f.root, '.vercel/output/static/index.html'), 'utf8');
  assert.match(html, /LATENCY_BACKEND_CONFIGURED = true/);
});

test('invalid or credential-bearing backend URLs fail before emitting a deployment', async (t) => {
  const f = await fixture(t);
  for (const url of ['http://example.com', 'https://user:secret@example.com', 'https://example.com/api', 'https://example.com/?token=secret', 'not-a-url']) {
    assert.throws(() => f.build(url));
  }
});

test('offline frontend disables generation and does not send an inference request', async () => {
  const nodes = new Map();
  const document = {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, { dataset: {}, addEventListener() {} });
      return nodes.get(id);
    },
    querySelectorAll: () => [],
  };
  const script = await readFile(new URL('frontend/app.js', source), 'utf8');
  vm.runInNewContext(script, {
    document, window: { LATENCY_BACKEND_CONFIGURED: false },
    fetch() { assert.fail('An unconfigured frontend must not call inference'); },
  });
  assert.equal(nodes.get('submit').disabled, true);
  assert.equal(nodes.get('status').textContent, 'Inference offline');
  assert.equal(nodes.get('error').hidden, false);
});
