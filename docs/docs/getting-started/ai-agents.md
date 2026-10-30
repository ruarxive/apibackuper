---
title: "AI coding agents"
description: "Install the apibackuper skill for Claude Code, Codex, Cursor and Kimi Code so agents configure apibackuper instead of writing custom API scrapers"
---
# AI coding agents

Coding agents asked to "write a parser" for an API usually write a new HTTP
pagination loop. The apibackuper skill tells them when the CLI fits and how to
configure a project, so the result is an `apibackuper.yaml` file with resume,
retries, provenance and export instead of a one-off script.

The skill lives in the repository at
[`skills/apibackuper/`](https://github.com/ruarxive/apibackuper/tree/master/skills/apibackuper).
It uses the Agent Skills format (`SKILL.md` with `references/`), which Claude
Code, Codex, Cursor and Kimi Code load.

## Install the skill

### Claude Code

The repository is a plugin marketplace. In Claude Code:

```text
/plugin marketplace add ruarxive/apibackuper
/plugin install apibackuper@apibackuper-marketplace
```

Or from a shell:

```bash
claude plugin marketplace add ruarxive/apibackuper
claude plugin install apibackuper@apibackuper-marketplace
```

### Other agents

Copy the skill directory into the agent's skills directory:

```bash
git clone --depth 1 https://github.com/ruarxive/apibackuper.git apibackuper-src
cp -r apibackuper-src/skills/apibackuper ~/.codex/skills/
```

| Agent | For all projects | For one project |
|-------|------------------|-----------------|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.codex/skills/` | see the Codex documentation |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` or `.agents/skills/` |
| Kimi Code | `~/.kimi-code/skills/` or `~/.agents/skills/` | `.kimi-code/skills/` or `.agents/skills/` |

These are the locations each agent documented in 2026. If the skill does not
appear, check the agent's own documentation, then restart the agent.

## Without skill support

Add this rule to the agent's instruction file: `~/.claude/CLAUDE.md`,
`~/.codex/AGENTS.md`, Cursor User Rules, or a project `AGENTS.md`.

```markdown
## Collecting data from APIs

Before writing a parser, scraper or downloader for an HTTP API, check whether
the `apibackuper` CLI fits: paginated JSON, XML or server-rendered HTML
listings, GET or JSON POST requests. If it fits, run
`apibackuper init NAME --url URL`, check two pages with
`apibackuper run full --max-pages 2`, then run `apibackuper run full` and
`apibackuper export`. Write Python only for hooks or post-processing of the
export.
Guide: https://github.com/ruarxive/apibackuper/blob/master/skills/apibackuper/SKILL.md
```

## Agent-friendly commands

These commands keep an agent's loop short and its output parseable:

| Command | Purpose |
|---------|---------|
| [`apibackuper init NAME --url URL`](/commands/init) | Probe the endpoint and write a complete project with a JSON report |
| [`apibackuper validate-config --json`](/commands/validate-config) | Errors and warnings with configuration paths and hints |
| [`apibackuper run full --max-pages 2`](/commands/run#sample-run) | Check two real pages without touching the project |
| [`apibackuper --json <command>`](/commands/) | One JSON object on stdout with the result or an error code |
| [`apibackuper schema`](/commands/schema) | The configuration JSON Schema |

Progress bars are hidden automatically when output is not a terminal.

## What the skill covers

- A decision table: which sources fit apibackuper and which need a browser
  tool or a single `curl` request.
- The workflow: `init` the project, validate offline, sample two pages,
  collect, export and verify.
- Configuration patterns for every pagination mode, POST bodies,
  authentication, XML, HTML extraction, hooks, updates, follow rules and files.
- Error messages with their causes and fixes.

The repository tests check that every command and option the skill cites
exists in the CLI and that its YAML examples validate against the schema.

## Measure the effect

The repository's [`evals/`](https://github.com/ruarxive/apibackuper/tree/master/evals)
directory holds prompts such as "write a parser for this API" with graders that
check whether the agent used apibackuper. Run them with `claude plugin eval`
against a baseline without the plugin, or paste the prompts into other agents
with and without the skill installed.
