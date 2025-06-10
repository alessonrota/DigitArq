# erro_logger.py
import logging, pathlib

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_ARQ = LOG_DIR / "erro.log"

logging.basicConfig(
    filename=LOG_ARQ,
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
