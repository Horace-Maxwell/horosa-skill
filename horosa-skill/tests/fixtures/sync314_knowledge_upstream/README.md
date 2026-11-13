# sync314_knowledge_upstream

A hand-written miniature of the upstream help layout (v3.14.0: one book per page, one chapter per technique), for
`tests/test_sync314_knowledge_harvest.py`. The test copies this tree to `<tmp>/Horosa-Web/astrostudyui/src/`, commits it
to a throwaway git repository and runs `scripts/harvest_help_books.mjs` on it.

Nothing here is copied from upstream. It only follows the same contract the harvester relies on:

- `components/help/techniqueHelpRegistry.js` exports `TECHNIQUE_HELP_DOCS` (tab key → component with a static `book`);
- `components/help/HelpBook.js` exports `bookChapters(book)`;
- `components/help/helpDocStyle.js` exports the style objects (`title` / `h` / `ct`), `kv()` (class `horosa-help-kv`) and the
  pure widgets marked `__helpPure` (`Lead`, `Section`, `Tip` with class `horosa-help-tip`, `Steps` with class
  `horosa-help-step-no`, `OptionTable`);
- `utils/aiTools/helpText.js` exports `helpElementToText(element)`, the plain-text walker the harvest is checked against.
