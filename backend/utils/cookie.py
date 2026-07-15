"""Cookie format conversion and validation utilities."""

import binascii
import json
import random
import time


REQUIRED_COOKIE_KEYS = {"web_session"}
OPTIONAL_COOKIE_KEYS = {"a1"}
_A1_CHARSET = "abcdefghijklmnopqrstuvwxyz1234567890"

ERR_EMPTY_COOKIE = "\u767b\u5f55\u51ed\u8bc1\u4e0d\u80fd\u4e3a\u7a7a\u3002\u8bf7\u7c98\u8d34\u63d2\u4ef6\u5bfc\u51fa\u7684\u5b8c\u6574\u5185\u5bb9\uff0c\u6216\u5bfc\u5165\u63d2\u4ef6\u5bfc\u51fa\u7684\u6587\u4ef6\u3002"
ERR_JSON_ARRAY = "\u767b\u5f55\u51ed\u8bc1\u6587\u4ef6\u683c\u5f0f\u770b\u8d77\u6765\u4e0d\u5b8c\u6574\u3002\u8bf7\u5728\u63d2\u4ef6\u91cc\u5bfc\u51fa xiaohongshu.com \u7684\u5168\u90e8\u5185\u5bb9\u3002"
ERR_UNSUPPORTED = "\u65e0\u6cd5\u8bc6\u522b\u8fd9\u4efd\u767b\u5f55\u51ed\u8bc1\u3002\u8bf7\u76f4\u63a5\u7c98\u8d34\u63d2\u4ef6\u5bfc\u51fa\u7684\u5b8c\u6574\u5185\u5bb9\uff0c\u6216\u5bfc\u5165\u63d2\u4ef6\u5bfc\u51fa\u7684\u6587\u4ef6\u3002"
ERR_MISSING_PREFIX = "\u767b\u5f55\u51ed\u8bc1\u4e0d\u5b8c\u6574\uff0c\u7f3a\u5c11\uff1a"
ERR_MISSING_SUFFIX = "\u3002\u8bf7\u5148\u5728\u540c\u4e00\u4e2a\u6d4f\u89c8\u5668\u91cc\u767b\u5f55\u5c0f\u7ea2\u4e66\uff0c\u518d\u7528\u63d2\u4ef6\u91cd\u65b0\u5bfc\u51fa\u3002"


def cookies_array_to_dict(cookies_str_or_array):
    """Normalize supported cookie inputs to a semicolon-joined cookie string."""
    if isinstance(cookies_str_or_array, str):
        s = cookies_str_or_array.strip().strip('"').strip("'")
        if not s:
            raise ValueError(ERR_EMPTY_COOKIE)
        if s.lower().startswith("cookie:"):
            s = s.split(":", 1)[1].strip()
        if s.startswith("["):
            try:
                cookies = json.loads(s)
            except json.JSONDecodeError:
                raise ValueError(ERR_JSON_ARRAY)
        elif s.startswith("{"):
            try:
                cookies = json.loads(s)
            except json.JSONDecodeError:
                _validate_cookie_string(s)
                return _with_generated_a1(_rebuild_cookie_string(s))
        else:
            if "\t" in s and "\n" in s:
                result = _parse_netscape_cookie_file(s)
                _validate_cookie_string(result)
                return _with_generated_a1(result)
            _validate_cookie_string(s)
            return _with_generated_a1(_rebuild_cookie_string(s))
    else:
        cookies = cookies_str_or_array

    if isinstance(cookies, list):
        parts = []
        seen = set()
        for c in cookies:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", "")).strip()
            value = str(c.get("value", "")).strip()
            if name and name not in seen:
                parts.append(f"{name}={value}")
                seen.add(name)
        result = "; ".join(parts)
        _validate_cookie_string(result)
        return _with_generated_a1(result)

    if isinstance(cookies, dict):
        for key in ("cookies", "cookie", "data"):
            nested = cookies.get(key)
            if isinstance(nested, (list, dict, str)):
                return cookies_array_to_dict(nested)
        result = "; ".join(f"{str(k).strip()}={str(v).strip()}" for k, v in cookies.items())
        _validate_cookie_string(result)
        return _with_generated_a1(result)

    raise ValueError(ERR_UNSUPPORTED)


def _validate_cookie_string(cookie_str: str):
    """Verify that required login-session fields are present and non-empty."""
    parts = _cookie_parts(cookie_str)
    keys = {k for k, v in parts.items() if v}
    missing = REQUIRED_COOKIE_KEYS - keys
    if missing:
        raise ValueError(ERR_MISSING_PREFIX + ", ".join(sorted(missing)) + ERR_MISSING_SUFFIX)


def _rebuild_cookie_string(cookie_str: str) -> str:
    """Rebuild a clean semicolon-joined cookie string."""
    parts = _cookie_parts(cookie_str)
    return "; ".join(f"{k}={v}" for k, v in parts.items())


def _cookie_parts(cookie_str: str) -> dict[str, str]:
    parts = {}
    for p in cookie_str.split(";"):
        if "=" in p:
            k, v = p.split("=", 1)
            key = k.strip()
            if key and key not in parts:
                parts[key] = v.strip()
    return parts


def _parse_netscape_cookie_file(cookie_text: str) -> str:
    """Parse Netscape/curl cookie export format."""
    parts = []
    seen = set()
    for line in cookie_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 7:
            continue
        domain, name, value = cols[0], cols[5].strip(), cols[6].strip()
        if "xiaohongshu.com" in domain and name and name not in seen:
            parts.append(f"{name}={value}")
            seen.add(name)
    return "; ".join(parts)


def _with_generated_a1(cookie_str: str) -> str:
    parts = _cookie_parts(cookie_str)
    if not parts.get("a1"):
        parts["a1"] = generate_a1()
    return "; ".join(f"{k}={v}" for k, v in parts.items())


def generate_a1() -> str:
    ts_hex = hex(int(time.time() * 1000))[2:]
    random_str = "".join(random.choices(_A1_CHARSET, k=30))
    a_part = ts_hex + random_str + "5" + "0" + "000"
    crc = binascii.crc32(a_part.encode()) & 0xFFFFFFFF
    return (a_part + str(crc))[:52]


def extract_a1(cookie_str: str) -> str:
    """Extract the a1 token from a cookie string."""
    return _cookie_parts(cookie_str).get("a1", "")
