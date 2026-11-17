"""
fs_tools.py
───────────
Part A: Core file-system tools used by the LLM-powered file assistant.

Provides four public tools that can be registered with an LLM's function-
calling interface:

    read_file(filepath)            → dict   Read TXT / PDF / DOCX files
    list_files(directory, ext)     → list   List files, optional ext filter
    write_file(filepath, content)  → dict   Write (or overwrite) a file
    search_in_file(filepath, kw)   → dict   Case-insensitive keyword search

Design principles
-----------------
- Every public function returns either a plain list (list_files) or a dict
  that always contains a ``success`` boolean key so callers never need to
  catch exceptions from the tool layer.
- Internal reader helpers (_read_txt, _read_pdf, _read_docx) are private;
  only the four public functions above should be imported by other modules.
- list_files raises ValueError for invalid input so the agent layer can
  translate it into a structured error response without try/except inside
  this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from pprint import pprint

import pdfplumber
from docx import Document
from pdfminer.pdfparser import PDFSyntaxError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".pdf", ".docx"})

# Characters of surrounding text to include on each side of a keyword hit.
DEFAULT_CONTEXT_CHARS: int = 80


# ---------------------------------------------------------------------------
# Private reader helpers
# ---------------------------------------------------------------------------


def _read_txt(path: Path) -> str:
    """Return the full text content of a UTF-8 encoded plain-text file."""
    return path.read_text(encoding="utf-8")


def _read_pdf(path: Path) -> str:
    """
    Extract all text from a PDF file using pdfplumber.

    Pages that contain no extractable text (e.g. scanned images without OCR)
    are silently skipped so that mixed PDFs still return as much content as
    possible.
    """
    pages: list[str] = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)

    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    """
    Extract paragraph text from a DOCX file using python-docx.

    Empty / whitespace-only paragraphs are omitted to keep the output clean.
    """
    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Shared metadata helper
# ---------------------------------------------------------------------------


def _get_file_metadata(path: Path) -> dict:
    """
    Build a metadata dictionary for *path*.

    Returns
    -------
    dict
        ``name``      – file basename  (str)
        ``extension`` – lower-cased suffix including the dot (str)
        ``size``      – file size in bytes (int)
        ``modified``  – ISO-8601 timestamp of last modification in local time
    """
    stats = path.stat()
    return {
        "name": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": stats.st_size,
        "modified": (
            datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc)
            .astimezone()
            .isoformat()
        ),
    }


# ---------------------------------------------------------------------------
# Public Tool A-1: read_file
# ---------------------------------------------------------------------------


def read_file(filepath: str) -> dict:
    """
    Read the content of a resume file and return its text with metadata.

    Supported formats: ``.txt``, ``.pdf``, ``.docx``

    Parameters
    ----------
    filepath : str
        Relative or absolute path to the file to read.

    Returns
    -------
    dict
        On success::

            {
              "success": True,
              "metadata": {name, extension, size_bytes, modified},
              "content":  "<extracted text>"
            }

        On failure::

            {"success": False, "error": "<human-readable message>"}
    """
    path = Path(filepath)

    # --- existence & type checks ---
    if not path.exists():
        return {"success": False, "error": f"File not found: '{filepath}'"}

    if not path.is_file():
        return {"success": False, "error": f"Path is not a file: '{filepath}'"}

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        return {
            "success": False,
            "error": (
                f"Unsupported file type '{extension}'. "
                f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        }

    # --- dispatch to the correct reader ---
    _readers = {
        ".txt": _read_txt,
        ".pdf": _read_pdf,
        ".docx": _read_docx,
    }

    try:
        content = _readers[extension](path)
        return {
            "success": True,
            "metadata": _get_file_metadata(path),
            "content": content,
        }

    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied when reading '{filepath}'",
        }
    except PDFSyntaxError as exc:
        return {
            "success": False,
            "error": f"Could not parse PDF '{filepath}': {exc}",
        }
    except UnicodeDecodeError as exc:
        return {
            "success": False,
            "error": f"Encoding error in '{filepath}': {exc}",
        }
    except OSError as exc:
        return {"success": False, "error": f"OS error reading '{filepath}': {exc}"}


# ---------------------------------------------------------------------------
# Public Tool A-2: list_files
# ---------------------------------------------------------------------------


def list_files(directory: str, extension: str | None = None) -> list:
    """
    List all files in *directory*, optionally filtered by *extension*.

    Parameters
    ----------
    directory : str
        Path to the directory to inspect.
    extension : str, optional
        File extension to filter by (e.g. ``'.pdf'``, ``'.txt'``).
        The leading dot is required. Pass ``None`` to return all files.

    Returns
    -------
    list[dict]
        A list of metadata dicts (one per matching file) sorted by filename::

            [
              {name, extension, size_bytes, modified},
              ...
            ]

    Raises
    ------
    ValueError
        If *directory* does not exist or is not a directory.  Callers
        (e.g. the agent's ``execute_tool``) should catch this and translate
        it into an error response.
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        raise ValueError(f"Directory does not exist: '{directory}'")

    if not dir_path.is_dir():
        raise ValueError(f"Path is not a directory: '{directory}'")

    results: list[dict] = []

    for item in sorted(dir_path.iterdir()):
        if not item.is_file():
            continue

        if extension and item.suffix.lower() != extension.lower():
            continue

        results.append(_get_file_metadata(item))

    return results


# ---------------------------------------------------------------------------
# Public Tool A-3: write_file
# ---------------------------------------------------------------------------


def write_file(filepath: str, content: str) -> dict:
    """
    Write *content* to *filepath*, creating any missing parent directories.

    If *filepath* already exists it will be **overwritten**.

    Parameters
    ----------
    filepath : str
        Destination file path (relative or absolute).
    content : str
        Text content to write.  The file is written as UTF-8.

    Returns
    -------
    dict
        On success::

            {
              "success":  True,
              "message":  "File written successfully.",
              "metadata": {name, extension, size_bytes, modified}
            }

        On failure::

            {"success": False, "error": "<human-readable message>"}
    """
    path = Path(filepath)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "message": "File written successfully.",
            "metadata": _get_file_metadata(path),
        }

    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied when writing '{filepath}'",
        }
    except UnicodeEncodeError as exc:
        return {
            "success": False,
            "error": f"Encoding error while writing '{filepath}': {exc}",
        }
    except OSError as exc:
        return {"success": False, "error": f"OS error writing '{filepath}': {exc}"}


# ---------------------------------------------------------------------------
# Public Tool A-4: search_in_file
# ---------------------------------------------------------------------------


def search_in_file(
    filepath: str,
    keyword: str,
    context_chars: int = DEFAULT_CONTEXT_CHARS,
) -> dict:
    """
    Search for *keyword* inside a file (case-insensitive).

    The function reuses ``read_file`` so it supports the same three formats
    (TXT, PDF, DOCX).  Each occurrence of the keyword is returned with its
    approximate line number and a snippet of surrounding text.

    Parameters
    ----------
    filepath : str
        Path to the file to search.
    keyword : str
        Term to look for.  Matching is case-insensitive.
    context_chars : int, optional
        Number of characters to include on *each side* of the keyword in the
        context snippet.  Defaults to ``DEFAULT_CONTEXT_CHARS`` (80).

    Returns
    -------
    dict
        On success::

            {
              "success":     True,
              "metadata":    {name, extension, size_bytes, modified},
              "keyword":     "<original keyword>",
              "match_count": <int>,
              "matches": [
                {"line_number": <int>, "context": "<snippet>"},
                ...
              ]
            }

        On failure the dict from ``read_file`` is returned as-is (containing
        ``success=False`` and an ``error`` key).
    """
    # Delegate reading so we inherit all its error handling.
    read_result = read_file(filepath)

    if not read_result.get("success"):
        return read_result  # propagate the error verbatim

    content: str = read_result.get("content", "")
    content_lower = content.lower()
    keyword_lower = keyword.lower()

    matches: list[dict] = []

    if keyword_lower:
        start = 0
        while True:
            idx = content_lower.find(keyword_lower, start)
            if idx == -1:
                break

            # Approximate line number (1-indexed).
            line_number = content.count("\n", 0, idx) + 1

            # Build a context snippet with collapsed whitespace so that
            # newlines in the extracted text don't break the snippet.
            ctx_start = max(0, idx - context_chars)
            ctx_end = min(len(content), idx + len(keyword_lower) + context_chars)
            snippet = " ".join(content[ctx_start:ctx_end].split())

            matches.append({"line_number": line_number, "context": snippet})

            # Advance past the current match (minimum 1 char to avoid infinite loop).
            start = idx + max(len(keyword_lower), 1)

    return {
        "success": True,
        "metadata": read_result.get("metadata"),
        "keyword": keyword,
        "match_count": len(matches),
        "matches": matches,
    }


# ---------------------------------------------------------------------------
# Quick smoke-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== fs_tools.py — quick smoke test ===\n")

    test_dir = "resumes"
    print(f"list_files('{test_dir}', extension='.txt'):")
    try:
        files = list_files(test_dir, extension=".txt")
        for f in files[:5]:
            print(f"  {f}")
    except ValueError as e:
        print(f"  Error: {e}")

    print()
    filepath = input("Enter a file path to read (or press Enter to skip): ").strip()
    if filepath:
        result = read_file(filepath)
        pprint(result)

        keyword = input("Enter a keyword to search (or press Enter to skip): ").strip()
        if keyword:
            pprint(search_in_file(filepath, keyword))
