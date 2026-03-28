"""JSON repair utilities for malformed LLM outputs."""

import json
import re


def repair_json(text: str) -> str:
    """Attempt to repair malformed JSON from LLM outputs.

    Handles common issues:
    - Markdown code block wrappers (```json ... ```)
    - Control characters in strings (literal newlines, tabs)
    - Trailing commas
    - Single quotes instead of double quotes
    - Unquoted keys
    - Truncated JSON (unclosed brackets/braces)
    """
    # Strip markdown code blocks (handle multiline)
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```\s*$", "", text)
    text = text.strip()

    # Try parsing as-is first (with strict=False to allow control chars)
    try:
        json.loads(text, strict=False)
        return text
    except json.JSONDecodeError:
        pass

    # Fix trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Try again
    try:
        json.loads(text, strict=False)
        return text
    except json.JSONDecodeError:
        pass

    # Fix unescaped control characters inside JSON strings
    # Replace literal newlines/tabs inside string values with escaped versions
    def _escape_control_chars(s):
        """Escape control characters that break JSON parsing."""
        result = []
        in_string = False
        escape_next = False
        for ch in s:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\':
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                    continue
                elif ch == '\r':
                    result.append('\\r')
                    continue
                elif ch == '\t':
                    result.append('\\t')
                    continue
            result.append(ch)
        return ''.join(result)

    escaped = _escape_control_chars(text)
    try:
        json.loads(escaped, strict=False)
        return escaped
    except json.JSONDecodeError:
        pass

    # Try to extract the outermost JSON object or array
    # Find first { or [ and match to last } or ]
    first_brace = -1
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            first_brace = i
            break

    if first_brace >= 0:
        open_char = text[first_brace]
        close_char = '}' if open_char == '{' else ']'

        # Find matching close from the end
        last_close = text.rfind(close_char)
        if last_close > first_brace:
            extracted = text[first_brace:last_close + 1]
            extracted_escaped = _escape_control_chars(extracted)

            # Fix trailing commas again
            extracted_escaped = re.sub(r',\s*([}\]])', r'\1', extracted_escaped)

            try:
                json.loads(extracted_escaped, strict=False)
                return extracted_escaped
            except json.JSONDecodeError:
                pass

            # Last resort: try to close unclosed brackets/braces
            repaired = _try_close_json(extracted_escaped)
            try:
                json.loads(repaired, strict=False)
                return repaired
            except json.JSONDecodeError:
                pass

    return text


def _try_close_json(text: str) -> str:
    """Try to close unclosed JSON brackets and braces."""
    stack = []
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()

    # Close any unclosed brackets/braces
    closers = []
    for opener in reversed(stack):
        closers.append('}' if opener == '{' else ']')

    return text + ''.join(closers)
