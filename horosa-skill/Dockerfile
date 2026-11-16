# v0.50.0-dev E-02: the JS engine (horosa-core-js) and a Node that can run it are baked into the image. Before, the gateway image
# had neither, so BaZi / Ziwei / Qimen / Taiyi / Jinkou / Liuren / Heluo / Canping … failed with js_engine.cli_missing.
# Node is pinned to the offline runtime's Node (contracts/runtime_toolchain.json `node.version`; the JS engine needs >= 20.10)
# and both stages share one Debian release so the copied binary finds the glibc / libstdc++ it was built against
# (tests/test_dockerfile_matches_wheel_includes.py keeps the pin, the floor and the copies in step).
# 审计 PF-15：基础镜像钉 tag@digest（只钉 tag 会被上游改写）；Dependabot 跟进。
FROM node:26.13.1-trixie-slim@sha256:e6bedef217677b276c591795e169840edd9096dbf13f29df8ef8d1856b8820bc AS corejs

WORKDIR /opt/horosa-core-js
# Production dependencies exactly as locked (astronomy-engine / lunar-javascript / moment / tz-lookup); dev deps never enter.
COPY horosa-core-js/package.json horosa-core-js/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund --loglevel=error
# The engine itself, from the build context (the committed dist/app-charts.cjs included). Nothing is fetched at runtime.
COPY horosa-core-js/bin ./bin
COPY horosa-core-js/src ./src
COPY horosa-core-js/dist ./dist

FROM python:3.12-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# uv 钉版本 + digest（以前 `pip install uv` 不钉版本）
COPY --from=ghcr.io/astral-sh/uv:0.10.7@sha256:edd1fd89f3e5b005814cc8f777610445d7b7e3ed05361f9ddfae67bebfe8456a /uv /uvx /usr/local/bin/

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

# 非 root 运行（CIS Docker Benchmark 4.1）：数据在 /data（卷挂这里），不再是 /root/.horosa-skill。
RUN groupadd --gid 10001 horosa && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin horosa \
    && mkdir -p /data && chown 10001:10001 /data
ENV HOROSA_SKILL_DATA_DIR=/data
USER 10001:10001

EXPOSE 8765

# 存活探针打不过鉴权的 /healthz（不带数据），CIS 4.6
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=4).status == 200 else 1)"]

CMD ["horosa-skill", "serve", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8765"]
