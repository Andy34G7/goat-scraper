#!/usr/bin/env python3
"""
PESU Academy PDF Fetcher

Interactive tool to fetch course PDFs from PESU Academy using the following workflow:
1. Get course codes from /Academy/a/g/getSubjectsCode
2. Get unit IDs for a course from /Academy/a/i/getCourse/[course_id]
3. Get classes for a unit from /Academy/a/i/getCourseClasses/[unit_id]
4. Download PDF from /Academy/s/studentProfilePESUAdmin
"""

import sys
import os
import subprocess
import shutil
import tempfile
from typing import Optional, List, Tuple
from pathlib import Path

from spire.presentation import Presentation, FileFormat

from .utils import _is_zip_container, _is_pdf, _looks_like_html, _truthy_env, logger

def _should_keep_repaired_artifacts() -> bool:
    return _truthy_env("PDF_FETCHER_KEEP_REPAIRED", default="0")
def _list_office_sources(unit_dir: Path) -> List[Path]:
    """List Office source docs in a unit directory.

    Excludes LibreOffice zip-repair artifacts (e.g. *_repaired.pptx).
    """
    office_exts = {".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls"}
    sources: List[Path] = []
    try:
        for p in unit_dir.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in office_exts:
                continue
            if p.stem.endswith("_repaired"):
                continue
            sources.append(p)
    except Exception:
        return []
    return sources
def _validate_and_retry_office_conversions(
    unit_dir: Path,
) -> Tuple[int, int, List[str]]:
    """Ensure each Office source has a corresponding non-empty PDF.

    Returns:
      (total_sources, converted_sources, missing_filenames)
    """
    sources = _list_office_sources(unit_dir)
    missing: List[str] = []
    converted_ok = 0

    for src in sources:
        expected_pdf = src.with_suffix(".pdf")
        if (
            expected_pdf.exists()
            and expected_pdf.stat().st_size > 0
            and _is_pdf(expected_pdf)
        ):
            converted_ok += 1
            continue

        # Retry conversion once (synchronously) to avoid missing slides due to timing.
        try:
            pdf = convert_to_pdf(src)
        except Exception as e:
            logger.warning(f"Conversion retry exception for {src.name}: {e}")
            pdf = None

        if pdf and pdf.exists() and pdf.stat().st_size > 0 and _is_pdf(pdf):
            converted_ok += 1
            continue

        missing.append(src.name)

    return (len(sources), converted_ok, missing)
def _unique_existing_pdfs(paths: List[Path]) -> List[Path]:
    """Return a de-duplicated list of valid PDFs, preserving the first-seen order."""
    out: List[Path] = []
    seen: set[str] = set()
    for p in paths:
        try:
            if not p or not p.exists() or p.stat().st_size <= 0:
                continue
            if p.suffix.lower() != ".pdf":
                continue
            # Avoid merging previously merged outputs back into themselves.
            name = p.name
            if name.endswith("_merged.pdf") or name.endswith("_ESA.pdf"):
                continue
            if not _is_pdf(p):
                continue
            key = str(p.resolve())
        except Exception:
            # Fall back to string key without resolve()
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out
def convert_to_pdf(input_path: Path) -> Optional[Path]:
    """
    Convert Office documents (PPTX, DOCX, etc.) to PDF.
    Tries multiple methods in order of preference.
    Returns the PDF path if successful, None otherwise.
    """
    if not input_path.exists():
        logger.error(f"File not found: {input_path}")
        return None

    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return input_path  # Already a PDF

    output_path = input_path.with_suffix(".pdf")

    # Quick sanity checks to avoid misleading "zip repair" spam.
    if suffix in {".pptx", ".docx", ".xlsx"}:
        if not _is_zip_container(input_path):
            if _looks_like_html(input_path):
                logger.warning(
                    f"File does not look like a real {suffix} (looks like HTML). Likely an auth/redirect or server error: {input_path.name}"
                )
            else:
                logger.warning(
                    f"File does not look like a valid ZIP-based Office document: {input_path.name}"
                )
            return None

    # Method 1 (Preferred for PPTX/PPT): Spire.Presentation
    if suffix in {".pptx", ".ppt"}:
        try:
            logger.debug(f"Converting {input_path.name} to PDF using Spire.Presentation...")
            presentation = Presentation()
            presentation.LoadFromFile(str(input_path))
            presentation.SaveToFile(str(output_path), FileFormat.PDF)
            presentation.Dispose()
            
            if (
                output_path.exists()
                and output_path.stat().st_size > 0
                and _is_pdf(output_path)
            ):
                logger.debug(f"✓ Converted to PDF using Spire: {output_path}")
                return output_path
            else:
                logger.warning("Spire.Presentation failed to produce a valid PDF. Falling back...")
        except Exception:
            logger.warning(f"Spire.Presentation failed to load {input_path.name}. Attempting zip repair...")
            
            # Try zip repair for Spire
            repaired_path = input_path.parent / f"{input_path.stem}_repaired{suffix}"
            try:
                zip_exe = shutil.which("zip")
                if zip_exe:
                    subprocess.run(
                        [zip_exe, "-FF", str(input_path), "--out", str(repaired_path)],
                        input="y\n",
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if (
                        repaired_path.exists()
                        and repaired_path.stat().st_size > 0
                        and _is_zip_container(repaired_path)
                    ):
                        logger.warning(f"✓ Repaired corrupted file: {repaired_path.name}, attempting Spire again...")
                        try:
                            presentation = Presentation()
                            presentation.LoadFromFile(str(repaired_path))
                            presentation.SaveToFile(str(output_path), FileFormat.PDF)
                            presentation.Dispose()
                            
                            if (
                                output_path.exists()
                                and output_path.stat().st_size > 0
                                and _is_pdf(output_path)
                            ):
                                logger.debug(f"✓ Converted repaired file to PDF using Spire: {output_path}")
                                if not _should_keep_repaired_artifacts():
                                    try: repaired_path.unlink()
                                    except: pass
                                return output_path
                        except Exception as e2:
                            logger.warning(f"Spire failed to load repaired file: {e2}")
                        
                        if not _should_keep_repaired_artifacts():
                            try: repaired_path.unlink()
                            except: pass
                    else:
                        logger.warning("Spire zip repair failed or produced empty file.")
            except Exception as zipe:
                logger.debug(f"Zip repair exception for Spire: {zipe}")
                if repaired_path.exists():
                    try: repaired_path.unlink()
                    except: pass
            
            logger.debug(f"Spire.Presentation fallback failed for {input_path.name}. Falling back...")

    # Method 2: Try soffice (LibreOffice) headless mode
    soffice_paths: List[str] = []
    env_soffice = os.getenv("PDF_FETCHER_SOFFICE_PATH")
    if env_soffice:
        soffice_paths.append(env_soffice)
    soffice_paths.extend(
        [
            shutil.which("soffice") or "",
            shutil.which("libreoffice") or "",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
            "/usr/bin/soffice",  # Linux
            "/usr/bin/libreoffice",  # Linux alternative
        ]
    )

    # De-duplicate while preserving order
    seen = set()
    soffice_paths = [p for p in soffice_paths if p and not (p in seen or seen.add(p))]

    # Track whether LibreOffice was available and capture stderr for diagnostics
    libreoffice_tried = False
    last_soffice_error = None

    for soffice in soffice_paths:
        if not soffice:
            continue
        if not Path(soffice).exists():
            continue
        try:
            logger.debug(f"Converting {input_path.name} to PDF using LibreOffice...")

            # Use an isolated LO profile to prevent first-run dialogs and avoid profile locks.
            lo_profile_dir = Path(tempfile.mkdtemp(prefix="goat_lo_profile_")).resolve()
            lo_profile_url = lo_profile_dir.as_uri()

            try:
                result = subprocess.run(
                    [
                        soffice,
                        "--headless",
                        "--nologo",
                        "--nofirststartwizard",
                        "--norestore",
                        f"-env:UserInstallation={lo_profile_url}",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(input_path.parent),
                        str(input_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
            finally:
                try:
                    shutil.rmtree(lo_profile_dir, ignore_errors=True)
                except Exception:
                    pass

            # Mark that we attempted LibreOffice and capture any stderr for diagnostics
            libreoffice_tried = True
            try:
                last_soffice_error = (result.stderr or "").strip()
            except Exception:
                last_soffice_error = None

            if (
                output_path.exists()
                and output_path.stat().st_size > 0
                and _is_pdf(output_path)
            ):
                logger.debug(f"✓ Converted to PDF: {output_path}")
                return output_path
            if output_path.exists() and (
                output_path.stat().st_size == 0 or not _is_pdf(output_path)
            ):
                # Avoid future false positives.
                try:
                    output_path.unlink()
                except Exception:
                    pass

            # Check if LibreOffice failed to load the file (corrupted zip)
            stderr_lower = (result.stderr or "").lower()
            if (
                "source file could not be loaded" in stderr_lower
                or "file format error" in stderr_lower
            ):
                logger.warning(
                    "LibreOffice failed to load file, attempting zip repair..."
                )

                # Try to repair the file using zip -FF
                repaired_path = (
                    input_path.parent / f"{input_path.stem}_repaired{suffix}"
                )
                try:
                    zip_exe = shutil.which("zip")
                    if not zip_exe:
                        logger.warning("zip tool not found; cannot attempt zip repair")
                        continue
                    repair_result = subprocess.run(
                        [
                            zip_exe,
                            "-FF",
                            str(input_path),
                            "--out",
                            str(repaired_path),
                        ],
                        input="y\n",
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                    if (
                        repaired_path.exists()
                        and repaired_path.stat().st_size > 0
                        and _is_zip_container(repaired_path)
                    ):
                        logger.debug(f"✓ Repaired corrupted file: {repaired_path.name}")

                        # Try converting the repaired file without mutating the original.
                        logger.debug("Converting repaired file to PDF...")
                        lo_profile_dir = Path(
                            tempfile.mkdtemp(prefix="goat_lo_profile_")
                        ).resolve()
                        lo_profile_url = lo_profile_dir.as_uri()
                        try:
                            retry_result = subprocess.run(
                                [
                                    soffice,
                                    "--headless",
                                    "--nologo",
                                    "--nofirststartwizard",
                                    "--norestore",
                                    f"-env:UserInstallation={lo_profile_url}",
                                    "--convert-to",
                                    "pdf",
                                    "--outdir",
                                    str(input_path.parent),
                                    str(repaired_path),
                                ],
                                capture_output=True,
                                text=True,
                                timeout=180,
                            )
                        finally:
                            try:
                                shutil.rmtree(lo_profile_dir, ignore_errors=True)
                            except Exception:
                                pass

                        repaired_pdf = repaired_path.with_suffix(".pdf")
                        if (
                            repaired_pdf.exists()
                            and repaired_pdf.stat().st_size > 0
                            and _is_pdf(repaired_pdf)
                        ):
                            # Normalize final name to the original stem.
                            try:
                                repaired_pdf.replace(output_path)
                            except Exception:
                                pass
                            if (
                                output_path.exists()
                                and output_path.stat().st_size > 0
                                and _is_pdf(output_path)
                            ):
                                logger.debug(
                                    f"✓ Converted repaired file to PDF: {output_path}"
                                )

                                # Clean up repaired artifacts unless explicitly requested.
                                if not _should_keep_repaired_artifacts():
                                    try:
                                        repaired_path.unlink(missing_ok=True)
                                    except Exception:
                                        pass
                                    try:
                                        repaired_pdf.unlink(missing_ok=True)
                                    except Exception:
                                        pass
                                return output_path
                        else:
                            logger.warning("Failed to convert repaired file")
                    else:
                        logger.warning("Zip repair failed or produced empty file")
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    logger.debug(f"Zip repair failed: {e}")
                    # Clean up if repair file was created
                    if repaired_path.exists():
                        repaired_path.unlink()

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            # Record the exception for later diagnostics
            try:
                last_soffice_error = str(e)
            except Exception:
                last_soffice_error = None
            logger.debug(f"LibreOffice conversion failed: {e}")
            continue

    # Method 2 (optional): Try macOS Keynote/Pages via osascript (for PPTX/DOCX)
    if sys.platform == "darwin" and _truthy_env("PDF_FETCHER_ALLOW_IWORK", default="0"):
        if suffix in [".pptx", ".ppt"]:
            try:
                logger.debug(f"Converting {input_path.name} to PDF using Keynote...")
                script = f"""
                tell application "Keynote"
                    set theDoc to open POSIX file "{input_path}"
                    export theDoc to POSIX file "{output_path}" as PDF
                    close theDoc
                end tell
                """
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if (
                    output_path.exists()
                    and output_path.stat().st_size > 0
                    and _is_pdf(output_path)
                ):
                    logger.debug(f"✓ Converted to PDF: {output_path}")
                    return output_path
            except Exception as e:
                logger.debug(f"Keynote conversion failed: {e}")

        elif suffix in [".docx", ".doc"]:
            try:
                logger.debug(f"Converting {input_path.name} to PDF using Pages...")
                script = f"""
                tell application "Pages"
                    set theDoc to open POSIX file "{input_path}"
                    export theDoc to POSIX file "{output_path}" as PDF
                    close theDoc
                end tell
                """
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if (
                    output_path.exists()
                    and output_path.stat().st_size > 0
                    and _is_pdf(output_path)
                ):
                    logger.debug(f"✓ Converted to PDF: {output_path}")
                    return output_path
            except Exception as e:
                logger.debug(f"Pages conversion failed: {e}")

    # Method 3: For PPTX, try python-pptx + reportlab (limited - only extracts text/images)
    # This is a fallback that won't preserve full formatting

    logger.warning(
        f"Could not convert {input_path.name} to PDF. Keeping original format."
    )

    if libreoffice_tried:
        logger.debug(
            "LibreOffice was available but failed to convert this file; it may be corrupted or use unsupported features. Try opening/converting it manually."
        )
        if last_soffice_error:
            logger.debug(f"LibreOffice stderr: {last_soffice_error}")
    else:
        logger.debug(
            "Tip: Install LibreOffice for automatic conversion, or convert manually."
        )

    return None
