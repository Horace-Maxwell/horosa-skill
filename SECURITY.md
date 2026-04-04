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

## Guidance For Contributors

- do not weaken checksum validation paths
- do not add hidden external network dependencies to offline flows
- keep local runtime execution explicit and inspectable
- prefer least-surprise defaults for ports, paths, and file writes
