FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache DEVICE=cpu PRELOAD_MODEL=true \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.0 \
    && pip install --no-cache-dir -r requirements.txt

# Include the default model at build time, rather than downloading it on a first visit.
ARG MODEL_NAME=distilgpt2
ENV MODEL_NAME=${MODEL_NAME}
RUN python -c "import os; from transformers import AutoTokenizer, AutoModelForCausalLM; n=os.environ['MODEL_NAME']; AutoTokenizer.from_pretrained(n); AutoModelForCausalLM.from_pretrained(n, use_safetensors=True)"

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /opt/hf-cache

COPY --chown=appuser:appuser api ./api
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser frontend ./frontend
COPY --chown=appuser:appuser dashboard ./dashboard
COPY --chown=appuser:appuser benchmarks/reference ./benchmarks/reference
COPY --chown=appuser:appuser scripts/serve.py ./scripts/serve.py

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/ready', timeout=4)"
CMD ["python", "scripts/serve.py"]
