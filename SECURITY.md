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
- **HTTP transport is opt-in and token-gated.** `serve --transport streamable-http` requires a bearer token
  (`--token` / `HOROSA_MCP_TOKEN`; 401 without it) and validates `Host` against `HOROSA_ALLOWED_HOSTS` (421 otherwise).
  Exposing it on a public interface without an authenticating gateway makes your local memory store readable by anyone —
  see `horosa-skill/examples/clients/remote-connectors-oauth-gateway.md`.
- **Process control never targets processes we did not start.** Stop / restart require strong ownership evidence
  (`runtime/identity.py`); the stop script scopes kills by runtime root; Windows liveness probes use `OpenProcess`,
  never `os.kill`.
- **The optional cloud decision layer (TypeSafe Jev) is off by default.** When enabled, `HOROSA_JEV_SCOPE=meta` sends
  only redacted question metadata; `snapshot` (needed by the faithfulness / hecan surfaces) additionally sends
  export-snapshot text. `HOROSA_JEV_API_KEY` is never logged, never printed by `doctor`, and never written into client
  configs or reports.
- **Client-config writes are minimal and reversible.** `setup --write` only upserts its own server entry, keeps a
  `.horosa-bak`, replaces atomically, and refuses shapes it cannot parse.

## Guidance For Contributors

- do not weaken checksum validation paths
- do not add hidden external network dependencies to offline flows
- keep local runtime execution explicit and inspectable
- prefer least-surprise defaults for ports, paths, and file writes
