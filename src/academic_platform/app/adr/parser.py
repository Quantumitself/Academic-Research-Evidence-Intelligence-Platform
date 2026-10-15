"""Parser for ADR markdown files.

The parser understands a restricted, well-documented markdown subset:

- A level-1 heading containing the number and title.
- A metadata block of ``Key: Value`` lines near the top.
- Level-2 sections (``## Context``, ``## Decision``, ...).
- Level-2 sections not in the canonical set are preserved as
  ``extra_sections`` so that no authoring content is silently dropped.

The parser must never raise on malformed input; instead it raises
``ADRValidationError`` with a precise description of the problem, which the
caller is expected to surface to the user.
"""

from __future__ import annotations

import re
from pathlib import Path

from academic_platform.app.adr.model import ADR, ADRStatus, ADRValidationError
from academic_platform.app.adr.validator import validate_adr

_TITLE_PATTERN = re.compile(r"^#\s*(?P<number>\d{4})\.\s*(?P<title>.+?)\s*$")
_SECTION_PATTERN = re.compile(r"^##\s+(?P<name>.+?)\s*$")
_METADATA_PATTERN = re.compile(r"^(?P<key>[A-Za-z][A-Za-z _-]*):\s*(?P<value>.*)$")

_METADATA_KEYS = {
    "status",
    "date",
    "deciders",
    "supersedes",
    "superseded by",
    "superseded_by",
}

_CANONICAL_SECTIONS = {
    "context",
    "decision",
    "consequences",
    "alternatives",
    "references",
}


def _split_values(raw: str) -> tuple[str, ...]:
    """Split a comma-separated metadata value into trimmed items."""
    items = [item.strip() for item in raw.split(",")]
    return tuple(item for item in items if item)


def _parse_status(raw: str, path: Path) -> ADRStatus:
    normalized = raw.strip().lower()
    for candidate in ADRStatus:
        if candidate.value == normalized:
            return candidate
    raise ADRValidationError(
        f"{path}: unrecognized status {raw!r}; expected one of "
        f"{', '.join(candidate.value for candidate in ADRStatus)}"
    )


def _parse_references(raw: str) -> tuple[str, ...]:
    """Extract ADR numbers from a metadata value.

    Accepts comma-separated four-digit numbers or markdown links whose text
    starts with the number. Anything that does not resolve to a four-digit
    token is dropped, keeping the record structurally clean.
    """
    numbers: list[str] = []
    for chunk in raw.split(","):
        candidate = chunk.strip()
        if not candidate:
            continue
        # Accept "0003" and "[0003](...)".
        head = candidate.split("]")[0].lstrip("[")
        if re.match(r"^\d{4}$", head):
            numbers.append(head)
    return tuple(numbers)


def parse_adr_file(path: Path) -> ADR:
    """Parse a single ADR file.

    Raises
    ------
    ADRValidationError
        If the file cannot be read, does not start with a valid title, or
        contains an unrecognized status.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ADRValidationError(f"Unable to read {path}: {exc}") from exc

    lines = text.splitlines()
    if not lines:
        raise ADRValidationError(f"{path}: file is empty")

    title_match = _TITLE_PATTERN.match(lines[0].strip())
    if not title_match:
        raise ADRValidationError(
            f"{path}: first line must match '# NNNN. Title', got {lines[0]!r}"
        )

    number = title_match.group("number")
    title = title_match.group("title").strip()

    metadata: dict[str, str] = {}
    index = 1
    # Metadata block continues until the first blank line followed by a
    # heading, or until the first section heading is encountered.
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("##"):
            break
        match = _METADATA_PATTERN.match(stripped)
        if not match:
            break
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if key in _METADATA_KEYS:
            metadata[key] = value
        index += 1

    raw_status = metadata.get("status", "")
    if not raw_status:
        raise ADRValidationError(f"{path}: missing 'Status' metadata field")
    status = _parse_status(raw_status, path)

    date_value = metadata.get("date", "").strip()
    if not date_value:
        raise ADRValidationError(f"{path}: missing 'Date' metadata field")

    deciders = _split_values(metadata.get("deciders", ""))
    supersedes = _parse_references(metadata.get("supersedes", ""))
    superseded_by_raw = metadata.get("superseded by") or metadata.get("superseded_by") or ""
    superseded_by_refs = _parse_references(superseded_by_raw)
    superseded_by = superseded_by_refs[0] if superseded_by_refs else None

    sections: dict[str, list[str]] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in lines[index:]:
        section_match = _SECTION_PATTERN.match(line.strip())
        if section_match:
            if current_name is not None:
                sections[current_name] = current_lines
            current_name = section_match.group("name").strip()
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = current_lines

    def _section_text(name: str) -> str:
        for key, value_lines in sections.items():
            if key.lower() == name.lower():
                return "\n".join(value_lines).strip()
        return ""

    context = _section_text("Context")
    decision = _section_text("Decision")
    consequences = _section_text("Consequences")
    alternatives = _section_text("Alternatives")
    references_section = _section_text("References")

    references: list[str] = []
    if references_section:
        for line in references_section.splitlines():
            stripped = line.strip()
            if stripped.startswith("-"):
                references.append(stripped.lstrip("-").strip())
            elif stripped:
                references.append(stripped)
    references.extend(
        _split_values(metadata.get("references", ""))
    )

    extra_sections: list[tuple[str, str]] = []
    for name, content_lines in sections.items():
        if name.lower() in _CANONICAL_SECTIONS:
            continue
        text_content = "\n".join(content_lines).strip()
        if text_content:
            extra_sections.append((name, text_content))

    adr = ADR(
        number=number,
        title=title,
        status=status,
        date=date_value,
        deciders=deciders,
        context=context,
        decision=decision,
        consequences=consequences,
        alternatives=alternatives,
        references=tuple(references),
        supersedes=supersedes,
        superseded_by=superseded_by,
        source_path=path,
        extra_sections=tuple(extra_sections),
    )

    issues = validate_adr(adr)
    if issues:
        rendered = "; ".join(issue.render() for issue in issues)
        raise ADRValidationError(f"{path}: validation failed: {rendered}")

    return adr


def parse_adr_directory(directory: Path) -> tuple[list[ADR], list[tuple[Path, str]]]:
    """Parse every ADR file in the directory.

    Returns
    -------
    tuple[list[ADR], list[tuple[Path, str]]]
        A tuple of successfully parsed records sorted by number, and a list of
        ``(path, error_message)`` pairs for files that failed to parse.
    """
    records: list[ADR] = []
    errors: list[tuple[Path, str]] = []
    if not directory.is_dir():
        return records, errors

    for path in sorted(directory.glob("*.md")):
        if path.name.lower() in {"readme.md", "template.md"}:
            continue
        try:
            records.append(parse_adr_file(path))
        except ADRValidationError as exc:
            errors.append((path, str(exc)))

    records.sort(key=lambda record: record.number)
    return records, errors