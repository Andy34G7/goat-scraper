# GOATScraper 🐐

Automatically download course materials (slides, PDFs) from PESU Academy.

## Features

- Fuzzy search through 16,000+ courses using `fzf`
- Regex pattern matching to download multiple courses at once
- Batch download all materials for a course
- Control concurrent downloads with `PDF_FETCHER_MAX_WORKERS` (env var) or `--max-workers N` CLI flag (overrides env var; default: 5)
- Use `--verbose` to enable detailed per-file logging (defaults to concise mode)
- Provide multiple course codes by repeating `-c`/`--course-code` (e.g., `-c CODE1 -c CODE2`), by supplying a single space- or comma-separated `-c` value (e.g., `-c "CODE1 CODE2"`), or use `-p/--pattern` to match many courses with a regex
- Automatic PDF merging per unit and ESA (all units combined)
- Stores SHA-256 checksums in the course summary JSON to avoid unnecessary re-downloads and re-merges when re-running the script
- Organized directory structure by units
- Login with credentials from `.env` file
- Interactive mode for selective downloads

## Installation

```bash
# Install fzf (required for fuzzy search)
brew install fzf

# Install dependencies
uv sync
```

## Usage

### Setup credentials

Create a `.env` file with your PESU Academy credentials:

```bash
PESU_USERNAME=your_srn_here
PESU_PASSWORD=your_password_here
```

### Run the fetcher

```bash
# Download a specific course
uv run main.py -c COURSE_CODE

# Download all courses matching a regex pattern
uv run main.py -p 'UE23CS3.*'           # All UE23 CS 3rd year courses
uv run main.py -p 'UE23CS341.*'         # All courses starting with UE23CS341
uv run main.py -p 'UE23CS342AA[1-4]'    # Elective bucket AA1 to AA4
uv run main.py -p 'UE23CS342BA.*'       # All BA bucket electives
uv run main.py -p 'UE23CS343BB.*'       # All BB bucket electives
uv run main.py -p '.*BlockChain'        # All courses with "BlockChain" in name

# Download specific units only
uv run main.py -c UE23CS343AB2 -u 1,3   # Download units 1 and 3

# Download with class range filter
uv run main.py -c UE23CS343AB2 -u 2 --class-range 1-5

# Skip PDF merging (keep only individual files)
uv run main.py -c UE23CS343AB2 --no-merge

# List units without downloading
uv run main.py -c UE23CS343AB2 --list-units
```

### Workflow

1. **Select a course** - Search through all available courses using fzf
2. **Choose download mode**:
  - Option 1: Batch download ALL materials (recommended)
  - Option 2: Interactive - select specific unit/class
3. **Wait** - PDFs are automatically downloaded and organized

### Output Structure

```
frontend/public/courses/
  course20972_UE23CS341A-Software-Engineering/
    unit_1_Introduction/
      01_Introduction.pdf
      02_Requirements.pdf
      ...
      UE23CS341A-Software-Engineering_u1_merged.pdf  # All unit 1 PDFs combined
    unit_2_Design/
      01_...pdf
      ...
      UE23CS341A-Software-Engineering_u2_merged.pdf  # All unit 2 PDFs combined
    unit_3_.../
    unit_4_.../
    UE23CS341A-Software-Engineering_ESA.pdf          # All 4 units combined (ESA prep)
    UE23CS341A-Software-Engineering_course_summary.json
    UE23CS341A-Software-Engineering_failures.log     # Only created if errors occur
```

## How it Works

The script uses the following PESU Academy API endpoints:

1. `/Academy/a/g/getSubjectsCode` - Get all course codes
2. `/Academy/a/i/getCourse/[course_id]` - Get units for a course
3. `/Academy/a/i/getCourseClasses/[unit_id]` - Get classes in a unit
4. `/Academy/s/studentProfilePESUAdmin` - Get PDF download links
5. `/Academy/a/referenceMeterials/downloadslidecoursedoc/[id]` - Download PDF

All data is saved to JSON files for reference.

## Usage Warning

- FOR ACADEMIC AND EDUCATIONAL USE ONLY
- The author is not responsible for misuse or violations resulting from improper use of this software.

## Credits

Akshaj my 🐐