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

### 2026-10-30, run 2 — end to end ($3.59)

Claude Code 2.1.314, default model, 1 run per arm, `apibackuper` from this
branch installed in `/opt/homebrew/bin` so the sandboxed agent can run it.

| Case | With skill | Without | Δ | Notes |
|------|-----------:|--------:|--:|-------|
| `rickandmorty-page` | 1.00 | 0.00 | +1.00 | |
| `bluesky-cursor` | 1.00 | 0.00 | +1.00 | |
| `github-link-header` | 0.75 | 0.00 | +0.75 | Collected all 98 repos; judge wanted rerun commands, not a wrapper script (criterion since relaxed) |
| `pokeapi-next-url` | 0.75 | 0.00 | +0.75 | Agent added a follow rule for 1,351 detail pages and hit the 900 s timeout |
| `etrust-post-ru` | 0.75 | 0.00 | +0.75 | Valid project; API unreachable from outside Russia; a debugging `urllib.request` call tripped `no-http-loop` |
| `github-auth-ru` | 0.83 | 1.00 | −0.17 | With the skill the agent did not run without a token; the baseline found the installed `apibackuper` on `PATH` |
| `single-request-negative` | 1.00 | 1.00 | 0 | |
| `websocket-negative` | 1.00 | 1.00 | 0 | |

- Mean over positive cases: 0.85 with the skill, 0.17 without.
- `apibackuper` ran in 5 of 6 positive cases with the skill and in 1 of 6
  without; the skill loaded in all 6. Neither negative case misused it.
- Without the skill, agents wrote their own scraper in 5 of 6 cases.

### 2026-10-30, run 1 — tool choice only ($3.41)

`apibackuper` was installed under `~/.local/bin`, which the sandbox cannot read.
With the skill all 6 positive runs chose apibackuper (2 wrote a project, 4 fell
back to a script after failing to run it); without it none mentioned it.
