# Security Policy

## Reporting

If you discover a security issue in Horosa Skill, please avoid opening a public issue with sensitive exploit details.

Instead, report:

- the affected area
- impact
- reproduction details
- any suggested mitigation

through a private channel controlled by the maintainer.

## Scope

Security-sensitive areas in this repository include:

- runtime archive installation
- manifest-driven asset download
- local process startup and shutdown
- local storage of structured run artifacts
- MCP exposure on local interfaces

## Local Attack Surface & Controls

- **Report output paths are untrusted input.** MCP callers are language models, so `output_path` may come from prompt
  injection. Report tools only write under the configured output directory or the roots listed in
  `HOROSA_REPORT_OUTPUT_ROOTS`; anything else fails with `report.output_path_not_allowed` and writes nothing. The three
  report tools are annotated `destructiveHint=true`.
- **HTTP transport is opt-in.** `serve --transport streamable-http` (or `sse`) bound to a **non-loopback** address
  refuses to start without a bearer token (`--token` / `HOROSA_MCP_TOKEN`; requests without it get 401) unless you pass
  `--allow-unauthenticated`. Bound to loopback (`127.0.0.1` / `localhost` / `::1`, the default) it needs no token: any
  local process can call it, the same trust level as the stdio transport. Every HTTP request's `Host` header is checked
  against an allow-list (DNS-rebinding protection): the bind address, loopback, `host.docker.internal`, plus whatever
  `HOROSA_MCP_ALLOWED_HOSTS` adds (comma-separated `name:*`); anything else gets 421, and the 421 body and the start-up
  banner print the exact `HOROSA_MCP_ALLOWED_HOSTS=…` line to add. The token is compared in constant time as UTF-8 bytes.
  Exposing the server on a public interface without an authenticating gateway makes your local memory store readable by
  anyone — see `horosa-skill/examples/clients/remote-connectors-oauth-gateway.md`.
- **Process control never targets processes we did not start.** Stop / restart require strong ownership evidence
  (`runtime/identity.py`); the stop script scopes kills by runtime root; Windows liveness probes use `OpenProcess`,
  never `os.kill`.
- **The optional cloud decision layer (TypeSafe Jev) is off by default.** When enabled, `HOROSA_JEV_SCOPE=meta` sends
  only redacted question metadata; `snapshot` (needed by the faithfulness / hecan surfaces) additionally sends
  export-snapshot text. `HOROSA_JEV_API_KEY` is never logged, never printed by `doctor`, and never written into client
  configs or reports.
- **Client-config writes are minimal and reversible.** `setup` / `client config --write` only upsert their own server
  entry and refuse shapes they cannot parse. When nothing changes nothing is written. Before the first change the user's
  original file is kept as `<file>.horosa-bak` (never overwritten afterwards); later changes add timestamped
  `<file>.horosa-bak.<time>` copies (the newest five are kept). Every format, OpenClaw's own config included, is replaced
  atomically and keeps the original file's permission bits; backups get the same bits.

## Guidance For Contributors

- do not weaken checksum validation paths
- do not add hidden external network dependencies to offline flows
- keep local runtime execution explicit and inspectable
- prefer least-surprise defaults for ports, paths, and file writes
