"""Spec 01 entrypoint only. Does not claim or process jobs."""

import logging
import signal
from threading import Event

from call_summary.api import database_ready
from call_summary.storage import S3Storage


def main():
    logging.basicConfig(level=logging.INFO)
    database_ready()
    S3Storage().ready()
    stopped = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    logging.getLogger(__name__).info(
        "Infrastructure ready; job processing is not implemented (spec 03)"
    )
    stopped.wait()


if __name__ == "__main__":
    main()
