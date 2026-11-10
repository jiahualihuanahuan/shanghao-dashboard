"""Tiny YAML-subset reader (stdlib only) so the standalone alert script needs no PyYAML.

Supports: comments, top-level `key: scalar`, top-level `key:` followed by a list of flat
mappings (`- k: v` plus indented `k: v`), scalars (str/int/float/bool/null) and inline lists.
Anything fancier -> use PyYAML (the app does for indicators/notes)."""
from __future__ import annotations
import re

_NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def _strip_comment(s: str) -> str:
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(v: str):
    v = v.strip()
    if v == "" or v in ("null", "~", "None"):
        return None
    if (v[0] == v[-1]) and v[0] in "\"'" and len(v) >= 2:
        return v[1:-1]
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in _split_csv(inner)] if inner else []
    if _NUM.match(v):
        return int(v) if re.match(r"^[-+]?\d+$", v) else float(v)
    return v


def _split_csv(s: str):
    parts, cur, q = [], [], None
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur.append(ch)
        elif ch == ",":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _kv(line: str):
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*:\s*(.*)$", line)
    if not m:
        raise ValueError(f"cannot parse line: {line!r}")
    return m.group(1), m.group(2)


def loads(text: str) -> dict:
    root: dict = {}
    cur_key = None      # top-level key owning a list
    cur_item = None
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 0:
            k, v = _kv(body)
            if v == "":
                root[k] = []
                cur_key, cur_item = k, None
            else:
                root[k] = _scalar(v)
                cur_key, cur_item = None, None
        elif body.startswith("- "):
            if cur_key is None:
                raise ValueError(f"list item outside list: {raw!r}")
            rest = body[2:].strip()
            if re.match(r"^[A-Za-z0-9_.\-]+\s*:", rest):
                k, v = _kv(rest)
                cur_item = {k: _scalar(v)}
                root[cur_key].append(cur_item)
            else:
                root[cur_key].append(_scalar(rest))
                cur_item = None
        else:
            if cur_item is None:
                raise ValueError(f"unexpected indentation: {raw!r}")
            k, v = _kv(body)
            cur_item[k] = _scalar(v)
    return root


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return loads(f.read())
