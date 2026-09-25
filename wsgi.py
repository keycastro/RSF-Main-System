from pathlib import Path
import zipfile

_bundle = Path(__file__).resolve().with_name("rsf_unified_code_bundle.zip")
if _bundle.is_file():
    with zipfile.ZipFile(_bundle, "r") as _zf:
        _zf.extractall(Path(__file__).resolve().parent)

from app import create_app

app = create_app()
application = app
