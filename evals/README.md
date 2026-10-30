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
| `single-request-negative` | One JSON request | no apibackuper run |
| `websocket-negative` | WebSocket stream | no apibackuper run |

Positive cases are graded on four checks: a Bash call ran `apibackuper run` or
`apibackuper export`, an `apibackuper.yaml` file was written, no written file
imports an HTTP client, and an LLM judge accepts the final reply.

## Run with Claude Code

`claude plugin eval` needs Claude Code 2.1.269 or later. Install apibackuper
from this checkout first (`pipx install --force .`), so the agent finds on
`PATH` the version whose commands the skill describes.
From the repository root:

```bash
claude plugin eval . --ablation with-without --allow-tools Bash Write Edit "WebFetch(domain:rickandmortyapi.com)" "WebFetch(domain:pokeapi.co)" "WebFetch(domain:api.github.com)" "WebFetch(domain:e-trust.gosuslugi.ru)" "WebFetch(domain:www.cbr-xml-daily.ru)" "WebFetch(domain:public.api.bsky.app)" "WebFetch(domain:stream.binance.com)" --threshold 0.75 --max-cost-usd 20
```

`--ablation with-without` adds a baseline arm without the plugin, so the report
shows the effect of the skill. Use `--case <glob>` or `--tag ru` to run a
subset, and `--runs 1` for a quick check. Results go to `evals/results/`.

## Run in other agents

For Codex, Cursor or Kimi Code, paste each `prompt.md` body into a new session
in an empty directory, once without the skill and once with
`skills/apibackuper` installed. Score each run with the same checks as the
graders: did it run `apibackuper`, write `apibackuper.yaml`, avoid an HTTP
client in written code, and hand over rerun commands.
