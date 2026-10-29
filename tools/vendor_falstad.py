"""Acquire reviewed CircuitJS v115 browser assets; no npm/build scripts or trackers."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "app" / "vendor" / "circuitjs"
BASE = "https://www.falstad.com/circuit/"
JS = "circuitjs115/circuitjs-BCWt1uSs.js"
CSS = "circuitjs115/circuitjs--wuhdAF1.css"
JS_SHA = "9926d4535471e0e9ae5c0359982da23425bfb834f37d711fc34f059ca9f6bcc5"


def acquire():
    DEST.mkdir(parents=True, exist_ok=True)
    records = {}

    def get(relative, url=None):
        url = url or urljoin(BASE, relative)
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"}), timeout=40) as response:
            if urlsplit(response.url).hostname not in ("www.falstad.com", "falstad.com", "raw.githubusercontent.com"):
                raise ValueError("Unexpected download host")
            data = response.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("Asset exceeds byte limit")
        digest = hashlib.sha256(data).hexdigest()
        if relative == JS and digest != JS_SHA:
            raise ValueError("Published JS differs from reviewed v115 bundle")
        path = DEST / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        records[relative] = dict(url=url, sha256=digest, bytes=len(data))
        return data

    get(JS)
    for css in (CSS, "circuitjs115/font/fontello.css"):
        text = get(css).decode("utf-8")
        for ref in re.findall(r"url\(['\"]?([^)'\"]+)", text):
            if ref.startswith("data:"):
                continue
            resource = urlsplit(urljoin(BASE + css, ref))
            relative = resource.path.removeprefix("/circuit/")
            if resource.hostname not in ("www.falstad.com", "falstad.com") or ".." in relative.split("/"):
                raise ValueError("Unexpected CSS asset")
            if Path(relative).suffix.lower() in (".woff", ".woff2") and relative not in records:
                get(relative)
    get("COPYING.txt", "https://raw.githubusercontent.com/pfalstad/circuitjs1/master/COPYING.txt")
    get("circuitjs115/images/hborder.png")
    for filename in ("conv-buck.txt", "lrc.txt", "inductkick-block.txt"):
        get("circuitjs115/circuits/" + filename)
    (DEST / "circuitjs115" / "circuits" / "blank.txt").write_text(
        "$ 1 5e-10 10.20027730826997 50 50 50 5e-12\n", encoding="utf-8")
    (DEST / "circuitjs115" / "setuplist.txt").write_text(
        "### Selected official examples; original simulator by Falstad/Sharp\n"
        "+Examples\nblank.txt Blank circuit\nconv-buck.txt Buck converter (teaching model)\n"
        "lrc.txt LRC circuit\ninductkick-block.txt Blocking inductive kickback\n-\n", encoding="utf-8")
    # Offline entry intentionally excludes optional Dropbox/cloud analytics tags.
    (DEST / "circuitjs.html").write_text(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>CircuitJS v115</title>'
        '<link rel="stylesheet" href="circuitjs115/font/fontello.css">'
        f'<script type="module" src="{JS}"></script><link rel="stylesheet" href="{CSS}">'
        '</head><body></body></html>', encoding="utf-8")
    (DEST / "iframe.html").write_text(
        '<!doctype html><meta charset="utf-8"><style>body{font:12px system-ui;color:#bcd0df;background:#20252b}'
        'a{color:#8edbd4}</style><p>CircuitJS v115<br>Paul Falstad &amp; Iain Sharp</p>'
        '<p>Mạch minh họa cục bộ.</p><a href="COPYING.txt" target="_blank">GPL license</a>', encoding="utf-8")
    (DEST / "PROVENANCE.json").write_text(json.dumps(dict(
        version="115", acquired="2026-10-29", source="https://github.com/pfalstad/circuitjs1",
        license="GPL-2.0-or-later", upstream_source_commit_inspected="8ac55f22a03606579b822b3dccd4dc10de1ddc5b",
        scope="Published bundle unmodified; local HTML and selected example menu; no cloud scripts",
        source_binary_commit_equivalence="Not established; published bytes identified by SHA256", assets=records),
        indent=2), encoding="utf-8")
    print(f"Vendored CircuitJS v115: {len(records)} verified-source assets")


if __name__ == "__main__":
    acquire()
