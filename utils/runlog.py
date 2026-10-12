"""
Log em arquivo para execuções sem ninguém olhando (daemon, cron, systemd).

Duplica tudo que vai para stdout/stderr — inclusive a saída do rich — em
data/logs/<nome>_YYYY-MM-DD.log, sem os códigos de cor ANSI.
"""

import re
import sys
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

LOG_DIR        = Path(__file__).parent.parent / "data" / "logs"
_ANSI_RE       = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_RETENTION_DAYS = 60


class _Tee:
    def __init__(self, original, log_file):
        self._original = original
        self._log      = log_file

    def write(self, text):
        self._original.write(text)
        self._log.write(_ANSI_RE.sub("", text))
        return len(text)

    def flush(self):
        self._original.flush()
        self._log.flush()

    def __getattr__(self, name):          # isatty, encoding etc. do terminal real
        return getattr(self._original, name)


def _prune_old_logs():
    cutoff = time.time() - _RETENTION_DAYS * 86_400
    for f in LOG_DIR.glob("*.log"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)


@contextmanager
def log_to_file(name: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _prune_old_logs()
    path = LOG_DIR / f"{name}_{date.today().isoformat()}.log"
    with open(path, "a", encoding="utf-8") as log:
        out, err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(out, log), _Tee(err, log)
        try:
            yield path
        finally:
            sys.stdout, sys.stderr = out, err
