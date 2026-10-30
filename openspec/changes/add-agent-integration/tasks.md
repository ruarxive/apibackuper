## 1. Agent skill and distribution
- [x] 1.1 Write `skills/apibackuper/SKILL.md` with trigger description, decision table, workflow and pitfalls
- [x] 1.2 Add `skills/apibackuper/references/` with configuration patterns and troubleshooting
- [x] 1.3 Add `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`; pass `claude plugin validate --strict`
- [x] 1.4 Add a test that every `apibackuper` command and option cited in `skills/` exists in the CLI
- [x] 1.5 Validate YAML blocks in `skills/` with `scripts/validate_examples.py`
- [x] 1.6 Add the AI agents documentation page with skill locations per agent and an `AGENTS.md` snippet
- [x] 1.7 Link the skill from README and `llms.txt`; broaden package description and keywords
- [x] 1.8 Fix pages that describe cursor and next-link pagination as unsupported

## 2. Evaluation
- [x] 2.1 Add `evals/` cases: page-number, next-URL, Link-header and POST APIs, and a single-request negative case; document how to rerun in other agents
- [ ] 2.2 Record a baseline and with-skill score
- [x] 2.3 Add cursor, authenticated-API and WebSocket negative cases

## 3. CLI ergonomics for agents
- [x] 3.1 Add `apibackuper init PATH --url URL` with `--method`, `--header`, `--body`, `--auth*`, `--data-key`, `--no-probe` and `--force`; write YAML and print a JSON report
- [x] 3.2 Add `run full --max-pages N` sample mode with temporary storage and record preview
- [x] 3.3 Add global `--json` output for command results and errors with stable error codes and hints
- [x] 3.4 Hide progress bars when stderr is not a terminal; add global `--no-progress`
- [x] 3.5 Add `apibackuper schema` and `validate-config --json`
- [x] 3.6 Warn in `validate-config` when the iteration mode has no pagination parameter; make `detect` probe page, offset and size parameters
- [x] 3.7 Update the skill and documentation to use the new commands
- [x] 3.8 Tests for probing, init, sample runs, JSON mode and validation warnings

## 4. LLM documentation
- [x] 4.1 Generate `llms-full.txt` from the configuration reference, pagination, HTTP request files and hooks pages
- [x] 4.2 Add a CI check that `llms-full.txt` is current
