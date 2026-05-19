import random
import struct
from collections.abc import Callable, Iterable

from ucap.config import BackendConfig, Var
from ucap.probe.base import BaseProbe

_FMT_RANGE = {
    'b': (-128, 127),
    'B': (0, 255),
    'h': (-32768, 32767),
    'H': (0, 65535),
    'i': (-2**31, 2**31 - 1),
    'I': (0, 2**32 - 1),
    'l': (-2**31, 2**31 - 1),
    'L': (0, 2**32 - 1),
    'q': (-2**63, 2**63 - 1),
    'Q': (0, 2**64 - 1),
}


class MockProbe(BaseProbe):

    def __init__(self,
                 cfg: BackendConfig,
                 memory: dict[int, list[int]] | None = None):
        super().__init__(cfg.serial_no)
        self._mem: dict[int, int] = {}
        self._sigma = cfg.mock.sigma
        if memory:
            for addr, data in memory.items():
                for i, b in enumerate(data):
                    self._mem[addr + i] = b


    def _ensure(self, address: int, n_bytes: int) -> None:
        for i in range(n_bytes):
            if address + i not in self._mem:
                self._mem[address + i] = 0

    def read_mem(self, address: int, n_bytes: int) -> list[int]:
        self._ensure(address, n_bytes)
        return [self._mem[address + i] for i in range(n_bytes)]

    def write_mem(self, address: int, data: list[int]) -> None:
        for i, b in enumerate(data):
            self._mem[address + i] = b

    def get_serial_no(self) -> str:
        return super().get_serial_no() or 'MOCK-00000000'

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
            sigma = self._sigma
            if sigma > 0:
                fmt = var.format
                byte_order = var.byte_order if var.byte_order is not None else ''
                fmt_chars = fmt.lstrip('@=<>!')

                def _read_with_noise(address: int, n: int) -> list[int]:
                    raw = self.read_mem(address, n)
                    packed = struct.pack(byte_order + 'B' * n, *raw)
                    values = list(struct.unpack(fmt, packed))
                    for i, (v, c) in enumerate(zip(values, fmt_chars)):
                        noisy = random.gauss(v, sigma)
                        if isinstance(v, int):
                            noisy = int(round(noisy))
                            rng = _FMT_RANGE.get(c)
                            if rng is not None:
                                lo, hi = rng
                                noisy = max(lo, min(hi, noisy))
                        values[i] = noisy
                    return list(struct.pack(fmt, *values))

                return (_read_with_noise, [var.address, n_bytes])
            else:
                return (self.read_mem, [var.address, n_bytes])
