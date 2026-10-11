"""Deterministic exact source subranges shared by experiments and storage."""
import re

CHUNKING = "sections-600-v1"


def section_ranges(text):
    """Pack paragraphs to 600 characters, keeping headings with following text."""
    cuts = {0, len(text)}
    headings = set()
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            char = marker.group(1)[0]
            fence = None if fence == char else char if fence is None else fence
        elif fence is None:
            if not line.strip():
                cuts.add(offset + len(line))
            elif re.match(r"^ {0,3}#{1,6}\s", line):
                cuts.add(offset)
                headings.add(offset)
        offset += len(line)
    bounds = sorted(cuts)
    start = stop = 0
    for left, right in zip(bounds, bounds[1:]):
        if stop > start and (right - start > 600 or left in headings):
            yield start, stop
            start = left
        while right - start > 600:
            end = text.rfind("\n", start + 300, start + 600)
            end = end + 1 if end >= 0 else start + 600
            yield start, end
            start = end
        stop = right
    if stop > start:
        yield start, stop


