import os
import logging
import shutil
from pathlib import Path
from main import convert_to_pdf, setup_logger

logger = setup_logger()
logger.setLevel(logging.WARNING)

# Let's create a dummy broken zip
test_file = Path('broken.pptx')
with open(test_file, 'wb') as f:
    f.write(b"PK\x03\x04" + os.urandom(100))

pdf_file = convert_to_pdf(test_file)
if pdf_file and pdf_file.exists():
    print(f"Success! PDF created at: {pdf_file}")
else:
    print("Failed to convert PDF. Check warnings above.")

try: test_file.unlink()
except: pass
