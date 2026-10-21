"""Configuração de logging da aplicação (substitui qualquer uso de `print`)."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configura o logger raiz uma única vez, no formato padrão da API."""
    root = logging.getLogger()
    if not any(getattr(h, "_reo", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler._reo = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level.upper())
