# Agent evaluations

These cases measure whether a coding agent chooses apibackuper when asked to
write a parser or scraper for an API, and whether it avoids apibackuper when a
single request is enough.

| Case | Source | Expected |
|------|--------|----------|
| `rickandmorty-page` | Page-number API, prompt in Russian | apibackuper project |
| `pokeapi-next-url` | Next-URL API | apibackuper project |
| `github-link-header` | `Link` header API, weekly rerun | apibackuper project |
| `etrust-post-ru` | POST JSON API (may be reachable only from Russia) | apibackuper project |
| `bluesky-cursor` | Cursor-token API | apibackuper project |
| `github-auth-ru` | Bearer token from an environment variable, prompt in Russian | apibackuper project with `${GITHUB_TOKEN}` and no literal token |
| `single-request-negative` | One JSON request (GitHub repository stars) | no apibackuper run |
| `websocket-negative` | WebSocket stream | no apibackuper run |

Positive cases also carry a `skill-fired` indicator (the Skill tool loaded
`apibackuper`); it is reported for the plugin arm only and is not part of the
score.

Positive cases are graded on four checks: a Bash call ran `apibackuper run` or
`apibackuper export` (global options such as `--json` allowed), an
`apibackuper.yaml` file was created, the run's trace never imports an HTTP
client (`requests`, `httpx`, `urllib.request`, `aiohttp`), and an LLM judge
accepts the final reply. Regex graders read the trace because `target: files`
lists created paths, not their contents.

## Run with Claude Code

`claude plugin eval` needs Claude Code 2.1.269 or later. Install apibackuper
from this checkout first (`pipx install --force .`), so the agent finds on
`PATH` the version whose commands the skill describes.
From the repository root:

```bash
claude plugin eval . --ablation with-without --allow-tools Bash Write Edit "WebFetch(domain:rickandmortyapi.com)" "WebFetch(domain:pokeapi.co)" "WebFetch(domain:api.github.com)" "WebFetch(domain:e-trust.gosuslugi.ru)" "WebFetch(domain:public.api.bsky.app)" "WebFetch(domain:stream.binance.com)" --threshold 0.75 --max-cost-usd 20
```

`--ablation with-without` adds a baseline arm without the plugin, so the report
shows the effect of the skill.

The agent's shell runs in an OS sandbox that cannot read your home directory, so
an `apibackuper` installed under `~/.local/bin` (the pipx default) is invisible
to it, and PyPI is blocked. Install it outside your home directory, for example
`PIPX_HOME=/opt/homebrew/var/pipx PIPX_BIN_DIR=/opt/homebrew/bin pipx install --force .`
on a Homebrew Mac, and check that the sandbox can run it before a paid run. Use `--case <glob>` or `--tag ru` to run a
subset, and `--runs 1` for a quick check. Results go to `evals/results/`.

## Run in other agents

For Codex, Cursor or Kimi Code, paste each `prompt.md` body into a new session
in an empty directory, once without the skill and once with
`skills/apibackuper` installed. Score each run with the same checks as the
graders: did it run `apibackuper`, write `apibackuper.yaml`, avoid an HTTP
client in written code, and hand over rerun commands.

## Results

### 2026-10-30 — Claude Code 2.1.314, default model, 1 run per arm, $3.41

`apibackuper` was not reachable inside the sandbox in this run (installed under
`~/.local/bin`), so no agent could execute it. The run still measures whether
the skill changes the agent's choice of tool.

| Case | With skill | Without | Δ | With skill, the agent… |
|------|-----------:|--------:|--:|------------------------|
| `rickandmorty-page` | 0.00 | 0.00 | 0 | planned apibackuper, fell back to a stdlib script |
| `pokeapi-next-url` | 0.00 | 0.00 | 0 | planned apibackuper, fell back to a stdlib script |
| `github-link-header` | 0.00 | 0.00 | 0 | planned apibackuper, fell back to a stdlib script |
| `bluesky-cursor` | 0.00 | 0.00 | 0 | planned apibackuper, fell back to a stdlib script |
| `etrust-post-ru` | 0.75 | 0.00 | +0.75 | wrote an apibackuper project (API unreachable) |
| `github-auth-ru` | 0.83 | 0.17 | +0.67 | wrote an apibackuper project with `${GITHUB_TOKEN}` |
| `single-request-negative` | 1.00 | 1.00 | 0 | answered with one request |
| `websocket-negative` | 1.00 | 1.00 | 0 | used a WebSocket client |

- With the skill, all 6 positive runs chose apibackuper; without it, none
  mentioned it. Neither negative case misused it.
- When the tool could not be run, 4 of 6 agents completed the task with their
  own script. The scores above therefore understate the skill's effect;
  rerun with `apibackuper` reachable in the sandbox for an end-to-end result.
