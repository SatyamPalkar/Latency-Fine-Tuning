import { AutoTokenizer, AutoModelForCausalLM, TextStreamer, env } from
  'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1/dist/transformers.min.js';

env.allowLocalModels = false;
// GitHub Pages cannot set the isolation headers required by multithreaded WASM.
env.backends.onnx.wasm.numThreads = 1;
const MODEL = 'Xenova/distilgpt2';
let tokenizer;
let model;
let lastProgress = 0;
const emit = (type, payload) => self.postMessage({ type, payload });

self.onmessage = async ({ data }) => {
  try {
    if (!data.prompt?.trim() || data.prompt.length > 4000 || !Number.isInteger(data.max_new_tokens)
        || data.max_new_tokens < 1 || data.max_new_tokens > 256
        || !Number.isFinite(data.temperature) || data.temperature < 0 || data.temperature > 2) {
      throw new Error('Enter a prompt, 1–256 output tokens, and a temperature between 0 and 2.');
    }
    if (!model) {
      emit('status', { message: 'Downloading model… first visit may take a few minutes' });
      const progress_callback = (progress) => {
        if (progress.status === 'progress' && performance.now() - lastProgress > 400) {
          lastProgress = performance.now();
          emit('status', { message: `Downloading ${progress.file}: ${Math.round(progress.progress)}%` });
        }
      };
      tokenizer = await AutoTokenizer.from_pretrained(MODEL, { progress_callback });
      model = await AutoModelForCausalLM.from_pretrained(MODEL, {
        device: 'wasm', dtype: 'q8', progress_callback,
      });
      emit('ready', {});
    }
    const inputs = await tokenizer(data.prompt);
    const inputTokens = inputs.input_ids.dims[1];
    if (inputTokens + data.max_new_tokens > 1024) {
      throw new Error(`Prompt (${inputTokens} tokens) plus output exceeds the 1,024-token context. Shorten the prompt or output.`);
    }
    emit('status', { message: 'Generating on your device…' });
    let firstToken = null;
    const streamer = new TextStreamer(tokenizer, {
      skip_prompt: true, skip_special_tokens: true,
      token_callback_function: () => { firstToken ??= performance.now(); },
      callback_function: (text) => emit('token', { text }),
    });
    const start = performance.now();
    const outputs = await model.generate({ ...inputs,
      max_new_tokens: data.max_new_tokens, do_sample: data.temperature > 0,
      ...(data.temperature > 0 ? { temperature: data.temperature } : {}),
      streamer, pad_token_id: tokenizer.eos_token_id,
    });
    const end = performance.now();
    const generated = outputs.tolist()[0].slice(inputTokens);
    const total = end - start;
    emit('metrics', {
      text: tokenizer.decode(generated, { skip_special_tokens: true }),
      model_name: 'distilgpt2 · ONNX q8', device: 'Browser CPU · WASM',
      input_tokens: inputTokens, output_tokens: generated.length,
      ttft_ms: firstToken === null ? null : firstToken - start,
      total_latency_ms: total, tokens_per_second: total > 0 ? generated.length * 1000 / total : 0,
      measurement_scope: 'Browser model.generate; excludes model download and tokenization. Includes first-run runtime warmup. Device-dependent; not a server benchmark.',
    });
  } catch (error) {
    emit('error', { message: error.message || 'Browser inference failed. Try a shorter prompt or a current desktop browser.' });
  }
};
