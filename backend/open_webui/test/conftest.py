import os
import tempfile

# Must run before any open_webui import — env.py / db.py / config.py read these at import time.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["WEBUI_AUTH"] = "False"
os.environ["ENABLE_DB_MIGRATIONS"] = "True"
os.environ["WEBUI_SECRET_KEY"] = "test-secret"
os.environ["FRONTEND_BUILD_DIR"] = "/nonexistent"
os.environ["DATA_DIR"] = tempfile.mkdtemp()

# Avoid deleting static dir
os.environ["STATIC_DIR"] = tempfile.mkdtemp()
