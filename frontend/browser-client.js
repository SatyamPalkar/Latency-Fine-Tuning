// Adapt worker events to the same streaming contract used by the Python service.
let worker;
let loaded = false;
let busy = false;
const encoder = new TextEncoder();

export async function request(url, options = {}) {
  if (url === '/health') {
    return Response.json({ model_name: 'distilgpt2 · ONNX q8', model_loaded: loaded,
      model_loading: busy, max_new_tokens: 256 });
  }
  if (url !== '/generate-stream') return Response.json({ detail: 'Unknown endpoint' }, { status: 404 });
  if (busy) return Response.json({ detail: 'Generation is already running.' }, { status: 429 });
  options.signal?.throwIfAborted();
  busy = true;
  worker ??= new Worker(new URL('./browser-worker.js', import.meta.url), { type: 'module' });
  const activeWorker = worker;
  let closeStream;
  const stream = new ReadableStream({
    start(controller) {
      let closed = false;
      const finish = (terminate = false, error) => {
        if (closed) return;
        closed = true;
        busy = false;
        options.signal?.removeEventListener('abort', abort);
        activeWorker.onmessage = null;
        activeWorker.onerror = null;
        if (terminate) {
          activeWorker.terminate();
          worker = undefined;
          loaded = false;
        }
        if (error) controller.error(error);
        else controller.close();
      };
      closeStream = () => finish(true);
      const abort = () => finish(true, new DOMException('Generation cancelled', 'AbortError'));
      options.signal?.addEventListener('abort', abort, { once: true });
      if (options.signal?.aborted) { abort(); return; }
      activeWorker.onerror = () => {
        controller.enqueue(encoder.encode('event: error\ndata: ' + JSON.stringify({
          message: 'The browser could not load the inference runtime. Check your connection and retry in a current browser.',
        }) + '\n\n'));
        finish(true);
      };
      activeWorker.onmessage = ({ data }) => {
        if (data.type === 'ready') { loaded = true; return; }
        controller.enqueue(encoder.encode(`event: ${data.type}\ndata: ${JSON.stringify(data.payload)}\n\n`));
        if (data.type === 'metrics') finish();
        if (data.type === 'error') finish(true);
      };
      activeWorker.postMessage(JSON.parse(options.body));
    },
    cancel() { closeStream?.(); },
  });
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } });
}
