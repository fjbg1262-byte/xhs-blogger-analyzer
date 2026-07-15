"""Cookie format conversion utilities."""

import json


def cookies_array_to_dict(cookies_str_or_array) -> str:
    """Convert cookie array (Playwright format) to dict string for Spider_XHS.

    Accepts either a JSON string or a Python list of cookie dicts.
    Returns a semi-colon joined cookie string.
    """
    if isinstance(cookies_str_or_array, str):
        try:
            cookies = json.loads(cookies_str_or_array)
        except json.JSONDecodeError:
            # Already a plain cookie string
            return cookies_str_or_array
    else:
        cookies = cookies_str_or_array

    if isinstance(cookies, list):
        parts = []
        seen = set()
        for c in cookies:
            name = c.get("name", "")
            value = c.get("value", "")
            if name and name not in seen:
                parts.append(f"{name}={value}")
                seen.add(name)
        return "; ".join(parts)

    if isinstance(cookies, dict):
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    return str(cookies)


def extract_a1(cookie_str: str) -> str:
    """Extract the a1 token from a cookie string."""
    for part in cookie_str.split(";"):
        part = part.strip()
        if part.startswith("a1="):
            return part[3:]
    return ""
