# Proxy package so `python -m app.*` works from the repository root
# This file maps the top-level `app` package to the real package located at `src/app`.
# This avoids requiring `poetry install` to run `python -m app.main` during development.
import os

# Compute absolute path to src/app
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_app = os.path.abspath(os.path.join(_repo_root, "src", "app"))

# Replace package search path for this package with the src/app directory
# Python will look inside this path when importing submodules like app.main
__path__ = [_src_app]

# Optional: expose package metadata (delegated to real package)
# from importlib.metadata import metadata
# try:
#     __version__ = metadata("ai-agent-trade-claude")["Version"]
# except Exception:
#     __version__ = "0.0.0"

