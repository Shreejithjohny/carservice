"""
Matches text read from a number plate photo (OCR) against the registration number on the booking.

OCR engines often confuse characters that look alike (0/O, 1/I, 5/S, 8/B ...), so those are treated
as equal, and a single remaining wrong, missing or extra character still counts as a likely match.
"""
import re

# Characters OCR commonly mixes up on number plates; each group is treated as one character.
LOOKALIKE_GROUPS = ["0ODQ", "1IL", "5S", "8B", "2Z", "6G"]
_CANONICAL = {ch: group[0] for group in LOOKALIKE_GROUPS for ch in group}

# Standard Indian plates (KA01AB1234, DL3CAB1234) and Bharat series (22BH1234AA).
PLATE_PATTERN = re.compile(r"[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}|\d{2}BH\d{4}[A-Z]{1,2}")

MATCH = "MATCH"
LIKELY = "LIKELY_MATCH"
MISMATCH = "MISMATCH"
NO_TEXT = "NO_TEXT"


def normalize(text: str) -> str:
    """Uppercase and keep only letters and digits (drops spaces, dashes, the IND hologram text, etc.)."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def canonical(text: str) -> str:
    return "".join(_CANONICAL.get(ch, ch) for ch in text)


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def best_window(ocr_text: str, expected: str):
    """The stretch of OCR text closest to the expected plate, and its edit distance (after lookalike folding)."""
    target = canonical(expected)
    best, best_dist = "", len(target)
    # OCR output may hold other text (dealer name, "IND"), so try every window of plausible length.
    for line in [ocr_text] + ocr_text.splitlines():
        text = normalize(line)
        for size in {len(target) - 1, len(target), len(target) + 1}:
            if size <= 0:
                continue
            for start in range(0, max(1, len(text) - size + 1)):
                window = text[start:start + size]
                dist = edit_distance(canonical(window), target)
                if dist < best_dist or (dist == best_dist and not best):
                    best, best_dist = window, dist
    return best, best_dist


def check_plate(ocr_text: str, registration_number: str) -> dict:
    expected = normalize(registration_number)
    if not normalize(ocr_text):
        return {"result": NO_TEXT, "detected": "", "expected": expected}

    window, dist = best_window(ocr_text, expected)
    if dist == 0:
        result = MATCH
    elif dist == 1 and len(expected) >= 6:
        result = LIKELY
    else:
        result = MISMATCH
        # Report what does look like a plate, so the driver can see what was read.
        found = PLATE_PATTERN.search(normalize(ocr_text))
        window = found.group(0) if found else normalize(ocr_text)[:12]
    return {"result": result, "detected": window, "expected": expected}
