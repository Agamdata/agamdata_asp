"""RFC 7807 global exception handler — renders top-level problem+json envelope
for every HTTPException raised within the Gateway.

Per ASP-FEAT-ASP-00 v1.0 §6 and §10, the envelope shape is:
    {type, title, status, detail, instance, request_id}
with Content-Type: application/problem+json.

Registered on the FastAPI app in app/main.py:
    app.add_exception_handler(HTTPException, http_exception_handler)
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

_STATUS_TITLES = {
    400: "Bad Request",
    401: "Unauthorised",
    404: "Not Found",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    504: "Gateway Timeout",
}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Render an RFC 7807 problem+json envelope at the top level of the response body.

    The exc.detail may be:
      - a string  -> used verbatim as `detail`
      - a dict    -> its own `detail` key is lifted; otherwise generic fallback
      - anything else -> generic fallback

    `request_id` is sourced from request.state.request_id when the router has set it
    (post-auth paths). Pre-auth errors (401 on invalid/missing API key, before the
    router assigns a correlation ID) legitimately emit `request_id: null`. This is
    the expected envelope for AC-S5-05; AC-S5-04 verifies the populated case.
    """
    if isinstance(exc.detail, str):
        detail_text = exc.detail
    elif isinstance(exc.detail, dict):
        detail_text = exc.detail.get("detail", "An error occurred")
    else:
        detail_text = "An error occurred"

    headers = {}
    # Preserve headers set on the HTTPException (e.g. Retry-After on 429)
    if exc.headers:
        headers.update(exc.headers)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type":       f"https://asp.internal/errors/{exc.status_code}",
            "title":      _STATUS_TITLES.get(exc.status_code, "Error"),
            "status":     exc.status_code,
            "detail":     detail_text,
            "instance":   str(request.url.path),
            "request_id": getattr(request.state, "request_id", None),
        },
        media_type="application/problem+json",
        headers=headers,
    )
