def hook(context):
    headers = context.get("headers") or {}
    headers["X-Request-Trace"] = "example-trace"
    return {"headers": headers}
