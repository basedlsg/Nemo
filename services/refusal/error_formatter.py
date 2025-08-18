from fastapi import HTTPException

def create_refusal_exception(code: str, context: dict | None = None, trace_id: str | None = None):
    payload = {
        "error": "refused",
        "code": code,
        "context": context or {},
        "trace_id": trace_id,
    }
    # Use 422 for policy/user errors, 503 for system
    status = 422 if code in {"no_first_party_citation","query_too_vague","language_policy_violation"} else 503
    # NEVER raise anything but HTTPException here
    return HTTPException(status_code=status, detail=payload)
