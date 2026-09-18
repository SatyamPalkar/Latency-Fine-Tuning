"use strict";

const element = (id) => document.getElementById(id);
const form = element("prompt-form");
const promptInput = element("prompt");
const status = element("status");
const responseText = element("response");
let result = null;
let running = false;

promptInput.addEventListener("input", () => {
  element("character-count").textContent = `${promptInput.value.length.toLocaleString()} / 4,000`;
  promptInput.setCustomValidity("");
});
element("temperature").addEventListener("input", (event) => {
  element("temperature-value").value = Number(event.target.value).toFixed(1);
});

function setStatus(message, state) {
  status.textContent = message;
  status.dataset.state = state;
}

function clearResult() {
  result = null;
  for (const id of ["ttft", "total-latency", "throughput", "device", "input-tokens", "output-tokens"]) {
    element(id).textContent = "--";
  }
  element("model-name").textContent = "Pending";
  element("timing-total").textContent = "No measurement";
  element("json-response").textContent = "Waiting for final metrics...";
  element("copy").disabled = true;
  element("copy").textContent = "Copy text";
  responseText.textContent = "";
  const chart = element("timing-chart");
  if (window.Plotly) Plotly.purge(chart);
  chart.replaceChildren();
  chart.setAttribute("aria-label", "No generation timing measured yet");
  const empty = document.createElement("p");
  empty.className = "chart-empty";
  empty.textContent = "Awaiting a completed request";
  chart.append(empty);
}

function showResult(data, accumulatedText) {
  const numericFields = ["input_tokens", "output_tokens", "total_latency_ms", "tokens_per_second"];
  if (numericFields.some((key) => typeof data[key] !== "number" || !Number.isFinite(data[key]) || data[key] < 0)
      || !(data.ttft_ms === null || (typeof data.ttft_ms === "number" && Number.isFinite(data.ttft_ms) && data.ttft_ms >= 0 && data.ttft_ms <= data.total_latency_ms))
      || typeof data.model_name !== "string" || typeof data.device !== "string") {
    throw new Error("The server returned invalid latency metrics.");
  }
  result = {
    text: typeof data.text === "string" ? data.text : accumulatedText,
    model_name: data.model_name,
    device: data.device,
    input_tokens: data.input_tokens,
    output_tokens: data.output_tokens,
    ttft_ms: data.ttft_ms,
    total_latency_ms: data.total_latency_ms,
    tokens_per_second: data.tokens_per_second,
  };
  const decimal = (value) => value === null ? "N/A" : value.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  element("ttft").textContent = decimal(result.ttft_ms);
  element("total-latency").textContent = decimal(result.total_latency_ms);
  element("throughput").textContent = decimal(result.tokens_per_second);
  element("model-name").textContent = result.model_name;
  element("device").textContent = result.device;
  element("input-tokens").textContent = result.input_tokens.toLocaleString();
  element("output-tokens").textContent = result.output_tokens.toLocaleString();
  element("json-response").textContent = JSON.stringify(result, null, 2);
  responseText.textContent = result.text.trimEnd() || "No visible text generated.";
  element("copy").disabled = !result.text;
  element("timing-total").textContent = `${decimal(result.total_latency_ms)} ms total`;
  drawTiming();
}

function drawTiming() {
  const chart = element("timing-chart");
  chart.replaceChildren();
  chart.setAttribute("aria-label", `TTFT: ${result.ttft_ms ?? "unavailable"} ms. Total generation: ${result.total_latency_ms} ms.`);
  if (!window.Plotly || result.ttft_ms === null) {
    const message = document.createElement("p");
    message.className = "chart-empty";
    message.textContent = !window.Plotly ? "Chart unavailable. Measured values are shown above." : "No first token was generated.";
    chart.append(message);
    return;
  }
  const traces = [
    { name: "Time to first token", value: result.ttft_ms, color: "#147d64" },
    { name: "Remaining generation", value: Math.max(0, result.total_latency_ms - result.ttft_ms), color: "#de806d" },
  ].map(({ name, value, color }) => ({
    type: "bar", orientation: "h", name, x: [value], y: ["Generation"],
    marker: { color }, width: 0.45,
    hovertemplate: `${name}: %{x:,.2f} ms<extra></extra>`,
  }));
  Plotly.newPlot(chart, traces, {
    barmode: "stack", height: 126, margin: { l: 0, r: 20, t: 5, b: 30 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", showlegend: false,
    font: { family: "-apple-system, sans-serif", size: 10, color: "#68726e" },
    xaxis: { rangemode: "tozero", ticksuffix: " ms", gridcolor: "#e0e6e2", zeroline: false, fixedrange: true },
    yaxis: { visible: false, fixedrange: true },
  }, { responsive: true, displayModeBar: false });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (running) return;
  if (!promptInput.value.trim()) {
    promptInput.setCustomValidity("Enter a sentence or prompt.");
    promptInput.reportValidity();
    return;
  }
  const payload = {
    prompt: promptInput.value,
    max_new_tokens: Number(element("max-tokens").value),
    temperature: Number(element("temperature").value),
  };
  running = true;
  clearResult();
  element("error").hidden = true;
  responseText.setAttribute("aria-busy", "true");
  setStatus("Starting model...", "busy");
  element("submit").textContent = "Generating...";
  for (const control of form.elements) control.disabled = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  let reader;
  let accumulatedText = "";
  let finalMetrics = null;
  try {
    const response = await fetch("/generate-stream", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload), signal: controller.signal,
    });
    if (!response.ok) {
      let message = `Request failed (${response.status}). Check the server logs and retry.`;
      const body = await response.json().catch(() => null);
      if (typeof body?.detail === "string") message = body.detail;
      if (Array.isArray(body?.detail)) message = body.detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`).join("; ");
      throw new Error(message);
    }
    if (!response.body) throw new Error("Streaming is unavailable in this browser.");
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    function consume(frame) {
      let eventType = "message";
      const dataLines = [];
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      if (!dataLines.length) return;
      const data = JSON.parse(dataLines.join("\n"));
      if (eventType === "error") throw new Error(data.message || "Generation failed.");
      if (eventType === "token") {
        accumulatedText += data.text;
        responseText.textContent = accumulatedText;
        setStatus("Generating...", "busy");
      }
      if (eventType === "metrics") finalMetrics = data;
    }
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let separator;
      while ((separator = /\r?\n\r?\n/.exec(buffer)) !== null) {
        consume(buffer.slice(0, separator.index));
        buffer = buffer.slice(separator.index + separator[0].length);
      }
      if (done) {
        if (buffer.trim()) consume(buffer);
        break;
      }
    }
    if (!finalMetrics) throw new Error("The stream ended without final metrics. Please retry.");
    showResult(finalMetrics, accumulatedText);
    setStatus("Complete", "complete");
  } catch (error) {
    element("error").textContent = error.name === "AbortError"
      ? "Request timed out after 3 minutes. The server may still be loading or generating. Check its logs before retrying."
      : error.message;
    element("error").hidden = false;
    element("json-response").textContent = "Request failed. No completed measurements.";
    if (!accumulatedText) responseText.textContent = "No response received.";
    setStatus("Request failed", "error");
  } finally {
    clearTimeout(timeout);
    if (reader) { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    for (const control of form.elements) control.disabled = false;
    element("submit").textContent = "Generate";
    responseText.setAttribute("aria-busy", "false");
    running = false;
  }
});

element("copy").addEventListener("click", async () => {
  if (!result) return;
  try {
    await navigator.clipboard.writeText(result.text);
    element("copy").textContent = "Copied";
  } catch {
    element("copy").textContent = "Copy failed";
  }
});
