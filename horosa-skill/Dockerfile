FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
# pyproject force-includes scripts/runtime_templates/windows into the wheel; without this COPY hatchling
# aborts the build inside the image (tests/test_dockerfile_matches_wheel_includes.py keeps the two in step).
COPY scripts/runtime_templates ./scripts/runtime_templates
# pyproject also force-includes two runtime contracts (v0.40.0 P1); the wheel build needs them present.
COPY contracts/jev_thresholds.json contracts/technique_provenance.json ./contracts/

RUN uv pip install --system .

EXPOSE 8765

CMD ["horosa-skill", "serve", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8765"]

