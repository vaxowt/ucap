import logging
import struct
from collections.abc import Callable, Iterable

from pyocd.core.helpers import ConnectHelper

from ucap.config import BackendConfig, Var
from ucap.constants import LOGGER_NAME, MAX_FREQ
from ucap.probe import ProbeConnectionError
from ucap.probe.base import BaseProbe

logger = logging.getLogger(LOGGER_NAME)


class PyOCDProbe(BaseProbe):

    def __init__(self, cfg: BackendConfig):
        super().__init__(cfg.serial_no)
        try:
            options: dict = dict(target_override=cfg.pyocd.target,
                                 connect_mode='attach')
            if cfg.freq == 0:
                options['frequency'] = MAX_FREQ
            elif cfg.freq > 0:
                options['frequency'] = cfg.freq
            self._session = ConnectHelper.session_with_chosen_probe(
                unique_id=cfg.serial_no,
                blocking=False,
                return_first=True,
                options=options)
            if self._session is None:
                raise ProbeConnectionError('no probe found')
            self._session.open()
            logger.info(f'serial number: {self.get_serial_no()}')
        except Exception as e:
            raise ProbeConnectionError(f"connection error: {e}")

    def get_serial_no(self) -> str:
        return self._session.probe.unique_id or super().get_serial_no()

    def get_func_args(self, var: Var) -> tuple[Callable, list]:
        n_bytes = var.n_bytes
        is_write = var.value is not None
        byte_order = var.byte_order if var.byte_order is not None else ''

        prefix = 'write' if is_write else 'read'

        func = getattr(self._session.board.target, f'{prefix}_memory_block8')
        args = [var.address, n_bytes]
        if is_write:
            value = var.value
            if not isinstance(value, Iterable):
                value = [value]
            value_raw = struct.pack(var.format, *value)
            value_blist = struct.unpack(byte_order + 'B' * n_bytes, value_raw)
            args = [var.address, value_blist]
        return (func, args)

    def close(self) -> None:
        self._session.close()
