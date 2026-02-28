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
import json
import logging
import argparse
import getpass
from typing import Optional, Dict, List, Any
from pathlib import Path
from colorama import Fore, Style
from .utils import logger, update_courses_index
from .client import PESUPDFFetcher, AuthenticationError
from .batch import batch_download_all

def print_table(items: List[Dict[str, Any]], keys: List[str], title: str = "") -> None:
    """Pretty print a list of dictionaries as a table."""
    if not items:
        print("No items to display")
        return

    if title:
        print(f"\n{title}")
        print("=" * len(title))

    # Calculate column widths
    widths = {}
    for key in keys:
        widths[key] = len(key)
        for item in items:
            value = str(item.get(key, ""))
            widths[key] = max(widths[key], len(value))

    # Print header
    header = " | ".join(key.ljust(widths[key]) for key in keys)
    print(f"\n{header}")
    print("-" * len(header))

    # Print rows
    for item in items:
        row = " | ".join(str(item.get(key, "")).ljust(widths[key]) for key in keys)
        print(row)

    print()
def interactive_mode(
    fetcher: PESUPDFFetcher,
    course_code: Optional[str] = None,
    unit_filter: Optional[List[int]] = None,
    class_filter: Optional[List[int]] = None,
    list_units: bool = False,
    skip_merge: bool = False,
    output_dir: Optional[str] = None,
    max_workers: Optional[int] = None,
) -> None:
    """Run the PDF fetcher in interactive mode with optional filters."""

    try:
        # Step 1: Get subject codes
        subjects = fetcher.get_subjects_code()
        if not subjects:
            print("\n❌ Failed to fetch subjects. Exiting.")
            return

        # Save all subjects to JSON file
        subjects_file = Path("courses.json")
        with open(subjects_file, "w", encoding="utf-8") as f:
            json.dump(subjects, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved all {len(subjects)} courses to {subjects_file}")

        # If course_code provided via CLI flag, use it directly
        if course_code:
            # Check if it's a regex pattern (used internally when --pattern is passed)
            if course_code.startswith("PATTERN:"):
                import re

                pattern = course_code[8:]  # Remove "PATTERN:" prefix
                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                    matches = [
                        s
                        for s in subjects
                        if regex.search(s["subjectCode"])
                        or regex.search(s.get("subjectName", ""))
                    ]

                    if not matches:
                        print(f"\n❌ No courses found matching pattern '{pattern}'")
                        return

                    print(
                        f"\n✓ Found {len(matches)} course(s) matching pattern '{pattern}'"
                    )
                    for match in matches:
                        print(f"  - {match['subjectCode']}: {match['subjectName']}")

                    # Download all matching courses
                    for idx, match in enumerate(matches, 1):
                        print(f"\n{'='*60}")
                        print(
                            f"[{idx}/{len(matches)}] Processing: {match['subjectCode']}"
                        )
                        print(f"{'='*60}")

                        course_id = match["id"]
                        course_name = match["subjectName"]
                        subject_code = match["subjectCode"]

                        # Create course directory
                        clean_name = (
                            course_name.split("-", 1)[-1].strip()
                            if "-" in course_name
                            else course_name
                        )
                        safe_name = "".join(
                            c if c.isalnum() or c in (" ", "-") else "-"
                            for c in clean_name
                        ).strip()
                        safe_name = "-".join(safe_name.split())

                        base_dir_env = output_dir or os.getenv(
                            "BASE_DIR", "frontend/public/courses"
                        )
                        base_dir = Path(__file__).parent / base_dir_env
                        base_dir.mkdir(parents=True, exist_ok=True)
                        course_dir = (
                            base_dir / f"course{course_id}_{subject_code}-{safe_name}"
                        )
                        course_dir.mkdir(exist_ok=True)

                        # Download all materials for this course
                        batch_download_all(
                            fetcher,
                            course_id,
                            course_name,
                            course_dir,
                            unit_filter,
                            class_filter,
                            skip_merge,
                            max_workers=max_workers,
                        )

                    return

                except re.error as e:
                    print(f"\n❌ Invalid regex pattern: {e}")
                    return

            # Try to match by ID first, then by subject code
            course_match = next(
                (
                    s
                    for s in subjects
                    if s["id"] == course_code or s["subjectCode"] == course_code
                ),
                None,
            )
            if not course_match:
                print(f"\n❌ Course code '{course_code}' not found.")
                print(
                    "Hint: Use course ID or subject code (e.g., '20975' or 'UE23CS342AA3')"
                )
                return
            course_id = course_match["id"]
            course_name = course_match["subjectName"]
            print(
                f"\n{Fore.GREEN}✓{Style.RESET_ALL} Using course: {course_name} (ID: {course_id})"
            )
        else:
            # Use fzf for fuzzy finding
            print(f"\nLaunching fzf to search through {len(subjects)} courses...")

            try:
                import subprocess

                # Prepare fzf input with format: "ID | Code | Name"
                fzf_input = "\n".join(
                    [
                        f"{s['id']} | {s['subjectCode']} | {s['subjectName']}"
                        for s in subjects
                    ]
                )

                # Run fzf
                result = subprocess.run(
                    ["fzf", "--prompt=Select course: ", "--height=40%", "--reverse"],
                    input=fzf_input,
                    text=True,
                    capture_output=True,
                )

                if result.returncode != 0:
                    print("No course selected. Exiting.")
                    return

                # Extract course ID from selected line
                selected = result.stdout.strip()
                if not selected:
                    print("No course selected. Exiting.")
                    return

                # Parse the selected line and extract course ID
                parts = selected.split(" | ")
                course_id = parts[0].strip()
                course_name = " | ".join(parts[1:]) if len(parts) > 1 else selected
                print(f"\n✓ Selected: {course_name}")

            except FileNotFoundError:
                logger.error("fzf not found. Please install fzf: brew install fzf")
                print("\nFalling back to manual search...")
                print("Enter course ID or search term: ", end="")
                search_term = input().strip()

                if search_term.lower() == "q":
                    print("Exiting...")
                    return

                if search_term.isdigit():
                    course_id = search_term
                    # Find the course name
                    course_match = next(
                        (s for s in subjects if s["id"] == course_id), None
                    )
                    course_name = (
                        course_match["subjectName"]
                        if course_match
                        else f"Course {course_id}"
                    )
                else:
                    # Fallback fuzzy search
                    matches = [
                        s
                        for s in subjects
                        if search_term.lower() in s.get("subjectName", "").lower()
                    ]
                    if not matches:
                        print(f"\n❌ No courses found matching '{search_term}'")
                        return
                    if len(matches) == 1:
                        course_id = matches[0]["id"]
                        course_name = matches[0]["subjectName"]
                        print(f"\n✓ Selected: {course_name}")
                    else:
                        print_table(
                            matches[:20],
                            ["id", "subjectCode", "subjectName"],
                            f"Found {len(matches)} matches",
                        )
                        print("\nEnter course ID: ", end="")
                        course_id = input().strip()
                        course_match = next(
                            (s for s in subjects if s["id"] == course_id), None
                        )
                        course_name = (
                            course_match["subjectName"]
                            if course_match
                            else f"Course {course_id}"
                        )

        if course_id.lower() == "q":
            print("Exiting...")
            return

        # Create course directory with format: course{id}_{subjectCode-Course-Name}
        subject_match = next((s for s in subjects if s["id"] == course_id), None)
        subject_code = subject_match["subjectCode"] if subject_match else course_id

        # Clean course name (remove subject code prefix if present)
        clean_name = (
            course_name.split("-", 1)[-1].strip() if "-" in course_name else course_name
        )
        safe_name = "".join(
            c if c.isalnum() or c in (" ", "-") else "-" for c in clean_name
        ).strip()
        safe_name = "-".join(safe_name.split())  # Replace spaces with hyphens

        # If --list-units flag is set, just list units and exit
        if list_units:
            units = fetcher.get_course_units(course_id)
            if units:
                print(f"\n{Fore.CYAN}Units for {course_name}:{Style.RESET_ALL}")
                for idx, unit in enumerate(units, 1):
                    print(f"  {idx}. {unit['unit']}")
            else:
                print("\n❌ Failed to fetch units.")
            return

        # Load base directory from environment variable or use default
        base_dir_env = output_dir or os.getenv("BASE_DIR", "frontend/public/courses")
        base_dir = Path(__file__).parent / base_dir_env
        base_dir.mkdir(parents=True, exist_ok=True)
        course_dir = base_dir / f"course{course_id}_{subject_code}-{safe_name}"
        course_dir.mkdir(exist_ok=True)

        # If course_code was provided via CLI, automatically download all materials
        if course_code:
            batch_download_all(
                fetcher,
                course_id,
                course_name,
                course_dir,
                unit_filter,
                class_filter,
                skip_merge,
                max_workers=max_workers,
            )
            return

        # Ask for download mode only in interactive mode
        print("\nDownload mode:")
        print("  1. Download ALL materials (all units, all classes)")
        print("  2. Interactive (select specific unit/class)")
        print("\nChoice (1/2, default=1): ", end="")
        mode = input().strip() or "1"

        if mode == "1":
            batch_download_all(
                fetcher, course_id, course_name, course_dir, max_workers=max_workers
            )
            return

        # Continue with interactive mode...
        # Step 2: Get course units
        units = fetcher.get_course_units(course_id)
        if not units:
            print("\n❌ Failed to fetch units for this course. Exiting.")
            return

        # Save units to JSON file
        units_file = course_dir / "units.json"
        with open(units_file, "w", encoding="utf-8") as f:
            json.dump(units, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved {len(units)} units to {units_file}")

        # Display units
        print_table(
            units, ["id", "unit", "unitNumber"], f"Units for Course {course_id}"
        )

        # Use fzf for unit selection
        print("\nLaunching fzf to select unit...")

        try:
            import subprocess

            # Prepare fzf input
            fzf_input = "\n".join([f"{u['id']} | {u['unit']}" for u in units])

            result = subprocess.run(
                ["fzf", "--prompt=Select unit: ", "--height=40%", "--reverse"],
                input=fzf_input,
                text=True,
                capture_output=True,
            )

            if result.returncode != 0:
                print("No unit selected. Exiting.")
                return

            selected = result.stdout.strip()
            if not selected:
                print("No unit selected. Exiting.")
                return

            unit_id = selected.split(" | ")[0].strip()
            print(
                f"\n✓ Selected unit: {selected.split(' | ')[1] if len(selected.split(' | ')) > 1 else unit_id}"
            )

        except FileNotFoundError:
            # Fallback to manual input
            print("\nEnter unit ID to continue (or 'q' to quit): ", end="")
            unit_id = input().strip()

            if unit_id.lower() == "q":
                print("Exiting...")
                return

        # Step 3: Get unit classes
        classes = fetcher.get_unit_classes(unit_id)
        if not classes:
            print("\n❌ Failed to fetch classes for this unit. Exiting.")
            return

        # Save classes to JSON file
        classes_file = course_dir / f"unit_{unit_id}_classes.json"
        with open(classes_file, "w", encoding="utf-8") as f:
            json.dump(classes, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved {len(classes)} classes to {classes_file}")

        # Display classes
        display_keys = [
            k
            for k in ["id", "className", "classType", "date", "topic"]
            if k in (classes[0] if classes else {})
        ]
        print_table(classes, display_keys, f"Classes for Unit {unit_id}")

        # Use fzf for class selection
        print("\nLaunching fzf to select class...")

        try:
            import subprocess

            # Prepare fzf input
            fzf_input = "\n".join([f"{c['id']} | {c['className']}" for c in classes])

            result = subprocess.run(
                ["fzf", "--prompt=Select class: ", "--height=40%", "--reverse"],
                input=fzf_input,
                text=True,
                capture_output=True,
            )

            if result.returncode != 0:
                print("No class selected. Exiting.")
                return

            selected = result.stdout.strip()
            if not selected:
                print("No class selected. Exiting.")
                return

            class_id = selected.split(" | ")[0].strip()
            print(
                f"\n✓ Selected class: {selected.split(' | ')[1] if len(selected.split(' | ')) > 1 else class_id}"
            )

        except FileNotFoundError:
            # Fallback to manual input
            print("\nEnter class ID to download PDF (or 'q' to quit): ", end="")
            class_id = input().strip()

            if class_id.lower() == "q":
                print("Exiting...")
                return

        # Step 4: Download PDF
        print("\nEnter output filename (press Enter for default): ", end="")
        filename = input().strip()

        if filename:
            output_path = Path(filename)
        else:
            # Default: save in course directory
            output_path = course_dir / f"class_{class_id}.pdf"

        success = fetcher.download_pdf(course_id, class_id, output_path)

        if success:
            print("\n✓ PDF download completed successfully!")
        else:
            print("\n❌ PDF download failed.")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="PESU Academy PDF Fetcher - Download course materials automatically",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all materials for a course
  python main.py -c UE23CS343AB2
  
  # Download all courses matching a pattern (regex)
  python main.py -p "UE23CS3.*"
  python main.py -p "UE23CS341.*"
  python main.py -p ".*BlockChain"
  
  # Download specific units only
  python main.py -c UE23CS343AB2 -u 1,3
  
  # Download specific unit with class range
  python main.py -c UE23CS343AB2 -u 2 --class-range 1-5
  
  # List available units without downloading
  python main.py -c UE23CS343AB2 --list-units
  
  # Skip merge (keep individual PDFs only)
  python main.py -c UE23CS343AB2 --no-merge
        """,
    )
    parser.add_argument(
        "-c",
        "--course-code",
        action="append",
        type=str,
        help="Course code/ID to download directly (can be given multiple times to process several courses; skips interactive selection)",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        help="Regex pattern to match course codes (e.g., 'UE23CS3.*' or 'UE23CS341.*'). Downloads all matching courses.",
    )
    parser.add_argument(
        "-u",
        "--units",
        type=str,
        help="Comma-separated unit numbers to download (e.g., '1,3,4' or '1-3'). Downloads all units if not specified.",
    )
    parser.add_argument(
        "--class-range",
        type=str,
        help="Range of class numbers to download within each unit (e.g., '1-5' or '3,5,7')",
    )
    parser.add_argument(
        "--list-units",
        action="store_true",
        help="List all units for the course without downloading",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip merging PDFs into a single file per unit",
    )
    parser.add_argument(
        "--update-index",
        action="store_true",
        help="Only update the courses index.json file (no download)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Override concurrency for parallel downloads (overrides PDF_FETCHER_MAX_WORKERS env var).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG) for detailed per-file messages",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Custom output directory (default: frontend/public/courses)",
    )
    args = parser.parse_args()

    # Respect --verbose flag (enable debug logs) if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Handle --update-index flag (no login required)
    if args.update_index:
        from dotenv import load_dotenv

        load_dotenv()
        base_dir_env = os.getenv("BASE_DIR", "frontend/public/courses")
        base_dir = Path(__file__).parent / base_dir_env
        if base_dir.exists():
            update_courses_index(base_dir)
            print(f"✓ Updated index.json in {base_dir}")
        else:
            print(f"❌ Courses directory not found: {base_dir}")
        return

    # Parse unit filter (e.g., "1,3,4" or "1-3")
    unit_filter = None
    if args.units:
        unit_filter = []
        for part in args.units.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                unit_filter.extend(range(start, end + 1))
            else:
                unit_filter.append(int(part))

    # Parse class filter (e.g., "1-5" or "3,5,7")
    class_filter = None
    if args.class_range:
        class_filter = []
        for part in args.class_range.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                class_filter.extend(range(start, end + 1))
            else:
                class_filter.append(int(part))

    print(f"{Fore.CYAN}{Style.BRIGHT}  \\_()_/{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  (o.o){Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  /) (\\  {Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}  goat-scraper{Style.RESET_ALL}")
    print()

    # Load credentials from .env file
    try:
        from dotenv import load_dotenv

        load_dotenv()

        username = os.getenv("PESU_USERNAME")
        password = os.getenv("PESU_PASSWORD")

        if username and password:
            logger.info(f"Loaded credentials from .env for user: {username}")
        else:
            # Fallback to manual input
            print("Enter your PESU Academy credentials:")
            username = input("Username (SRN): ").strip()
            password = getpass.getpass("Password: ").strip()
    except ImportError:
        # If dotenv not available, ask for manual input
        print("Enter your PESU Academy credentials:")
        username = input("Username (SRN): ").strip()
        password = getpass.getpass("Password: ").strip()

    if not username or not password:
        print("❌ Username and password are required.")
        sys.exit(1)

    # Create fetcher and login
    fetcher = PESUPDFFetcher(username, password)

    try:
        fetcher.login()

        # Handle pattern flag by converting it to a special course_code format
        # Normalize course-code inputs: accept multiple -c flags or a single space/comma-separated string
        if args.course_code:
            normalized_codes: List[str] = []
            for raw in args.course_code:
                if not raw:
                    continue
                # Allow either space or comma separated lists in a single -c value
                parts = raw.replace(",", " ").split()
                for p in parts:
                    p_clean = p.strip()
                    if p_clean:
                        normalized_codes.append(p_clean)
            args.course_code = normalized_codes if normalized_codes else None

        # Decide course(s) to process
        if args.pattern:
            if args.course_code:
                print(
                    "⚠️  Warning: Both --course-code and --pattern provided. Using --pattern."
                )
            course_code_arg = f"PATTERN:{args.pattern}"

            # Pattern mode: single interactive_mode invocation will handle multiple matches
            interactive_mode(
                fetcher,
                course_code_arg,
                unit_filter,
                class_filter,
                args.list_units,
                args.no_merge,
                args.output,
                args.max_workers,
            )
        else:
            # Non-pattern mode: allow multiple -c values (action=append or space-separated). If none provided, go into interactive selection.
            if args.course_code:
                for provided_code in args.course_code:
                    print(
                        f"{Fore.BLUE}Processing course:{Style.RESET_ALL} {provided_code}"
                    )
                    interactive_mode(
                        fetcher,
                        provided_code,
                        unit_filter,
                        class_filter,
                        args.list_units,
                        args.no_merge,
                        args.output,
                        args.max_workers,
                    )
            else:
                # No course provided: enter interactive selection
                interactive_mode(
                    fetcher,
                    None,
                    unit_filter,
                    class_filter,
                    args.list_units,
                    args.no_merge,
                    args.output,
                    args.max_workers,
                )

    except AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        fetcher.logout()
