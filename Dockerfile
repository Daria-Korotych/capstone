FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --create-home kv \
    && mkdir /data && chown kv /data
USER kv
ENV KV_PORT=8080
CMD exec uvicorn kv.main:app --host 0.0.0.0 --port ${KV_PORT}
