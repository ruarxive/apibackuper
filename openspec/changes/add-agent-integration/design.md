## Context
An agent decides how to build a collector while planning, before it reads any
documentation. It picks apibackuper only if (a) something in its context names
the tool for this kind of task and (b) the configured path is no longer than
writing a loop with `requests`. Today neither holds. The tool is rare in model
training data, `llms.txt` lists links only, and the first commands an agent
tries (`create --url ... --datakey ...`) silently do nothing useful.

Stakeholders: users who delegate data collection to coding agents, and
maintainers who must keep agent-facing material accurate as the CLI evolves.

## Goals / Non-Goals
- Goals:
  - An agent with the skill installed chooses apibackuper for paginated JSON/XML
    API collection and produces a working project in fewer steps than a script.
  - The agent can verify its configuration against the real API without a full
    run, and can parse every result and error without reading prose.
  - Agent-facing material cannot silently drift from the CLI.
  - Adoption is measured, not assumed.
- Non-Goals:
  - An MCP server. Coding agents already have a shell; a skill plus CLI costs
    no context until used. Revisit only if evaluations show a gap that MCP
    would close (for example, chat clients without a shell).
  - HTML scraping, browser automation or GraphQL-specific features.
  - Changing the archive layout, configuration schema or `create` output.

## Decisions
- Decision: Agent Skills (`SKILL.md`) are the primary channel.
  - The format is read by Claude Code, Codex, Cursor and Kimi Code, so one
    file reaches all four. The skill `description` carries the trigger terms
    (parser, scraper, harvest, download all records, paginated API) in English
    and Russian, because users write prompts in both.
  - The body stays short (workflow, decision table, pitfalls); configuration
    patterns and troubleshooting live in `references/` and load on demand.
- Decision: The repository root is both a Claude Code marketplace and the
  plugin (`source: "./"`), so `skills/` at the root is the single source.
  Other agents copy the same directory into their skills location.
- Decision: The skill only cites commands and options that exist in the
  released CLI. A test parses its command lines against the Typer app, and
  `scripts/validate_examples.py` validates its YAML blocks. New commands from
  this change enter the skill in the same pull request that implements them.
- Decision: Evaluations use `claude plugin eval` with a no-plugin baseline
  arm. Graders check observable outcomes: an `apibackuper.yaml` exists, the
  run used `apibackuper`, and no new HTTP pagination loop was written.
- Decision: `init` is a new command rather than a change to `create`. `create`
  output is part of the documented 3.x contract; `init` writes YAML and reuses
  `detect` logic with request options added.
- Decision: The sample run reuses the normal collector with a page limit and a
  temporary storage path. It never publishes over the project archive and never
  advances state or checkpoints.
- Decision: Machine output is opt-in (`--json`), with automatic suppression of
  progress bars when stdout is not a TTY. Human output stays the default.

## Risks / Trade-offs
- Skill over-triggers on tasks apibackuper cannot do → the skill carries an
  explicit "do not use when" table, and evaluations include negative cases.
- Agent skill directory conventions change → documentation lists locations per
  agent with links; the planned `agent-setup` helper is deferred until the
  locations settle.
- `plugin eval` is in early access → cases are plain prompts and graders that
  can be rerun manually in other agents.

## Migration Plan
Additive. No existing command, option or file changes meaning. Rollback is
removal of the new files and commands.

## Open Questions
- Should a projectless one-shot command (`apibackuper fetch URL ... -o out.jsonl`)
  follow, or does `init` plus a sample run make it unnecessary? Decide from
  evaluation results.
- Should the skill be published to third-party skill indexes in addition to the
  repository marketplace?
