def hook(context):
    response = context.get("response") or {}
    return {"status_code": response.get("status_code")}
