FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system .

EXPOSE 8765

CMD ["horosa-skill", "serve", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8765"]

