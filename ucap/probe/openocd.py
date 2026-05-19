import logging
import re
import socket
import struct
from collections.abc import Callable, Iterable

from ucap.config import BackendConfig, Var
from ucap.constants import LOGGER_NAME, MAX_FREQ
from ucap.probe import ProbeConnectionError
from ucap.probe.base import BaseProbe

logger = logging.getLogger(LOGGER_NAME)


class OpenOCDProbe(BaseProbe):

    def __init__(self, cfg: BackendConfig):
        super().__init__(cfg.serial_no)
        try:
            oc = cfg.openocd
            self._sock = socket.create_connection((oc.host, oc.port),
                                                  timeout=5)
            self._buffer = b''
            self._recv_until_prompt()
            if cfg.freq >= 0:
                freq_khz = MAX_FREQ // 1000 if cfg.freq == 0 else cfg.freq // 1000
                self._cmd(f'adapter speed {freq_khz}')
            logger.warning('serial number: unavailable via OpenOCD')
        except (OSError, ConnectionError) as e:
            raise ProbeConnectionError(f'OpenOCD connection failed: {e}')

    def _recv_until_prompt(self) -> str:
        while b'> ' not in self._buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError('OpenOCD connection closed')
            self._buffer += chunk
        text = self._buffer.decode('utf-8', errors='replace')
        self._buffer = b''
        return text

    def _cmd(self, cmd: str) -> str:
        self._sock.sendall((cmd + '\n').encode())
        return self._recv_until_prompt()

    def read_mem(self, address: int, n_bytes: int) -> list[int]:
        resp = self._cmd(f'mdb {hex(address)} {n_bytes}')
        hex_bytes = re.findall(r'\b([0-9a-fA-F]{2})\b', resp)
        return [int(b, 16) for b in hex_bytes[:n_bytes]]

    def write_mem(self, address: int, data: list[int]) -> None:
        for i, b in enumerate(data):
            self._cmd(f'mwb {hex(address + i)} {b}')

    def get_func_args(self, var: Var) -> tuple[Callable, list]:
        n_bytes = var.n_bytes
        is_write = var.value is not None

        if is_write:
            value = var.value
            if not isinstance(value, Iterable):
                value = [value]
            value_raw = struct.pack(var.format, *value)
            value_blist = list(value_raw)
            return (self.write_mem, [var.address, value_blist])
        else:
            return (self.read_mem, [var.address, n_bytes])

    def close(self) -> None:
        if hasattr(self, '_sock'):
            self._sock.close()
