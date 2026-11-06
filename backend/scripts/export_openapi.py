"""Write the API schema that the web app's types are generated from.

Run from backend/: python -m scripts.export_openapi <path>. It only imports the app: no env vars.
"""

import json
import sys
from pathlib import Path

from app.main import app

Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2) + "\n")
