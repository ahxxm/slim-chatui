import logging
import sys


def configure_logging():
    # Alembic's fileConfig (via alembic.ini) resets root to WARN/stderr during migrations.
    # Re-apply our format after startup.
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
