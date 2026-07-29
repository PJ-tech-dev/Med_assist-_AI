import logging
import sys
import time
from contextlib import contextmanager
from typing import Generator

# Configure root logger once
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def log_execution(logger: logging.Logger, label: str) -> Generator[None, None, None]:
    """Context manager that logs start, end, and elapsed time of a block."""
    logger.info("START — %s", label)
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        elapsed = time.perf_counter() - start
        logger.error("ERROR — %s | %.3fs | %s", label, elapsed, exc)
        raise
    else:
        elapsed = time.perf_counter() - start
        logger.info("END   — %s | %.3fs", label, elapsed)
