import logging
import time
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from multiprocessing.synchronize import Event as MpEvent
from typing import Any

from ucap.config import Config, Var
from ucap.constants import LOG_FORMAT, LOGGER_NAME
from ucap.expression import apply_expr
from ucap.probe import ProbeConnectionError, create_probe, rw_vars

logger = logging.getLogger(LOGGER_NAME)


def _get_var_members(var: Var) -> list[str] | None:
    """Get member suffix list for a dict/struct var, or None for single-value vars."""
    if isinstance(var.expr, dict):
        if var.struct is not None:
            return [m for m in var.struct if not m.startswith('_')]
        if var.n_values > 1:
            return [str(i) for i in range(var.n_values)]
        return list(var.expr)
    if var.type is dict:
        if var.struct is not None:
            return [m for m in var.struct if not m.startswith('_')]
        return [str(i) for i in range(var.n_values)]
    return None


def build_mon_channels(vars: list[Var]) -> list[str]:
    """Build channel list from Var.mon config."""
    channels = []
    for var in vars:
        if var.is_write:
            continue
        members = _get_var_members(var)
        if members is not None:
            channels.extend(f'{var.name}.{m}' for m in members)
        else:
            channels.append(var.name)
    return channels


def channels_to_var_data(vars: list[Var], times: list[float],
                         ch_data: dict[str, list]) -> dict:
    """Convert flat channel data back to var data format (compatible with `show`)."""
    var_data = {}
    for var in vars:
        if var.is_write:
            continue
        n = len(times)
        members = _get_var_members(var)
        if members is not None:
            struct_data = {}
            for m in members:
                struct_data[m] = ch_data.get(f'{var.name}.{m}', [None] * n)
            var_data[var.name] = struct_data
        else:
            var_data[var.name] = list(ch_data.get(var.name, []))
    return var_data


def interpolate_at(times: Sequence, values: Sequence,
                   x: float) -> float | None:
    """Linearly interpolate values at x, or nearest if only 1 point."""
    if len(times) == 0:
        return None
    if len(times) == 1:
        return float(values[0])
    idx = bisect_left(times, x)
    if idx <= 0:
        return float(values[0])
    if idx >= len(times):
        return float(values[-1])
    t0, t1 = times[idx - 1], times[idx]
    v0, v1 = values[idx - 1], values[idx]
    ratio = (x - t0) / (t1 - t0) if t1 != t0 else 0.0
    return float(v0 + ratio * (v1 - v0))


def snap_at(times: Sequence, x: float) -> tuple[int, float]:
    """Find nearest data point index and its time value."""
    if not times:
        return 0, 0.0
    idx = bisect_left(times, x)
    if idx == len(times):
        idx = len(times) - 1
    elif idx > 0 and (x - times[idx - 1]) < (times[idx] - x):
        idx -= 1
    return idx, times[idx]


def reader_process(cfg: Config, queue: Any, stop_event: MpEvent,
                   pause_event: MpEvent):
    """Run in a separate process: connect to probe, read variables, send data."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(cfg.log_level.upper())

    try:
        dev = create_probe(cfg)
    except ProbeConnectionError as e:
        queue.put(('error', {'message': str(e)}))
        return

    try:
        logger.info("monitor reader process started")

        if cfg.post_vars:
            logger.warning('post_vars is ignored in monitor mode')

        timestamp_pre = time.time()
        if cfg.pre_vars:
            pre_data = rw_vars(dev, cfg.pre_vars)
        else:
            pre_data = {}
        logger.debug(pre_data)

        if cfg.pre_delay > 0:
            logger.info(f'pre_delay (s): {cfg.pre_delay}')
            time.sleep(cfg.pre_delay)

        vars = [r for r in cfg.vars if not r.is_write]
        hw_vars = [r for r in vars if not r.is_computed]
        vars_dict = {r.name: r for r in vars}

        rw_funcs = {r.name: dev.get_func_args(r) for r in hw_vars}
        rw_func_pairs = [(r.name, rw_funcs[r.name]) for r in hw_vars]

        rw_freq = cfg.rw_freq
        delta = 1 / rw_freq if rw_freq else 0
        t0 = time.perf_counter()
        t_target = 0

        timestamp = time.time()
        queue.put(('init', {
            'timestamp_pre': timestamp_pre,
            'timestamp': timestamp,
            'pre_data': pre_data,
            'serial': dev.get_serial_no(),
        }))

        while not stop_event.is_set():
            if pause_event.is_set():
                time.sleep(0.05)
                continue

            if delta > 0:
                t_iter_start = time.perf_counter()
                t_target = t_iter_start + delta

            timestamp = time.perf_counter() - t0

            local_values = {}
            namespace_data = {}
            for var_name, (read_func, args) in rw_func_pairs:
                raw = read_func(*args)
                if raw is None:
                    continue
                value = vars_dict[var_name].unpack(raw)
                r = vars_dict[var_name]
                namespace_data[r.name] = value
                if isinstance(value, dict):
                    for k, v in value.items():
                        local_values[f'{var_name}.{k}'] = v
                else:
                    local_values[var_name] = value

            apply_expr(vars, namespace_data, batch=False)

            for var in vars:
                if var.expr is not None:
                    result = namespace_data[var.name]
                    if isinstance(result, dict):
                        for k, v in result.items():
                            local_values[f'{var.name}.{k}'] = v
                    else:
                        local_values[var.name] = result

            if local_values:
                queue.put((timestamp, local_values))

            if delta > 0:
                remaining = t_target - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)

        logger.info("monitor reader process stopped")
    finally:
        dev.close()


class MonitorModel:
    """Local data buffer — single-process cache of the reader's output."""

    def __init__(self, channels: list[str]):
        self._time_buffer: list[float] = []
        self._data_buffer: dict[str, list] = {ch: [] for ch in channels}

    @property
    def is_empty(self) -> bool:
        return len(self._time_buffer) == 0

    @property
    def time_start(self) -> float:
        return self._time_buffer[0] if self._time_buffer else 0.0

    @property
    def time_end(self) -> float:
        return self._time_buffer[-1] if self._time_buffer else 0.0

    @property
    def size(self) -> int:
        return len(self._time_buffer)

    def append(self, timestamp: float, values: dict[str, float]):
        self._time_buffer.append(timestamp)
        for ch, v in values.items():
            self._data_buffer[ch].append(v)

    def clear(self):
        self._time_buffer.clear()
        for buf in self._data_buffer.values():
            buf.clear()

    def time_to_index(self, t: float) -> int:
        return bisect_right(self._time_buffer, t)

    def channel_size(self, ch: str) -> int:
        return len(self._data_buffer.get(ch, []))

    def get_times(self, start: int, end: int) -> list[float]:
        return self._time_buffer[start:end]

    def get_data(self, ch: str, start: int, end: int) -> list:
        return self._data_buffer[ch][start:end]

    def memory_estimate(self) -> int:
        return (self.size * 8 +
                sum(len(v) * 8 for v in self._data_buffer.values()))

    def read_frequency(self, n: int = 100) -> float:
        if self.size < 2:
            return 0.0
        n = min(self.size, n)
        dt = self._time_buffer[-1] - self._time_buffer[-n]
        return (n - 1) / dt if dt > 0 else 0.0

    def elapsed(self) -> float:
        if self.size < 2:
            return 0.0
        return self._time_buffer[-1] - self._time_buffer[0]
