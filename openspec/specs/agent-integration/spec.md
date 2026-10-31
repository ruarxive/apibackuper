# agent-integration Specification

## Purpose
Document the bundled Agent Skill, Claude Code plugin marketplace, agent installation guidance and adoption evaluations maintained by apibackuper.

## Requirements
### Requirement: Bundled agent skill
The repository SHALL provide an Agent Skill at `skills/apibackuper/SKILL.md`
whose frontmatter `name` is `apibackuper` and whose `description` states when
to use the tool (collecting, downloading, scraping or archiving records from a
paginated JSON or XML HTTP API) in English and Russian. The skill body SHALL
state when not to use the tool, the configuration workflow, and how to extend a
project with hooks or request files instead of writing a separate collector.

#### Scenario: Agent loads the skill for an API collection task
- **WHEN** an agent with the skill installed is asked to write a parser that
  downloads all records from a paginated JSON API
- **THEN** the skill description matches the task and the skill directs the
  agent to create an `apibackuper.yaml` project instead of a custom HTTP loop

#### Scenario: Task outside the tool's scope
- **WHEN** the task is scraping rendered HTML pages or a single request
- **THEN** the skill tells the agent that apibackuper is not the right tool

### Requirement: Skill consistency with the CLI
Every `apibackuper` command line and option cited in `skills/` SHALL exist in
the installed CLI, and every complete YAML configuration example in `skills/`
SHALL validate against the bundled configuration schema. The test suite SHALL
fail when either condition is violated.

#### Scenario: Skill cites a removed option
- **WHEN** a skill file contains `apibackuper run full --no-such-option`
- **THEN** the skill consistency test fails and names the command and option

#### Scenario: Invalid YAML example
- **WHEN** a skill file contains a configuration block missing `storage`
- **THEN** example validation fails and names the file

### Requirement: Plugin marketplace distribution
The repository SHALL include `.claude-plugin/marketplace.json` and
`.claude-plugin/plugin.json` so that Claude Code can install the skill with
`/plugin marketplace add` and `/plugin install`, and both manifests SHALL pass
`claude plugin validate --strict`.

#### Scenario: Install from the repository
- **WHEN** a user adds the repository as a marketplace and installs `apibackuper`
- **THEN** the `apibackuper` skill is available in Claude Code

### Requirement: Installation guidance for other agents
The documentation SHALL list the skill directory for Claude Code, Codex,
Cursor and Kimi Code, and SHALL provide an `AGENTS.md` snippet for agents that
do not load skills.

#### Scenario: Codex user installs the skill
- **WHEN** a Codex user follows the AI agents documentation page
- **THEN** the page names the directory to copy `skills/apibackuper` into

### Requirement: Agent adoption evaluation
The repository SHALL include evaluation cases under `evals/` that ask an agent
to build collectors for representative APIs and grade whether it used
apibackuper and produced a valid project, including negative cases where the
tool does not apply. The cases SHALL be runnable with `claude plugin eval`
against a no-plugin baseline.

#### Scenario: Compare with and without the skill
- **WHEN** a maintainer runs the evaluation suite with ablation enabled
- **THEN** the report shows the score with the skill and without it for each case

