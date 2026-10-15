"""Immutable duplicate-detection policy.

The policy describes which signals the detector evaluates and how much
weight each signal carries. It does not describe how the decision is
made; the detector owns that logic and reads the policy for its
thresholds and its signal toggles.

Design decisions
----------------
- Checksum equality is a decisive signal. When two files share a
  SHA-256 checksum, they are byte-identical; the detector reports them
  as duplicates regardless of other signals.
- DOI equality is a strong signal but not decisive. Two documents that
  share a DOI usually refer to the same work, but a metadata extraction
  error can produce a spurious match. The policy treats DOI equality as
  a duplicate when the primary signal agrees or when the title and
  authors also match closely.
- Title and author equality is a conservative signal. Titles are
  normalized (case-folded, punctuation stripped, whitespace collapsed)
  before comparison. Author lists are normalized (case-folded,
  punctuation stripped, sorted) before comparison.
- Year equality is advisory. A difference of one year is accepted
  because preprints and published versions frequently carry different
  years.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DuplicatePolicy:
    """Configuration for duplicate detection.

    Attributes
    ----------
    use_checksum:
        When True, the detector queries the repository by checksum.
    use_doi:
        When True, the detector queries the repository by DOI.
    use_metadata:
        When True, the detector falls back to conservative metadata
        matching when neither checksum nor DOI matches.
    require_author_match:
        When True, a metadata-only match requires both the title and the
        author list to match. When False, a title-only match is
        sufficient. The default is True.
    allow_year_difference:
        When True, a one-year difference between the candidate and the
        existing document is accepted for a metadata-only match.
    metadata_candidate_limit:
        Maximum number of repository rows to inspect during the
        metadata-only fallback. This bounds the cost of the fallback.
    """

    use_checksum: bool = True
    use_doi: bool = True
    use_metadata: bool = True
    require_author_match: bool = True
    allow_year_difference: bool = True
    metadata_candidate_limit: int = 500

    def __post_init__(self) -> None:
        if self.metadata_candidate_limit < 1:
            raise ValueError("metadata_candidate_limit must be at least 1")
        if not (self.use_checksum or self.use_doi or self.use_metadata):
            raise ValueError(
                "at least one detection signal must be enabled"
            )