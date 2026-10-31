# Change: Make apibackuper discoverable and efficient for AI coding agents

## Why
Coding agents (Claude Code, Codex, Cursor, Kimi Code) asked to "write a parser"
for a paginated API write a new Python requests loop per source instead of
configuring apibackuper. Two causes: agents do not learn about the tool at the
moment they plan the work, and the apibackuper path costs more steps than a
30-line script (`create` writes INI and ignores its API flags, `detect` only
handles public GET endpoints, there is no quick sample run against the real
API, and errors and progress are written for humans).

## What Changes
- Ship an Agent Skill (`skills/apibackuper/SKILL.md` plus references) that
  tells agents when to choose apibackuper, how to configure a project, and how
  to extend it with hooks instead of writing a separate parser.
- Package the repository as a Claude Code plugin marketplace and document the
  skill locations for Codex, Cursor and Kimi Code; provide an `AGENTS.md`
  snippet for agents without skill support.
- Keep the skill in sync with the CLI: tests check that every command and
  option it cites exists and that its YAML examples validate against the schema.
- Add an evaluation suite that measures how often agents choose apibackuper,
  with and without the skill.
- Add `apibackuper init` that probes an endpoint (GET or POST, headers,
  authentication, body) and writes a complete YAML project with a JSON report.
- Add a sample run (`run full --max-pages N`) that saves into a temporary
  location and prints the first records, so a configuration can be checked in
  seconds against the real API.
- Add machine-readable output: a global `--json` mode for results and errors
  with stable error codes and hints, and no progress bars when stdout is not a
  terminal.
- Add `apibackuper schema` and `validate-config --json`.
- Publish LLM-oriented documentation (`llms-full.txt`), fix pages that still
  describe cursor and next-link pagination as unsupported, and broaden the
  package description and keywords.

## Impact
- Affected specs: `agent-integration` (new), `cli-machine-output` (new),
  `backup-sample` (new), `api-detection`, `config-validation`, `document-usage`
- Affected code: `apibackuper/core.py`, `apibackuper/cmds/project.py`,
  `apibackuper/cmds/backup.py`, `apibackuper/cmds/profile.py`,
  `scripts/validate_examples.py`, `pyproject.toml`, `docs/`, new `skills/`,
  `.claude-plugin/` and `evals/` directories
- No change to archive layout, configuration schema or existing command
  behaviour; `create` keeps its current output for compatibility
