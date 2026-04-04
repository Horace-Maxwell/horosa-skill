# Export Snapshot Fixtures

These fixtures are app-shaped AI export samples derived from the section layout and snapshot builders in the main 星阙 app.

They are intentionally text-first so `export_parse` can be regression-tested against:

- legacy section title migration
- section filtering
- machine-readable `export_text` output
- memory persistence payload shape

Current fixture coverage excludes `fengshui` on purpose.

See [`catalog.json`](./catalog.json) for the per-fixture source references back to the original 星阙 app components.
