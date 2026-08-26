#!/usr/bin/env python3
"""Normalize browser-side data URLs for GitHub Pages.

The dashboard is served from /seven-factor-stock-picker/ rather than the
repository root. Use raw.githubusercontent.com as the primary candidate-data
source and keep the local Pages path as a fallback.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "index.html"

PRIMARY = "https://raw.githubusercontent.com/ethanjiang1008-lgtm/seven-factor-stock-picker/main/data/seven_factor_latest.json"
LOCAL = "./data/seven_factor_latest.json"

text = OUT.read_text(encoding="utf-8")
text = text.replace("fetch('data/seven_factor_latest.json')", f"fetch('{PRIMARY}').catch(() => fetch('{LOCAL}'))")
text = text.replace('fetch("data/seven_factor_latest.json")', f"fetch('{PRIMARY}').catch(() => fetch('{LOCAL}'))")
OUT.write_text(text, encoding="utf-8")
print(f"[Dashboard paths] patched {OUT}")
