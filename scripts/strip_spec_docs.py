#!/usr/bin/env python3
"""Strip doc strings from a Soroban wasm's contractspecv0 section.

Soroban embeds `///` doc comments in the contract spec, which pushes the
escrow wasm past the network's 128 KiB contract size limit. This keeps the
full interface (functions, types, errors, events) and only blanks the docs.

Usage: python3 scripts/strip_spec_docs.py <in.wasm> <out.wasm>
Requires the `stellar` CLI on PATH.
"""
import json, subprocess, sys

def leb_read(d, i):
    r = s = 0
    while True:
        b = d[i]; i += 1; r |= (b & 0x7F) << s; s += 7
        if b < 0x80:
            return r, i

def leb_write(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b); return bytes(out)

def blank_docs(o):
    if isinstance(o, dict):
        return {k: ("" if k == "doc" else blank_docs(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [blank_docs(v) for v in o]
    return o

def strip(payload):
    js = subprocess.run(["stellar", "xdr", "decode", "--type", "ScSpecEntry", "--input", "stream", "--output", "json"],
                        input=payload, capture_output=True, check=True).stdout.decode()
    out = bytearray()
    for line in js.splitlines():
        if not line.strip():
            continue
        e = json.dumps(blank_docs(json.loads(line)))
        out += subprocess.run(["stellar", "xdr", "encode", "--type", "ScSpecEntry", "--input", "json", "--output", "single"],
                              input=e.encode(), capture_output=True, check=True).stdout
    return bytes(out)

def main(src, dst):
    d = open(src, "rb").read()
    out = bytearray(d[:8]); i = 8
    while i < len(d):
        sid = d[i]; size, j = leb_read(d, i + 1); body = d[j:j + size]
        if sid == 0:
            nl, k = leb_read(body, 0); name = body[k:k + nl]
            if name == b"contractspecv0":
                body = body[:k + nl] + strip(body[k + nl:])
        out.append(sid); out += leb_write(len(body)); out += body
        i = j + size
    open(dst, "wb").write(out)
    print(f"{src}: {len(d)} -> {dst}: {len(out)} bytes")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
