"""Minimal loguru stub — replaces the real loguru for environments where it's unavailable."""

import logging
import sys


class Logger:
    """Drop-in replacement for loguru.Logger using stdlib logging."""

    def __init__(self, name="loguru_stub"):
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def trace(self, msg, *args, **kwargs):
        pass  # noqa: unnecessary-pass

    def debug(self, msg, *args, **kwargs):
        self._logger.debug(self._fmt(msg, args), **kwargs)

    def info(self, msg, *args, **kwargs):
        self._logger.info(self._fmt(msg, args), **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._logger.warning(self._fmt(msg, args), **kwargs)

    def error(self, msg, *args, **kwargs):
        self._logger.error(self._fmt(msg, args), **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._logger.exception(self._fmt(msg, args), **kwargs)

    def _fmt(self, msg, args):
        return str(msg) % args if args else str(msg)

    def bind(self, **kwargs):
        return self

    def opt(self, **kwargs):
        return self

    def add(self, sink, **kwargs):
        handler = logging.StreamHandler(sink) if isinstance(sink, type(sys.stdout)) else logging.StreamHandler()
        self._logger.addHandler(handler)
        return handler

    def remove(self, handler_id=None):
        pass


logger = Logger()
