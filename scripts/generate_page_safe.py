#!/usr/bin/env python3
"""Compatibility wrapper for the dashboard generator.
Normalizes signal fields before delegating to generate_page.py.
"""
import generate_page as page

_original_tags = page.tags


def safe_tags(items, cls="default-tag"):
    if isinstance(items, dict):
        normalized = []
        for key, value in items.items():
            if value in (None, "", False):
                normalized.append(str(key))
            elif isinstance(value, (dict, list, tuple)):
                normalized.append(f"{key}: {value}")
            else:
                normalized.append(f"{key}: {value}")
        items = normalized
    elif items is None:
        items = []
    elif isinstance(items, (str, int, float, bool)):
        items = [items]
    elif not isinstance(items, (list, tuple, set)):
        items = [str(items)]
    return _original_tags(items, cls)


page.tags = safe_tags

if __name__ == "__main__":
    page.run()
