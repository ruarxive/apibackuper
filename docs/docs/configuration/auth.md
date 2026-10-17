---
title: "Authentication"
description: "Basic, Bearer, API Key, and OAuth2 configuration"
---
# Authentication

```yaml
auth:
  type: bearer   # basic | bearer | apikey | oauth2
```

Prefer `*_file` fields over inline secrets.

YAML values can also read credentials from the process environment:

```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

Export the variable in your shell before running the CLI. An unset or empty
required variable stops configuration loading. `run full` reports it with status
2; `validate-config` and offline plans fail validation with status 1. `${VAR:-default}`
uses its default when the variable is unset or empty; use defaults for
non-sensitive settings. A `.env` file is not loaded automatically.

## Basic

```yaml
auth:
  type: basic
  username: myuser
  password_file: /path/to/password.txt
```

## Bearer

```yaml
auth:
  type: bearer
  token_file: /path/to/token.txt
```

## API key

```yaml
auth:
  type: apikey
  api_key: your_api_key_here
  api_key_header: X-API-Key   # default
```

## OAuth2

```yaml
auth:
  type: oauth2
  token: your_access_token
  auth_url: https://api.example.com/oauth/token
  refresh_token: your_refresh_token
```

Template: `examples/templates/bearer-auth.yaml`. See also
[protected APIs](/use-cases/protected-apis).
