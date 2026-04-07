FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN rm -rf utils/auth_core/*.py 2>/dev/null || true

# === HF 适配修改 ===
EXPOSE ${PORT:-8000}          # 支持 HF 的 $PORT
ENV PYTHONUNBUFFERED=1
ENV PORT=7860                 # 给本地测试一个默认值，HF 会覆盖

CMD ["python", "wfxl_openai_regst.py"]
