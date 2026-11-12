# v0.50.0-dev E-02: the JS engine (horosa-core-js) and a Node that can run it are baked into the image. Before, the gateway image
# had neither, so BaZi / Ziwei / Qimen / Taiyi / Jinkou / Liuren / Heluo / Canping … failed with js_engine.cli_missing.
# Node is pinned to the offline runtime's Node (contracts/runtime_toolchain.json `node.version`; the JS engine needs >= 20.10)
# and both stages share one Debian release so the copied binary finds the glibc / libstdc++ it was built against
# (tests/test_dockerfile_matches_wheel_includes.py keeps the pin, the floor and the copies in step).
FROM node:22.23.2-trixie-slim AS corejs

WORKDIR /opt/horosa-core-js
# Production dependencies exactly as locked (astronomy-engine / lunar-javascript / moment / tz-lookup); dev deps never enter.
COPY horosa-core-js/package.json horosa-core-js/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund --loglevel=error
# The engine itself, from the build context (the committed dist/app-charts.cjs included). Nothing is fetched at runtime.
COPY horosa-core-js/bin ./bin
COPY horosa-core-js/src ./src
COPY horosa-core-js/dist ./dist

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir uv

# Node + the engine from the first stage; HOROSA_CORE_JS_ROOT points the JS client at it (doctor's js_engine section: ready).
COPY --from=corejs /usr/local/bin/node /usr/local/bin/node
COPY --from=corejs /opt/horosa-core-js /opt/horosa-core-js
ENV HOROSA_CORE_JS_ROOT=/opt/horosa-core-js

COPY pyproject.toml README.md ./
COPY src ./src
# pyproject force-includes scripts/runtime_templates/windows into the wheel; without this COPY hatchling
# aborts the build inside the image (tests/test_dockerfile_matches_wheel_includes.py keeps the two in step).
COPY scripts/runtime_templates ./scripts/runtime_templates
# pyproject also force-includes two runtime contracts (v0.40.0 P1); the wheel build needs them present.
COPY contracts/jev_thresholds.json contracts/technique_provenance.json ./contracts/

RUN uv pip install --system . && node --version

EXPOSE 8765

CMD ["horosa-skill", "serve", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8765"]
