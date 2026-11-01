"""
Vercel entry point: Vercel runs this file as a Python serverless function and calls `app`.
vercel.json sends every /api/... request here; Django sees the original path.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402  (needs the path set above)

app = get_wsgi_application()
