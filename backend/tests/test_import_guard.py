import sys
import pytest
from pathlib import Path

def test_no_obsolete_imports():
    import app.main  # ensure app is loaded
    
    forbidden_modules = [
        "app.providers.aviation",
        "app.providers.opensky_auth",
        "app.providers.bts_t100",
        "app.providers.faa_bulk",
        "app.providers.openflights",
        "pandas",
    ]
    
    for mod in forbidden_modules:
        assert mod not in sys.modules, f"Forbidden module {mod} was imported!"

def test_no_data_dir_usage():
    import app.main
    
    # Check that no file in app/ has a reference to "backend/data" or "/data/"
    # This is a simple text search over the codebase.
    app_dir = Path(__file__).parent.parent / "app"
    
    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "backend/data" not in content, f"Found 'backend/data' in {py_file}"
        # We allow 'data' as a variable name, but not as a path component like '"data/' or '/data/'
        assert '"data/' not in content, f"Found '\"data/' in {py_file}"
        assert "'data/" not in content, f"Found \"'data/\" in {py_file}"
