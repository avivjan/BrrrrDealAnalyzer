"""Email the nightly result. Thin wrapper: the implementation lives in ``nightly/`` next to this file.

    nightly_e2e_email.py <playwright.json>              send
    nightly_e2e_email.py <playwright.json> <out.html>   render only
    nightly_e2e_email.py --help                         every option
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from nightly.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv))
