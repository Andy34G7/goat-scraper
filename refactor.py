import os
from pathlib import Path

with open("main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_lines(start, end):
    return "".join(lines[start-1:end])

# --- IMPORTS ---
common_imports = "".join(lines[0:36])

utils_imports = common_imports + """
from pypdf import PdfMerger
"""

converter_imports = common_imports + """
from .utils import _is_zip_container, _is_pdf, _looks_like_html, _truthy_env, logger
"""

client_imports = common_imports + """
from .utils import logger
from .converter import convert_to_pdf
"""

batch_imports = common_imports + """
from .utils import logger, compute_combined_sha, _unique_existing_pdfs, merge_pdfs
from .client import PESUPDFFetcher, AuthenticationError
from .converter import convert_to_pdf
"""

cli_imports = common_imports + """
from .utils import logger, update_courses_index
from .client import PESUPDFFetcher, AuthenticationError
from .batch import batch_download_all, generate_esa_pdf
"""

# Ensure dir
Path("scraper").mkdir(exist_ok=True)

# --- UTILS ---
utils_content = utils_imports + "\n"
utils_content += get_lines(43, 95) # logger
utils_content += get_lines(103, 133) # update_courses_index
utils_content += get_lines(141, 167) # file conversion utils
utils_content += get_lines(1640, 1688) # sha
utils_content += get_lines(1691, 1759) # merge
with open("scraper/utils.py", "w", encoding="utf-8") as f:
    f.write(utils_content)

# --- CONVERTER ---
converter_content = converter_imports + "\n"
converter_content += get_lines(170, 171) # _should_keep_repaired_artifacts
converter_content += get_lines(174, 192) # _list_office_sources
converter_content += get_lines(195, 230) # _validate_and_retry
converter_content += get_lines(233, 257) # _unique_existing
converter_content += get_lines(260, 636) # convert_to_pdf
with open("scraper/converter.py", "w", encoding="utf-8") as f:
    f.write(converter_content)

# --- CLIENT ---
client_content = client_imports + "\n"
client_content += get_lines(644, 647) # AuthenticationError
client_content += get_lines(650, 653) # PDFDownloadError
client_content += get_lines(656, 1601) # PESUPDFFetcher
with open("scraper/client.py", "w", encoding="utf-8") as f:
    f.write(client_content)

# --- BATCH ---
batch_content = batch_imports + "\n"
batch_content += get_lines(1762, 1850) # generate_esa
batch_content += get_lines(1853, 2428) # batch_download_all
with open("scraper/batch.py", "w", encoding="utf-8") as f:
    f.write(batch_content)

# --- CLI ---
cli_content = cli_imports + "\n"
cli_content += get_lines(1609, 1637) # print_table
cli_content += get_lines(2431, 2843) # interactive_mode
cli_content += get_lines(2846, 3082) # main
with open("scraper/cli.py", "w", encoding="utf-8") as f:
    f.write(cli_content)

with open("scraper/__init__.py", "w", encoding="utf-8") as f:
    f.write('"""PESU Academy PDF Fetcher - Scraper Package"""\n')

print("Refactoring complete.")
