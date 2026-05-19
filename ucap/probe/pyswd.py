import logging
import struct
from collections.abc import Callable, Iterable

import swd
from swd.stlink.usb import NoDeviceFoundException

from ucap.config import BackendConfig, Var
from ucap.constants import LOGGER_NAME, MAX_FREQ
from ucap.probe import ProbeConnectionError
from ucap.probe.base import BaseProbe

logger = logging.getLogger(LOGGER_NAME)


class PySWDProbe(BaseProbe):

    def __init__(self, cfg: BackendConfig):
        super().__init__(cfg.serial_no)
        try:
            if cfg.freq == 0:
                freq = MAX_FREQ
            elif cfg.freq < 0:
                freq = None
            else:
                freq = cfg.freq
            self._dev = swd.Swd(swd_frequency=freq, serial_no=cfg.serial_no)
            logger.info(self._dev.get_version().str)
            logger.info(f'serial number: {self.get_serial_no()}')
        except NoDeviceFoundException:
            raise ProbeConnectionError('ST-Link not found')
        except Exception as e:
            raise ProbeConnectionError(f'connection error: {e}')

    def get_serial_no(self) -> str:
        return self._dev._drv._com.usb._dev.serial_no or super().get_serial_no()

    def get_func_args(self, var: Var) -> tuple[Callable, list]:
        n_bytes = var.n_bytes
        is_write = var.value is not None
        address = var.address

        prefix = 'write' if is_write else 'read'
        suffix = min(n_bytes * 8, 32)

        if suffix > 8 and address % (suffix // 8) != 0:
            logger.warning(
                f"Var '{var.name}' address 0x{address:x} is not {suffix // 8}-byte "
                f"aligned, using single-byte reads/writes. Performance may degrade."
            )
            suffix = 8

        func = getattr(self._dev._drv._com, f'{prefix}_mem{suffix}')
        args = [var.address, n_bytes]
        if is_write:
            value = var.value
            if not isinstance(value, Iterable):
                value = [value]
            value_raw = struct.pack(var.format, *value)
            args = [var.address, value_raw]
        return (func, args)
