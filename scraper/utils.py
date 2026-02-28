#!/usr/bin/env python3
"""
PESU Academy PDF Fetcher

Interactive tool to fetch course PDFs from PESU Academy using the following workflow:
1. Get course codes from /Academy/a/g/getSubjectsCode
2. Get unit IDs for a course from /Academy/a/i/getCourse/[course_id]
3. Get classes for a unit from /Academy/a/i/getCourseClasses/[unit_id]
4. Download PDF from /Academy/s/studentProfilePESUAdmin
"""

import os
import json
import logging
from typing import Optional, List
from pathlib import Path
import hashlib
from pypdf import PdfWriter
from colorama import Fore, Style, init as colorama_init


# Initialize colorama for cross-platform colored output
colorama_init(autoreset=True)



def setup_logger(
    name: str = "pdf_fetcher", log_file: Optional[Path] = None
) -> logging.Logger:
    """Set up a logger with console and file output."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)  # Default to WARNING to reduce noise

    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler()

    class ColoredFormatter(logging.Formatter):
        COLORS = {
            "DEBUG": Fore.CYAN,
            "INFO": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "CRITICAL": Fore.RED + Style.BRIGHT,
        }

        def format(self, record):
            # Make a copy to avoid modifying the original record
            log_record = logging.makeLogRecord(record.__dict__)
            levelname = log_record.levelname
            if levelname in self.COLORS:
                log_record.levelname = (
                    f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
                )
            return super().format(log_record)

    console_handler.setFormatter(ColoredFormatter("%(levelname)s - %(message)s"))
    logger.addHandler(console_handler)

    # File handler for failures (without colors) - only if log_file is explicitly provided
    if log_file is not None:
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.ERROR)  # Only log errors to file
        # Use plain formatter for file (no colors)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        logger.addHandler(file_handler)

    logger.propagate = False

    return logger


logger = setup_logger()  # Default logger for initialization
def update_courses_index(base_dir: Path) -> None:
    """
    Update the index.json file in the courses directory.
    This file lists all available course directories for the frontend API.
    """
    index_file = base_dir / "index.json"

    # Find all course directories
    course_dirs = []
    if base_dir.exists():
        for entry in sorted(base_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith("course"):
                # Verify it has a summary file
                has_summary = any(
                    f.name.endswith("_course_summary.json")
                    for f in entry.iterdir()
                    if f.is_file()
                )
                if has_summary:
                    course_dirs.append(entry.name)

    # Write the index file
    index_data = {
        "courses": course_dirs,
        "updated_at": __import__("datetime").datetime.now().isoformat(),
    }

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Updated courses index: {len(course_dirs)} courses in {index_file}")
def _read_prefix(path: Path, size: int = 4096) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(size)
    except Exception:
        return b""


def _is_zip_container(path: Path) -> bool:
    # Office OpenXML formats (pptx/docx/xlsx) are ZIP containers.
    prefix = _read_prefix(path, 8)
    return prefix.startswith(b"PK")


def _is_pdf(path: Path) -> bool:
    prefix = _read_prefix(path, 8)
    return prefix.startswith(b"%PDF")


def _looks_like_html(path: Path) -> bool:
    prefix = _read_prefix(path, 512).lstrip()
    lower = prefix.lower()
    return lower.startswith(b"<!doctype html") or lower.startswith(b"<html")


def _truthy_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}
def sha_sidecar_path(path: Path) -> Path:
    """Return the sidecar .sha256 path for a given file."""
    return path.with_name(path.name + ".sha256")


def orig_sidecar_path(path: Path) -> Path:
    """Return the sidecar .orig.sha256 path (stores original file sha for converted PDFs)."""
    return path.with_name(path.name + ".orig.sha256")


def compute_file_sha256(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_sidecar_sha(path: Path) -> Optional[str]:
    """Read the sidecar SHA256 for a file if present."""
    side = sha_sidecar_path(path)
    if side.exists():
        return side.read_text().strip()
    return None


def write_sidecar_sha(path: Path, sha_hex: str) -> None:
    """Write the sidecar SHA256 for a file."""
    side = sha_sidecar_path(path)
    side.write_text(sha_hex)


def compute_combined_sha(pdf_paths: List[Path]) -> str:
    """Compute a combined SHA over a list of PDFs using their individual sidecars or file contents.

    The resulting SHA is stable for the same set & order of files.
    """
    pieces: List[str] = []
    for p in sorted(pdf_paths, key=lambda x: x.name):
        if p.suffix.lower() != ".pdf":
            continue
        sha = read_sidecar_sha(p)
        if not sha and p.exists():
            sha = compute_file_sha256(p)
        sha_part = sha if sha else "missing"
        pieces.append(f"{p.name}:{sha_part}")
    combined = hashlib.sha256(";".join(pieces).encode()).hexdigest()
    return combined
def merge_pdfs(pdf_files: List[Path], output_path: Path) -> bool:
    """Merge multiple PDF files into a single PDF. Skips non-PDF files.

    The function computes a combined SHA of the inputs; if an existing merged
    file has the same SHA the merge is skipped to avoid unnecessary work. No
    `.sha256` sidecar files are written — checksums are stored in the course
    summary JSON instead.
    """
    try:
        # Compute combined SHA of inputs and skip merge if nothing changed
        combined = compute_combined_sha(pdf_files)
        if output_path.exists():
            try:
                existing = compute_file_sha256(output_path)
                if existing == combined:
                    logger.debug(
                        f"Skipping merge; merged PDF up-to-date: {output_path.name}"
                    )
                    return True
            except Exception:
                # If we cannot compute existing hash, proceed to re-merge
                pass

        merger = PdfWriter()
        pdf_count = 0

        for pdf_file in pdf_files:
            # Only merge PDF files
            if pdf_file.suffix.lower() != ".pdf":
                logger.debug(f"Skipping non-PDF file: {pdf_file.name}")
                continue

            if pdf_file.exists() and pdf_file.stat().st_size > 0:
                try:
                    merger.append(str(pdf_file))
                    pdf_count += 1
                except Exception as e:
                    logger.warning(f"Failed to add {pdf_file.name} to merged PDF: {e}")
                    continue

        if len(merger.pages) == 0:
            logger.warning(
                f"No valid PDFs to merge (found {len(pdf_files)} files, {pdf_count} were PDFs)"
            )
            return False

        with open(output_path, "wb") as f:
            merger.write(f)

        merger.close()

        # Compute merged file SHA (do not write a sidecar file; store in JSON instead)
        try:
            merged_sha = compute_file_sha256(output_path)
        except Exception:
            merged_sha = None

        logger.debug(
            f"✓ Merged {pdf_count} PDFs into {output_path.name} ({output_path.stat().st_size:,} bytes)"
        )
        if merged_sha:
            logger.debug(f"Merged PDF sha256: {merged_sha}")
        return True

    except Exception as e:
        logger.error(f"FAILURE [merge_pdfs]: Failed to merge PDFs - {e}")
        logger.error(f"Output Path: {output_path}")
        logger.error(f"Number of files: {len(pdf_files)}")
        return False
