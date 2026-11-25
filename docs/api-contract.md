# API contract: Milestone 1

## `GET /api/health`

Returns service status and the configured runtime mode. No authentication or provider credentials are required.

```json
{
  "status": "ok",
  "service": "medicall-api",
  "mode": "demo"
}
```

`mode` is `demo` in this milestone because no external voice provider is integrated. Future dashboard copy must preserve this distinction and must not call it a live AI call.
