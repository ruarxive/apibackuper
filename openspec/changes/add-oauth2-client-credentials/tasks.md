## 1. Configuration
- [x] 1.1 Add `grant_type`, `client_id`, `client_secret`, `client_secret_file`,
      `scope`, `audience` and `client_auth_method` to the schema
- [x] 1.2 Validate the fields required by each grant in `validate-config`

## 2. Token handling
- [x] 2.1 Implement the client-credentials token request with Basic or body
      client authentication, scope and audience
- [x] 2.2 Track token expiry from `expires_in` and refresh 60 seconds before it,
      and after a 401
- [x] 2.3 Add client authentication to refresh-token requests when `client_id` is set
- [x] 2.4 Serialize token refresh with a lock shared by parallel requests
- [x] 2.5 Redact the client secret and tokens in all diagnostics

## 3. Tests and docs
- [x] 3.1 Tests: initial fetch, proactive refresh, 401 refresh, Basic vs body
      client auth, missing secret file, parallel requests issue one token
      request, no secret in logs
- [x] 3.2 Update `docs/docs/configuration/auth.md` and `CHANGELOG.md`
