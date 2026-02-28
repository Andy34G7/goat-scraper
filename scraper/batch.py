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
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from pypdf import PdfWriter
from colorama import Fore, Style
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import (
    logger,
    compute_combined_sha,
    merge_pdfs,
    compute_file_sha256,
    setup_logger,
    update_courses_index,
)
from .client import PESUPDFFetcher
from .converter import (
    convert_to_pdf,
    _validate_and_retry_office_conversions,
    _list_office_sources,
    _unique_existing_pdfs,
)

def generate_esa_pdf(course_dir: Path, course_prefix: str) -> bool:
    """Generate ESA PDF by combining all 4 unit merged PDFs."""
    try:
        # Find all unit merged PDFs
        merged_pdfs = []
        for unit_num in range(1, 5):
            # Look for unit directories
            unit_dirs = list(course_dir.glob(f"unit_{unit_num}_*"))
            if not unit_dirs:
                continue

            # Look for merged PDF in this unit directory
            unit_dir = unit_dirs[0]
            merged_pdf_pattern = f"{course_prefix}_u{unit_num}_merged.pdf"
            merged_pdf_files = list(unit_dir.glob(merged_pdf_pattern))

            if merged_pdf_files:
                merged_pdfs.append((unit_num, merged_pdf_files[0]))

        if len(merged_pdfs) == 0:
            logger.warning(
                f"No merged PDFs found for ESA generation in {course_dir.name}"
            )
            return False

        # Sort by unit number
        merged_pdfs.sort(key=lambda x: x[0])

        # Create ESA PDF
        esa_pdf_path = course_dir / f"{course_prefix}_ESA.pdf"

        # Compute combined SHA of unit merged PDFs and skip if ESA is up-to-date
        combined = compute_combined_sha([pdf for _, pdf in merged_pdfs])
        if esa_pdf_path.exists():
            try:
                existing = compute_file_sha256(esa_pdf_path)
                if existing == combined:
                    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} (up-to-date)")
                    logger.debug(
                        f"Skipping ESA generation; ESA PDF up-to-date: {esa_pdf_path.name}"
                    )
                    return True
            except Exception:
                pass

        print(
            f"  {Fore.BLUE}Creating ESA PDF from {len(merged_pdfs)} unit(s)...{Style.RESET_ALL} ",
            end="",
            flush=True,
        )

        merger = PdfWriter()
        for unit_num, pdf_path in merged_pdfs:
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                try:
                    merger.append(str(pdf_path))
                except Exception as e:
                    logger.warning(f"Failed to add unit {unit_num} to ESA PDF: {e}")
                    continue

        if len(merger.pages) == 0:
            print(f"{Fore.RED}✗{Style.RESET_ALL}")
            logger.warning("No valid PDFs to merge for ESA")
            return False

        with open(esa_pdf_path, "wb") as f:
            merger.write(f)

        merger.close()
        print(f"{Fore.GREEN}✓{Style.RESET_ALL}")
        # Compute and log ESA PDF SHA (do not write sidecar)
        try:
            esa_sha = compute_file_sha256(esa_pdf_path)
        except Exception:
            esa_sha = None

        logger.info(
            f"✓ Created ESA PDF: {esa_pdf_path.name} ({esa_pdf_path.stat().st_size:,} bytes)"
        )
        if esa_sha:
            logger.info(f"ESA PDF sha256: {esa_sha}")
        return True

    except Exception as e:
        print(f"{Fore.RED}✗{Style.RESET_ALL}")
        logger.error(f"FAILURE [generate_esa_pdf]: Failed to generate ESA PDF - {e}")
        logger.error(f"Course Directory: {course_dir}")
        logger.error(f"Course Prefix: {course_prefix}")
        return False
def batch_download_all(
    fetcher: PESUPDFFetcher,
    course_id: str,
    course_name: str,
    course_dir: Path,
    unit_filter: Optional[List[int]] = None,
    class_filter: Optional[List[int]] = None,
    skip_merge: bool = False,
    max_workers: Optional[int] = None,
) -> None:
    """
    Download all PDFs for units in a course automatically.

    Args:
        fetcher: The PDF fetcher instance
        course_id: Course ID to download
        course_name: Course name
        course_dir: Directory to save files
        unit_filter: List of unit numbers to download (None = all units)
        class_filter: List of class numbers to download per unit (None = all classes)
        skip_merge: If True, don't merge PDFs into single file per unit
    """
    print(
        f"{Fore.YELLOW}{Style.BRIGHT}Batch Download - All Course Materials{Style.RESET_ALL}"
    )

    # Setup course-specific failure log using same naming as directory

    subject_match = next(
        (s for s in fetcher.get_subjects_code() or [] if s["id"] == course_id), None
    )
    subject_code = subject_match["subjectCode"] if subject_match else course_id

    clean_name = (
        course_name.split("-", 1)[-1].strip() if "-" in course_name else course_name
    )
    safe_name = "".join(
        c if c.isalnum() or c in (" ", "-") else "-" for c in clean_name
    ).strip()
    safe_name = "-".join(safe_name.split())

    course_prefix = f"{subject_code}-{safe_name}"
    course_log_file = course_dir / f"{course_prefix}_failures.log"

    # Reconfigure logger with course-specific log file
    global logger
    logger = setup_logger("pdf_fetcher", course_log_file)

    # Get all units
    units = fetcher.get_course_units(course_id)

    # Load existing summary (if available) so we can avoid re-downloading/remaring unchanged files
    existing_summary = None
    summary_file_path = course_dir / f"{course_prefix}_course_summary.json"
    if summary_file_path.exists():
        try:
            with open(summary_file_path, "r", encoding="utf-8") as sf:
                existing_summary = json.load(sf)
        except Exception:
            existing_summary = None
    if not units:
        print("\n❌ Failed to fetch units.")
        return

    # Filter units if specified
    if unit_filter:
        filtered_units = [
            (idx, u) for idx, u in enumerate(units, 1) if idx in unit_filter
        ]
        if not filtered_units:
            print(f"\n❌ No units found matching filter: {unit_filter}")
            return
        print(
            f"{Fore.MAGENTA}Found {len(units)} total units. Downloading {len(filtered_units)} unit(s): {unit_filter}{Style.RESET_ALL}"
        )
        units_to_process = filtered_units
    else:
        print(
            f"{Fore.MAGENTA}Found {len(units)} units. Starting download...{Style.RESET_ALL}"
        )
        units_to_process = list(enumerate(units, 1))

    total_downloaded = 0
    total_failed = 0

    # Prepare summary data
    import datetime

    summary = {
        "course_id": course_id,
        "course_name": course_name,
        "download_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_units": len(units),
        "filtered_units": len(units_to_process) if unit_filter else None,
        "units": [],
        "failure_log": course_log_file.name,
    }

    for unit_idx, unit in units_to_process:
        unit_id = unit["id"]
        unit_name = unit["unit"]

        print(
            f"\n{Fore.CYAN}[{unit_idx}/{len(units)}]{Style.RESET_ALL} {Fore.WHITE}{Style.BRIGHT}{unit_name}{Style.RESET_ALL}"
        )

        # Get classes
        classes = fetcher.get_unit_classes(unit_id)
        if not classes:
            print(f"  {Fore.YELLOW}⚠ No classes found{Style.RESET_ALL}")
            summary["units"].append(
                {
                    "unit_number": unit_idx,
                    "unit_id": unit_id,
                    "unit_name": unit_name,
                    "classes": [],
                    "total_files": 0,
                    "failed_files": 0,
                    "merged_pdf": None,
                }
            )
            continue

        # Create unit directory - extract title after colon or use full name
        # Format: "Unit 1: Introduction" -> "Introduction" or "IoT  Analytics, Security & Privacy:" -> "IoT-Analytics-Security-Privacy"
        unit_title = (
            unit_name.split(":", 1)[-1].strip() if ":" in unit_name else unit_name
        )
        # Remove trailing colon if present
        unit_title = unit_title.rstrip(":")
        safe_unit_title = "".join(
            c if c.isalnum() or c in (" ", "-") else "-" for c in unit_title
        ).strip()
        safe_unit_title = "-".join(
            safe_unit_title.split()
        )  # Replace spaces with hyphens
        # Remove any trailing hyphens and empty strings
        safe_unit_title = safe_unit_title.strip("-")
        if not safe_unit_title:  # Fallback if title is empty
            safe_unit_title = f"Unit-{unit_idx}"
        unit_dir = course_dir / f"unit_{unit_idx}_{safe_unit_title}"
        unit_dir.mkdir(exist_ok=True)

        # Track downloaded PDFs for this unit
        unit_pdfs = []
        unit_summary = {
            "unit_number": unit_idx,
            "unit_id": unit_id,
            "unit_name": unit_name,
            "unit_directory": unit_dir.name,
            "classes": [],
            "total_files": 0,
            "failed_files": 0,
            "merged_pdf": None,
        }

        # Filter classes if specified
        classes_to_download = classes
        if class_filter:
            classes_to_download = [
                cls for idx, cls in enumerate(classes, 1) if idx in class_filter
            ]
            if not classes_to_download:
                print(
                    f"  {Fore.YELLOW}⚠ No classes match filter: {class_filter}{Style.RESET_ALL}"
                )
                summary["units"].append(unit_summary)
                continue
            print(f"  Filtering: {len(classes_to_download)}/{len(classes)} classes")

        # Helper function for parallel downloads
        def download_class(class_data: Tuple[int, Dict]) -> Tuple[Dict, List[Path]]:
            """Download a single class and return class info and downloaded files."""
            class_idx, cls = class_data
            class_id = cls["id"]
            class_name = cls["className"]

            # Safe filename with zero-padded numbering
            safe_name = "".join(
                c for c in class_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()[:50]
            padded_num = str(class_idx).zfill(2)  # 01, 02, 03, etc.
            output_path = unit_dir / f"{padded_num}_{safe_name}.pdf"

            class_info = {
                "class_number": class_idx,
                "class_id": class_id,
                "class_name": class_name,
                "files": [],
                "status": "failed",
            }

            # download_pdf now returns a list of downloaded file paths
            downloaded_files = fetcher.download_pdf(
                course_id,
                class_id,
                output_path,
                class_name,
                existing_summary=existing_summary,
            )

            return class_info, downloaded_files

        # Download classes in parallel with progress bar
        # Determine concurrency: CLI flag (max_workers param) overrides env var PDF_FETCHER_MAX_WORKERS or MAX_WORKERS; default 5
        workers = None
        if max_workers is not None:
            try:
                workers = int(max_workers)
                if workers <= 0:
                    raise ValueError("must be > 0")
            except Exception:
                logger.warning(
                    f"Invalid --max-workers='{max_workers}', falling back to env var or default"
                )
                workers = None

        if workers is None:
            _max_workers_env = os.getenv("PDF_FETCHER_MAX_WORKERS") or os.getenv(
                "MAX_WORKERS"
            )
            try:
                workers = int(_max_workers_env) if _max_workers_env is not None else 5
                if workers <= 0:
                    raise ValueError("must be > 0")
            except Exception:
                logger.warning(
                    f"Invalid PDF_FETCHER_MAX_WORKERS='{_max_workers_env}', falling back to 5"
                )
                workers = 5

        logger.debug(f"Using max_workers={workers} for concurrent downloads")

        # Configure non-blocking conversion executor (so conversion runs concurrently with other downloads)
        _conv_env = os.getenv("PDF_FETCHER_CONVERT_WORKERS")
        try:
            conv_workers = int(_conv_env) if _conv_env is not None else 2
            if conv_workers <= 0:
                raise ValueError("must be > 0")
        except Exception:
            logger.warning(
                f"Invalid PDF_FETCHER_CONVERT_WORKERS='{_conv_env}', falling back to 2"
            )
            conv_workers = 2

        logger.debug(f"Using convert_workers={conv_workers} for background conversions")

        conversion_executor = ThreadPoolExecutor(max_workers=conv_workers)
        conversion_futures = []
        import threading

        class_lock = threading.Lock()

        def _convert_and_attach(
            src_path: Path, cls_info: Dict[str, Any], orig_sha: Optional[str]
        ):
            """Convert src_path to PDF and attach metadata to cls_info in a thread-safe way."""
            try:
                # If PDF already exists (same stem), avoid re-conversion
                possible_pdf = src_path.with_suffix(".pdf")
                if possible_pdf.exists() and possible_pdf.stat().st_size > 0:
                    # Compute sha and attach if not already present
                    try:
                        pdf_sha = compute_file_sha256(possible_pdf)
                    except Exception:
                        pdf_sha = None

                    with class_lock:
                        cls_info["files"].append(
                            {
                                "filename": possible_pdf.name,
                                "file_size": possible_pdf.stat().st_size,
                                "file_type": "pdf",
                                "sha256": pdf_sha,
                                "orig_sha256": orig_sha,
                            }
                        )
                    return possible_pdf

                pdf_path = convert_to_pdf(src_path)
                if (
                    not pdf_path
                    or not pdf_path.exists()
                    or pdf_path.stat().st_size == 0
                ):
                    logger.warning(
                        f"Conversion failed or produced empty PDF for {src_path.name}"
                    )
                    return None

                try:
                    pdf_sha = compute_file_sha256(pdf_path)
                except Exception:
                    pdf_sha = None

                with class_lock:
                    cls_info["files"].append(
                        {
                            "filename": pdf_path.name,
                            "file_size": pdf_path.stat().st_size,
                            "file_type": "pdf",
                            "sha256": pdf_sha,
                            "orig_sha256": orig_sha,
                        }
                    )

                logger.debug(f"✓ Converted {src_path.name} -> {pdf_path.name}")
                return pdf_path

            except Exception as e:
                logger.warning(f"Conversion exception for {src_path.name}: {e}")
                return None

        with tqdm(
            total=len(classes_to_download),
            desc="  Downloading",
            unit="file",
            leave=False,
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ) as pbar:

            with ThreadPoolExecutor(max_workers=workers) as executor:
                # Submit all download tasks
                future_to_class = {
                    executor.submit(download_class, (idx, cls)): (idx, cls)
                    for idx, cls in enumerate(classes_to_download, 1)
                }

                # Process completed downloads as they finish
                for future in as_completed(future_to_class):
                    try:
                        class_info, downloaded_files = future.result()

                        class_name = class_info["class_name"]
                        pbar.set_postfix_str(
                            f"{class_name[:40]}..."
                            if len(class_name) > 40
                            else class_name
                        )

                        if downloaded_files:
                            total_downloaded += len(downloaded_files)
                            # downloaded_files is now a list of dicts {'path', 'original_sha', 'extension'}
                            # extend unit_pdfs with the Path objects for later conversion/merge
                            for item in downloaded_files:
                                # Support both legacy Path items and new dict items
                                if isinstance(item, dict):
                                    path = item["path"]
                                else:
                                    path = item
                                unit_pdfs.append(path)

                            # Update class info with all downloaded files and store SHA in-memory (no sidecar files written)
                            for item in downloaded_files:
                                if isinstance(item, dict):
                                    path = item["path"]
                                    extension = item.get(
                                        "extension", path.suffix.lstrip(".")
                                    )
                                    orig_sha = item.get("original_sha")
                                else:
                                    path = item
                                    extension = path.suffix.lstrip(".")
                                    orig_sha = None

                                if path.exists():
                                    try:
                                        file_sha = compute_file_sha256(path)
                                    except Exception:
                                        file_sha = None
                                    class_info["files"].append(
                                        {
                                            "filename": path.name,
                                            "file_size": path.stat().st_size,
                                            "file_type": extension,
                                            "sha256": file_sha,
                                            # original_sha only applies to the downloaded original (for converted files)
                                            "orig_sha256": orig_sha,
                                        }
                                    )

                            class_info["status"] = "success"
                            unit_summary["total_files"] += len(downloaded_files)

                            file_count_msg = (
                                f" ({len(downloaded_files)} files)"
                                if len(downloaded_files) > 1
                                else ""
                            )
                            pbar.write(
                                f"    {Fore.GREEN}✓{Style.RESET_ALL} {class_name}{file_count_msg}"
                            )
                        else:
                            # logger.error(
                            #     f"FAILURE [batch_download]: Failed to download class"
                            # )
                            # logger.error(f"  Unit: {unit_name}")
                            # logger.error(f"  Class: {class_name}")
                            # logger.error(f"  Class ID: {class_info['class_id']}")
                            total_failed += 1
                            unit_summary["failed_files"] += 1
                            pbar.write(f"    {Fore.RED}✗{Style.RESET_ALL} {class_name}")

                        unit_summary["classes"].append(class_info)
                        pbar.update(1)

                        # Schedule non-blocking conversions for any non-PDF files that were just downloaded
                        for item in downloaded_files:
                            if isinstance(item, dict):
                                path = item["path"]
                                extension = item.get(
                                    "extension", path.suffix.lstrip(".")
                                )
                                orig_sha = item.get("original_sha")
                            else:
                                path = item
                                extension = path.suffix.lstrip(".")
                                orig_sha = None

                            if extension != "pdf":
                                try:
                                    fut = conversion_executor.submit(
                                        _convert_and_attach, path, class_info, orig_sha
                                    )
                                    conversion_futures.append(fut)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to schedule conversion for {path.name}: {e}"
                                    )

                    except Exception as e:
                        idx, cls = future_to_class[future]
                        logger.error(f"Exception downloading class {idx}: {e}")
                        total_failed += 1
                        unit_summary["failed_files"] += 1
                        pbar.update(1)

        # Wait for background conversions to finish and collect converted PDFs
        converted_pdfs: List[Path] = []
        if conversion_futures:
            converted_count = 0
            for fut in as_completed(conversion_futures):
                try:
                    res = fut.result()
                    if res:
                        converted_pdfs.append(res)
                        converted_count += 1
                except Exception as e:
                    logger.warning(f"Background conversion task failed: {e}")
            logger.debug(
                f"Completed background conversions: {converted_count} converted"
            )

        # Always shutdown conversion executor for this unit (ensure threads cleaned up)
        try:
            conversion_executor.shutdown(wait=True)
        except Exception:
            pass

        # Ensure we didn't miss any PPTX->PDF conversions.
        # This guarantees: for every Office source in the unit dir, a corresponding valid PDF exists
        # or we explicitly report it as missing.
        try:
            total_sources, converted_sources, missing_sources = (
                _validate_and_retry_office_conversions(unit_dir)
            )
        except Exception as e:
            total_sources, converted_sources, missing_sources = (0, 0, [])
            logger.warning(f"Conversion validation failed for unit '{unit_name}': {e}")

        unit_summary["office_sources"] = total_sources
        unit_summary["office_converted"] = converted_sources
        unit_summary["office_missing"] = missing_sources

        if total_sources:
            if missing_sources:
                logger.error(
                    f"Missing PDF conversions in {unit_dir.name}: {len(missing_sources)}/{total_sources} source file(s) still have no PDF"
                )
                for name in missing_sources:
                    logger.error(f"  Missing PDF for: {name}")
                print(
                    f"  {Fore.YELLOW}Office conversion:{Style.RESET_ALL} {converted_sources}/{total_sources} (missing {len(missing_sources)})"
                )
            else:
                print(
                    f"  {Fore.GREEN}Office conversion:{Style.RESET_ALL} {converted_sources}/{total_sources}"
                )

        # Build a list of PDFs to merge: include existing PDFs, newly converted PDFs, and any PDFs
        # produced by the post-validation retry pass above. Then de-duplicate and validate.
        candidate_pdfs = [
            f for f in unit_pdfs if f.suffix.lower() == ".pdf"
        ] + converted_pdfs

        # Add any PDFs that exist on disk for Office sources (covers retry conversions)
        office_pdf_candidates: List[Path] = []
        try:
            for src in _list_office_sources(unit_dir):
                office_pdf_candidates.append(src.with_suffix(".pdf"))
        except Exception:
            office_pdf_candidates = []

        candidate_pdfs.extend(office_pdf_candidates)
        pdf_files_only = _unique_existing_pdfs(candidate_pdfs)

        # Helpful breakdown to explain "Conversion X/Y" vs "Merging N PDFs"
        converted_office_pdfs = _unique_existing_pdfs(office_pdf_candidates)
        converted_office_count = len(converted_office_pdfs)
        non_office_pdf_count = max(0, len(pdf_files_only) - converted_office_count)

        # Sort PDFs by filename to ensure correct order (01_, 02_, etc.)
        pdf_files_only.sort(key=lambda x: x.name)

        # Merge PDFs for this unit (non-PDF files will be skipped) unless --no-merge flag is set
        if pdf_files_only and not skip_merge:
            print(
                f"  {Fore.BLUE}Merging {len(pdf_files_only)} PDFs{Style.RESET_ALL} ({converted_office_count} converted + {non_office_pdf_count} already-PDF)... ",
                end="",
                flush=True,
            )
            merged_pdf_path = unit_dir / f"{course_prefix}_u{unit_idx}_merged.pdf"
            if merge_pdfs(pdf_files_only, merged_pdf_path):
                print(f"{Fore.GREEN}✓{Style.RESET_ALL}")
                unit_summary["merged_pdf"] = merged_pdf_path.name
                try:
                    merged_sha = compute_file_sha256(merged_pdf_path)
                    unit_summary["merged_pdf_sha"] = merged_sha
                except Exception:
                    unit_summary["merged_pdf_sha"] = None
            else:
                print(f"{Fore.RED}✗{Style.RESET_ALL}")
        elif pdf_files_only and skip_merge:
            logger.info("  Skipping merge (--no-merge flag set)")
        else:
            logger.debug(
                f"  No PDF files to merge for this unit (downloaded {len(unit_pdfs)} non-PDF files)"
            )

        # Sort classes by class_number to ensure proper order in JSON and merged PDF
        unit_summary["classes"].sort(key=lambda x: x["class_number"])

        summary["units"].append(unit_summary)

    # Add summary totals
    summary["total_downloaded"] = total_downloaded
    summary["total_failed"] = total_failed

    # Save summary to JSON file with course prefix
    summary_file = course_dir / f"{course_prefix}_course_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Generate ESA PDF (combining all 4 units) unless skip_merge is set
    if not skip_merge:
        print()
        esa_created = generate_esa_pdf(course_dir, course_prefix)
        if esa_created:
            esa_pdf_path = course_dir / f"{course_prefix}_ESA.pdf"
            try:
                summary["esa_pdf"] = esa_pdf_path.name
                summary["esa_pdf_sha"] = compute_file_sha256(esa_pdf_path)
            except Exception:
                summary["esa_pdf_sha"] = None

    # Update the courses index.json for the frontend API
    update_courses_index(course_dir.parent)

    print(
        f"{Fore.GREEN}{Style.BRIGHT}Complete!{Style.RESET_ALL} Downloaded: {Fore.GREEN}{total_downloaded}{Style.RESET_ALL}, Failed: {Fore.RED}{total_failed}{Style.RESET_ALL}"
    )
    print(f"{Fore.CYAN}Location:{Style.RESET_ALL} {course_dir}")
    print(f"{Fore.CYAN}Summary saved to:{Style.RESET_ALL} {summary_file}")
    if total_failed > 0:
        print(f"{Fore.YELLOW}Failure log:{Style.RESET_ALL} {course_log_file}")
