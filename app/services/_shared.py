"""Shared utilities for service handlers."""
import re
import anthropic
from app.config import settings
from app.models.request import ConversationTurn, InvokeRequest
from app.models.response import InvokeResponse, ResponseMeta
from app.cost.meter import calculate_cost


def strip_json(raw: str) -> str:
    """Extract a JSON object/array from an LLM response.

    Handles three patterns Claude emits:
      1. Clean JSON          {  ...  }
      2. Fenced JSON         ```json\\n{...}\\n```
      3. Prose + fenced JSON  # Analysis\\n...\\n```json\\n{...}\\n```

    For case 3 the fence is not at position 0, so anchor-based regexes fail.
    After fence removal, we scan forward to the first { or [ so that any
    leading prose, headers, or explanation text is discarded.
    """
    text = raw.strip()

    # Step 1: remove opening fence (``` or ```json) wherever it appears
    text = re.sub(r"```(?:json)?\s*", "", text)
    # Step 2: remove closing fence
    text = re.sub(r"\s*```", "", text)
    text = text.strip()

    # Step 3: if the result still has prose before the JSON object, discard it.
    # Find the first { or [ — everything before it is preamble.
    first_brace = len(text)
    for ch in ('{', '['):
        idx = text.find(ch)
        if idx != -1 and idx < first_brace:
            first_brace = idx
    if first_brace > 0:
        text = text[first_brace:]

    return text.strip()


# Language labels Claude may emit as a bare first line (no backticks)
_BARE_LANG_RE = re.compile(
    r"^(?:typescript|javascript|python|ts|js|py)\s*\n",
    re.IGNORECASE,
)


def strip_script(raw: str) -> str:
    """Strip code fences and bare language labels from LLM-generated code.

    Handles two forms Claude uses:
      1. Fenced:  ```typescript\\n...\\n```
      2. Bare:    typescript\\nimport ...   (no backticks, label on its own line)
    """
    text = raw.strip()
    # Remove ```<lang> ... ``` fences (opening fence with optional language tag)
    text = re.sub(r"^```\w*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    # Remove bare language label on first line
    text = _BARE_LANG_RE.sub("", text)
    return text.strip()


_VALID_JSON_ESCAPES = set('"\\\/bfnrtu')
_JS_EXPR_PATTERNS = [
    # "x".repeat(n)  →  "xxx..." (n chars of x)
    (re.compile(r'"(.)"\s*\.\s*repeat\s*\(\s*(\d+)\s*\)'), lambda m: f'"{m.group(1) * int(m.group(2))}"'),
    # "x".repeat(n) outside quotes (bare)
    (re.compile(r"'(.)'\s*\.\s*repeat\s*\(\s*(\d+)\s*\)"), lambda m: f'"{m.group(1) * int(m.group(2))}"'),
    # Array(n+1).join("x")  →  "xxx..."
    (re.compile(r'Array\s*\(\s*(\d+)\s*\+?\s*1?\s*\)\s*\.\s*join\s*\(\s*["\'](.)["\']'), lambda m: f'"{m.group(2) * int(m.group(1))}"'),
    # "x".padStart(n, "y")  →  actual padded string
    (re.compile(r'"([^"]*)"\s*\.\s*padStart\s*\(\s*(\d+)\s*(?:,\s*"([^"]*)")?\s*\)'), lambda m: f'"{m.group(1).rjust(int(m.group(2)), m.group(3) or " ")}"'),
]


def repair_json(raw: str) -> str:
    """
    Two-pass repair for LLM-generated JSON:
    Pass 1 — fix invalid escape sequences (e.g. \' \( \. that Claude sometimes emits).
    Pass 2 — close any unclosed arrays/objects caused by max_tokens truncation.
    """
    text = strip_json(raw)

    # --- Pass 0: replace JS expressions that Claude emits as values ---
    for pattern, replacement in _JS_EXPR_PATTERNS:
        text = pattern.sub(replacement, text)

    # --- Pass 1: fix invalid escape sequences inside JSON strings ---
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"' and (i == 0 or text[i - 1] != '\\'):
            in_string = not in_string
            result.append(ch)
        elif ch == '\\' and in_string:
            next_ch = text[i + 1] if i + 1 < len(text) else ''
            if next_ch in _VALID_JSON_ESCAPES:
                result.append(ch)
                result.append(next_ch)
                i += 2
                continue
            else:
                # Drop the invalid backslash, keep the character
                result.append(next_ch)
                i += 2
                continue
        else:
            result.append(ch)
        i += 1
    text = ''.join(result)

    # --- Pass 2: close unclosed brackets (truncation) ---
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace = max(0, depth_brace - 1)
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket = max(0, depth_bracket - 1)

    if in_string:
        text += '"'
    text += ']' * depth_bracket
    text += '}' * depth_brace
    return text

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
anthropic_client_sync = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def build_messages(
    history: list[ConversationTurn],
    current_user_message: str,
) -> list[dict]:
    messages = []
    for turn in history:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": current_user_message})
    return messages


def build_invoke_response(
    request_id: str,
    service_type: str,
    task: str,
    output,
    usage,
    model: str,
    latency_ms: int = 0,
) -> InvokeResponse:
    input_tokens = usage.input_tokens if hasattr(usage, "input_tokens") else 0
    output_tokens = usage.output_tokens if hasattr(usage, "output_tokens") else 0
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    result = output.model_dump() if hasattr(output, "model_dump") else output

    return InvokeResponse(
        request_id=request_id,
        service_type=service_type,
        task=task,
        result=result,
        meta=ResponseMeta(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        ),
    )
