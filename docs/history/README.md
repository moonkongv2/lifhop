# Historical execution evidence

## Legacy test output

`legacy-test-result.txt` preserves the former root `test_result.txt` byte-for-byte.
Its last modifying commit before cleanup was `668b64a` (`refactor: extract ChatGPT
import job processor`). It records 62 tests: 56 passed and six import tests failed.
It is historical failure evidence, not the current suite result or an unresolved
failure reproduced by this maintenance work. No current code/CI consumer of the
old path was found; future checks should report their own fresh results.

The full status snapshot is [CURRENT_HISTORY_20261021.md](CURRENT_HISTORY_20261021.md).
Current implementation and open gates are in [CURRENT.md](../../CURRENT.md).

## Immutable status snapshot

[CURRENT_20261021.original.txt](CURRENT_20261021.original.txt) preserves the entire
pre-move root `CURRENT_HISTORY_20261021.md` byte-for-byte, including its header.
SHA-256: `789af22a1bb011cd6dfed99c354e8a40dfa215f725d3e9d68e42b4e6dee7c520`.
Its old relative paths use the repository root at capture time. The Markdown
reading copy updates documentation links and its provenance header; dates,
results, incidents and approval boundaries remain historical evidence.
