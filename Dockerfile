FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# 依赖单独一层，代码变更时不必重装
# PIP_INDEX_URL 可在构建时覆盖，例如国内网络：
#   docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY requirements.txt ./
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

COPY api ./api
COPY web ./web
COPY data ./data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status==200 else 1)"

CMD ["python", "api/server.py"]
