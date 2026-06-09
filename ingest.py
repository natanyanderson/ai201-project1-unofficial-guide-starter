"""
Ingestion + chunking for the Mercy CS RAG project.

Loads raw files from data/raw/, cleans them, and chunks them per the
source-aware strategy in planning.md (overlap = 0, one semantic unit per chunk):

    RMP          -> 1 review  = 1 chunk
    Coursicle    -> 1 course  = 1 chunk
    Catalog      -> 1 course  = 1 chunk
    Requirements -> 1 semester = 1 chunk   (PDF, column-aware)

Output: a list of dicts shaped {text, source_url, metadata}.

Run:  python ingest.py
"""

from __future__ import annotations

import glob
import os
import re
from typing import Any

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

RAW_DIR = "data/raw"

# Base source URLs from planning.md "Documents" table.
COURSICLE_BASE_URL = "https://www.coursicle.com/mercy/courses/CISC/"
CATALOG_URL = "https://ug.catalog.mercy.edu/courses?page=1&cq=computer+science"
REQUIREMENTS_URL = "https://mercy.edu/media/2024-2025-bs-computer-science"

# The degree-requirements PDF is a two-up layout: two semesters printed
# side by side (Fall on the left half of the page, Spring on the right).
# Each page is split into this many vertical strips before table extraction
# so the two semesters never get concatenated onto the same row. Set to 1
# for a single-column requirements sheet.
REQ_PAGE_COLUMNS = 2

# Map professor name -> RMP profile URL (planning.md Documents table).
# The .txt files don't carry the URL, so we look it up by professor name.
RMP_URLS = {
    "Samer Almazahreh": "https://www.ratemyprofessors.com/professor/1725736",
    "John Marchan":      "https://www.ratemyprofessors.com/professor/2575199",
    "Sisi Li":           "https://www.ratemyprofessors.com/professor/3120865",
    "Marion Ben-Jacob":  "https://www.ratemyprofessors.com/professor/789013",
    "Brian Landin":      "https://www.ratemyprofessors.com/professor/2909340",
    "Angelo Ordonez":    "https://www.ratemyprofessors.com/professor/2206397",
    "Yun Wang":          "https://www.ratemyprofessors.com/professor/1817836",
}

COURSE_CODE_RE = re.compile(r"\b([A-Z]{3,4})\s?-?\s?(\d{3})\b")
# Matches only when a course code is at the very start of a line (a real course
# row), used to tell course rows apart from wrapped-cell continuations.
_STARTS_WITH_CODE = re.compile(r"^\s*[A-Z]{3,4}\s?-?\s?\d{3}\b")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def clean_text(s: str) -> str:
    """Normalize whitespace and strip scrape noise we know shows up."""
    if not s:
        return ""
    # Coursicle dumps occasionally prefix descriptions with this label.
    s = s.replace("Section information text:", " ")
    s = s.replace("\xa0", " ")           # non-breaking spaces
    s = re.sub(r"[ \t]+", " ", s)        # collapse runs of spaces/tabs
    s = re.sub(r"\n{3,}", "\n\n", s)     # collapse big blank gaps
    # Trim trailing/leading whitespace per line, drop empty edge lines.
    lines = [ln.strip() for ln in s.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def split_blocks(raw: str) -> list[str]:
    """Split a file on standalone '---' separator lines."""
    parts = re.split(r"(?m)^\s*-{3,}\s*$", raw)
    return [p.strip() for p in parts if p.strip()]


def parse_kv(block: str) -> tuple[dict[str, str], str]:
    """
    Parse leading 'Key: value' lines into a dict.
    Returns (fields, leftover_text) where leftover_text is any non-kv tail.
    """
    fields: dict[str, str] = {}
    leftover: list[str] = []
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z /]*?):\s*(.*)$", line)
        if m and m.group(1).strip() in {
            "Source", "Professor", "School", "Department",
            "Course", "Title", "Description", "Prerequisites",
            "Credits", "Recent Professors", "Recent Semesters",
        }:
            fields[m.group(1).strip()] = m.group(2).strip()
        else:
            leftover.append(line)
    return fields, "\n".join(leftover).strip()


# --------------------------------------------------------------------------- #
# 1. Rate My Professors  (1 review = 1 chunk)
# --------------------------------------------------------------------------- #

def ingest_rmp(rmp_dir: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(rmp_dir, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()

        blocks = split_blocks(raw)
        if not blocks:
            continue

        # First block is the header (Professor / School / Department).
        header, _ = parse_kv(blocks[0])
        professor = header.get("Professor", "Unknown").strip()
        source_url = RMP_URLS.get(professor, "")

        for block in blocks[1:]:
            # Strip the "Review N:" label; keep the body.
            body = re.sub(r"^\s*Review\s+\d+\s*:\s*", "", block).strip()
            body = clean_text(body)
            if not body:
                continue
            # Prepend professor name so the embedding ties the opinion to a
            # person (helps "how is professor X" queries). Still one review.
            text = f"Student review of Professor {professor} (Mercy University):\n{body}"
            chunks.append({
                "text": text,
                "source_url": source_url,
                "metadata": {"source_type": "rmp", "professor": professor},
            })
    return chunks


# --------------------------------------------------------------------------- #
# 2. Coursicle  (1 course = 1 chunk)
# --------------------------------------------------------------------------- #

def _split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def ingest_coursicle(coursicle_dir: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(coursicle_dir, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()

        for block in split_blocks(raw):
            fields, _ = parse_kv(block)
            if "Course" not in fields:          # skips the "Source:" header block
                continue

            code = fields.get("Course", "").strip()
            title = fields.get("Title", "").strip()
            professors = _split_list(fields.get("Recent Professors", ""))
            semesters = _split_list(fields.get("Recent Semesters", ""))
            credits = fields.get("Credits", "").strip()
            desc = clean_text(fields.get("Description", ""))

            # Build a self-contained chunk so retrieval has full context.
            text = (
                f"{code} {title} ({credits} credits)\n"
                f"Recently taught by: {', '.join(professors) or 'N/A'}\n"
                f"Recently offered: {', '.join(semesters) or 'N/A'}\n"
                f"{desc}"
            ).strip()

            # Per-course URL (Coursicle uses the trailing course number).
            num = code.replace("CISC", "").strip()
            source_url = f"{COURSICLE_BASE_URL}{num}/" if num else COURSICLE_BASE_URL

            chunks.append({
                "text": text,
                "source_url": source_url,
                "metadata": {
                    "source_type": "coursicle",
                    "course_code": code,
                    "course_title": title,
                    "professors": professors,
                },
            })
    return chunks


# --------------------------------------------------------------------------- #
# 3. Catalog  (1 course = 1 chunk)
# --------------------------------------------------------------------------- #

def ingest_catalog(catalog_dir: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(catalog_dir, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()

        for block in split_blocks(raw):
            fields, _ = parse_kv(block)
            if "Course" not in fields:          # skips "Source:" header block
                continue

            code = fields.get("Course", "").strip()
            title = fields.get("Title", "").strip()
            credits = fields.get("Credits", "").strip()
            desc = clean_text(fields.get("Description", ""))
            prereqs = clean_text(fields.get("Prerequisites", "")) or "None"

            text = (
                f"{code} {title} ({credits} credits)\n"
                f"Prerequisites: {prereqs}\n"
                f"{desc}"
            ).strip()

            chunks.append({
                "text": text,
                "source_url": CATALOG_URL,
                "metadata": {
                    "source_type": "catalog",
                    "course_code": code,
                    "prereqs": prereqs,
                },
            })
    return chunks


# --------------------------------------------------------------------------- #
# 4. Requirements PDF  (1 semester = 1 chunk, column-aware)
# --------------------------------------------------------------------------- #
#
# See Anticipated Challenge #4: pdfplumber's plain .extract_text() reads in
# visual reading order and scrambles multi-column tables, bunching prereqs/
# coreqs onto course codes. We avoid that by extracting STRUCTURE, not text:
#
#   (a) Try page.extract_tables() so cells stay in their own columns.
#   (b) Fall back to word-level clustering (extract_words) when there are no
#       ruling lines: group words into rows by their y-coordinate, then sort
#       each row left-to-right by x so columns can't interleave.
#
# We then walk the rows, detect semester headers, and accumulate the rows
# under each header into one semester block = one chunk.

# Semester labels normalized to the planning.md form: "Year N Fall/Spring".
_YEAR_WORDS = {
    "first": 1, "1": 1, "freshman": 1, "i": 1,
    "second": 2, "2": 2, "sophomore": 2, "ii": 2,
    "third": 3, "3": 3, "junior": 3, "iii": 3,
    "fourth": 4, "4": 4, "senior": 4, "iv": 4,
}
_TERM_RE = re.compile(r"\b(fall|spring|summer|winter)\b", re.I)
_YEAR_RE = re.compile(
    r"\b(first|second|third|fourth|freshman|sophomore|junior|senior|year\s*[1-4]|[1-4])\b",
    re.I,
)


def _normalize_semester(line: str) -> str | None:
    """Return 'Year N Term' if `line` looks like a semester header, else None."""
    low = line.lower()
    term_m = _TERM_RE.search(low)
    if not term_m:
        return None
    term = term_m.group(1).capitalize()

    year_m = re.search(r"year\s*([1-4])", low)
    if year_m:
        year = int(year_m.group(1))
    else:
        ym = _YEAR_RE.search(low)
        token = re.sub(r"year\s*", "", ym.group(1).lower()) if ym else ""
        year = _YEAR_WORDS.get(token)
        if year is None:
            return None
    # Reject lines that are clearly real content (a course row, not a header).
    if COURSE_CODE_RE.search(line):
        return None
    return f"Year {year} {term}"


def _cluster_words_to_lines(words: list[dict], y_tol: float = 3.0) -> list[tuple[float, str]]:
    """Group words by y (row), sort each row left-to-right by x. Returns (top, line)."""
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    out: list[tuple[float, str]] = []
    current_top, line_words = None, []
    for w in words:
        if current_top is None or abs(w["top"] - current_top) <= y_tol:
            line_words.append(w)
            current_top = w["top"] if current_top is None else current_top
        else:
            line_words.sort(key=lambda x: x["x0"])
            out.append((current_top, " ".join(x["text"] for x in line_words)))
            line_words, current_top = [w], w["top"]
    if line_words:
        line_words.sort(key=lambda x: x["x0"])
        out.append((current_top, " ".join(x["text"] for x in line_words)))
    return out


def _rows_from_region(region) -> list[list[str]]:
    """
    Extract rows from a single pdfplumber page OR cropped region, in
    top-to-bottom order. Captures BOTH table rows (columns preserved) and any
    text outside tables (e.g. semester headers floating above a table).
    """
    tables = region.find_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
    })
    if not tables:
        tables = region.find_tables({
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
        })

    items: list[tuple[float, list[str]]] = []
    table_bboxes = [t.bbox for t in tables]  # (x0, top, x1, bottom)

    for t in tables:
        top = t.bbox[1]
        for row in t.extract():
            cells = [clean_text(c or "") for c in row]
            if any(cells):
                items.append((top, cells))
                top += 0.01  # keep row order stable within the table

    def in_a_table(w) -> bool:
        cx = (w["x0"] + w["x1"]) / 2
        cy = (w["top"] + w["bottom"]) / 2
        return any(bx0 <= cx <= bx1 and bt <= cy <= bb
                   for (bx0, bt, bx1, bb) in table_bboxes)

    outside = [w for w in region.extract_words(keep_blank_chars=False)
               if not in_a_table(w)]
    for top, line in _cluster_words_to_lines(outside):
        if line.strip():
            items.append((top, [line]))

    items.sort(key=lambda x: x[0])
    return [cells for _, cells in items]


def _page_regions(page, n_columns: int):
    """
    Split a page into `n_columns` vertical strips (left-to-right) and yield a
    cropped region per strip. The degree-requirements sheet is a two-up layout
    (Fall on the left half, Spring on the right half), so each strip holds one
    semester. With n_columns == 1 the whole page is returned unchanged.
    """
    if n_columns <= 1:
        yield page
        return
    w, h = page.width, page.height
    step = w / n_columns
    for i in range(n_columns):
        x0 = max(0, i * step)
        x1 = min(w, (i + 1) * step)
        # relative=False keeps absolute coordinates so bbox math stays consistent.
        yield page.crop((x0, 0, x1, h), relative=False)


def _rows_from_pdf(pdf_path: str, n_columns: int = REQ_PAGE_COLUMNS) -> list[list[str]]:
    """
    Return a flat list of rows across the whole PDF. Each page is split into
    `n_columns` side-by-side regions and each region is extracted on its own,
    so a left-half semester is never concatenated onto the right-half semester.
    Regions are emitted left-to-right, page by page, so the downstream
    header-driven block assembly sees one clean semester stream at a time.
    """
    import pdfplumber

    rows: list[list[str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for region in _page_regions(page, n_columns):
                rows.extend(_rows_from_region(region))
    return rows


def _row_to_line(row: list[str]) -> str:
    """Render a row to text, splitting a merged 'CISC131Foundations...' if needed."""
    cells = [c for c in row if c]
    repaired = []
    for c in cells:
        # A wrapped cell comes back with an embedded newline
        # (e.g. 'CISC231/MATH231\nand MATH244'); a cell is one logical value,
        # so collapse internal newlines to spaces.
        c = c.replace("\n", " ")
        # Only de-bunch when a course code is glued directly to a following
        # word/digit (the Challenge #4 case), e.g. 'CISC131Foundations' or
        # 'CISC339CISC231'. Leave legitimate 'CISC231/MATH231' alone.
        c = re.sub(r"\b([A-Z]{3,4}\d{3})(?=[A-Za-z])", r"\1 ", c)
        repaired.append(re.sub(r"\s{2,}", " ", c).strip())
    return "  |  ".join(repaired)


def ingest_requirements(req_dir: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    pdfs = sorted(glob.glob(os.path.join(req_dir, "*.pdf")))
    if not pdfs:
        print(f"[requirements] no PDF found in {req_dir} — skipping. "
              f"Drop the degree-requirements PDF there to ingest it.")
        return chunks

    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        print("[requirements] pdfplumber not installed; "
              "run `pip install pdfplumber`. Skipping PDF.")
        return chunks

    for pdf_path in pdfs:
        rows = _rows_from_pdf(pdf_path)

        # Walk rows, opening a new block whenever we hit a semester header.
        current_sem: str | None = None
        buffer: list[str] = []

        def flush():
            if current_sem and buffer:
                body = "\n".join(buffer).strip()
                chunks.append({
                    "text": f"{current_sem} — BS Computer Science required courses:\n{body}",
                    "source_url": REQUIREMENTS_URL,
                    "metadata": {"source_type": "requirements", "semester": current_sem},
                })

        for row in rows:
            joined = " ".join(c for c in row if c).strip()
            sem = _normalize_semester(joined)
            if sem:
                flush()
                current_sem, buffer = sem, []
            elif current_sem:
                line = _row_to_line(row)
                if not line:
                    continue
                # A row that does NOT start with a course code, following a row
                # that does, is a cell-wrap continuation (e.g. a long prereq
                # like "...and MATH244" that spilled to a second line — note it
                # *contains* a code but doesn't *start* with one). Glue it back
                # onto the previous course row so the prereq stays intact.
                if (not _STARTS_WITH_CODE.match(line)
                        and buffer
                        and _STARTS_WITH_CODE.match(buffer[-1])):
                    buffer[-1] = f"{buffer[-1]} {line.replace('|', ' ').strip()}".strip()
                    buffer[-1] = re.sub(r"\s{2,}", " ", buffer[-1])
                else:
                    buffer.append(line)
        flush()

    if not chunks:
        print("[requirements] PDF read but no semester blocks detected — "
              "the header pattern likely differs from the heuristic in "
              "_normalize_semester(); adjust _YEAR_RE/_TERM_RE for your file.")
    return chunks


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def build_corpus(raw_dir: str = RAW_DIR) -> list[dict[str, Any]]:
    corpus: list[dict[str, Any]] = []
    corpus += ingest_rmp(os.path.join(raw_dir, "rmp"))
    corpus += ingest_coursicle(os.path.join(raw_dir, "coursicle"))
    corpus += ingest_catalog(os.path.join(raw_dir, "catalog"))
    corpus += ingest_requirements(os.path.join(raw_dir, "requirements"))
    return corpus


def _print_samples(corpus: list[dict[str, Any]], n: int = 5) -> None:
    # Pick one chunk per source type first so the sample is representative,
    # then fill up to n.
    by_type: dict[str, dict[str, Any]] = {}
    for c in corpus:
        by_type.setdefault(c["metadata"]["source_type"], c)
    samples = list(by_type.values())
    for c in corpus:
        if len(samples) >= n:
            break
        if c not in samples:
            samples.append(c)

    print("\n" + "=" * 72)
    print(f"SAMPLE CHUNKS ({min(n, len(samples))} of {len(corpus)} total)")
    print("=" * 72)
    for i, c in enumerate(samples[:n], 1):
        text = c["text"]
        preview = text if len(text) <= 600 else text[:600] + " …"
        print(f"\n--- Sample {i} [{c['metadata']['source_type']}] ---")
        print(f"source_url: {c['source_url']}")
        print(f"metadata:   {c['metadata']}")
        print("text:")
        print(preview)


if __name__ == "__main__":
    corpus = build_corpus()
    counts: dict[str, int] = {}
    for c in corpus:
        counts[c["metadata"]["source_type"]] = counts.get(c["metadata"]["source_type"], 0) + 1
    print(f"Built {len(corpus)} chunks: {counts}")
    _print_samples(corpus, n=5)

print("\n\n========================================================================")
print("ALL REQUIREMENTS CHUNKS")
print("========================================================================")
for c in corpus:
    if c["metadata"]["source_type"] == "requirements":
        print(f"\n--- {c['metadata']['semester']} ---")
        print(c["text"])