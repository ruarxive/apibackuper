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
- [ ] 2.3 Add cursor, authenticated-API and JavaScript-site negative cases

## 3. CLI ergonomics for agents
- [ ] 3.1 Add `apibackuper init NAME --url URL` with `--method`, `--header`, `--body`, `--auth-*` options; write YAML and print a JSON report
- [ ] 3.2 Add `run full --max-pages N` sample mode with temporary storage and record preview
- [ ] 3.3 Add global `--json` output for command results and errors with stable error codes and hints
- [ ] 3.4 Disable progress bars when stdout is not a TTY; add `--no-progress`
- [ ] 3.5 Add `apibackuper schema` and `validate-config --json`
- [ ] 3.6 Warn in `validate-config` when the iteration mode has no pagination parameter; make `detect` suggest page/offset parameter names by probing a second page
- [ ] 3.7 Update the skill to use the new commands; rerun evaluations

## 4. LLM documentation
- [ ] 4.1 Generate `llms-full.txt` from the configuration reference, pagination, HTTP request files and hooks pages
- [ ] 4.2 Add a CI check that `llms-full.txt` is current
