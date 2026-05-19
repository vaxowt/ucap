import logging

from ucap.config import Backend, Config
from ucap.constants import LOGGER_NAME
from ucap.probe.base import BaseProbe


class ProbeConnectionError(Exception):
    """Raised when probe connection fails."""


from ucap.probe.core import (continuous_rw_vars, rw_vars,
                               unpack_continuous_data)
from ucap.probe.mock import MockProbe
from ucap.probe.openocd import OpenOCDProbe
from ucap.probe.pyocd import PyOCDProbe
from ucap.probe.pyswd import PySWDProbe

logger = logging.getLogger(LOGGER_NAME)


def create_probe(cfg: Config) -> BaseProbe:
    backend_cfg = cfg.backend
    logger.debug(f"backend '{backend_cfg.name}'")
    if backend_cfg.name == Backend.mock:
        logger.info('using mock backend')
        return MockProbe(backend_cfg)
    elif backend_cfg.name == Backend.pyswd:
        return PySWDProbe(backend_cfg)
    elif backend_cfg.name == Backend.openocd:
        return OpenOCDProbe(backend_cfg)
    else:
        return PyOCDProbe(backend_cfg)


__all__ = [
    'BaseProbe',
    'MockProbe',
    'PySWDProbe',
    'OpenOCDProbe',
    'PyOCDProbe',
    'ProbeConnectionError',
    'create_probe',
    'rw_vars',
    'continuous_rw_vars',
    'unpack_continuous_data',
]
