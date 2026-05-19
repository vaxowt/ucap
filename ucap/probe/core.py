import logging
import signal
import time

from ucap.config import Var
from ucap.constants import LOGGER_NAME
from ucap.expression import apply_expr
from ucap.probe.base import BaseProbe

logger = logging.getLogger(LOGGER_NAME)


def rw_vars(probe: BaseProbe, vars: list[Var]) -> dict:
    hw_vars = [r for r in vars if not r.is_computed]
    rw_funcs = {var.name: probe.get_func_args(var) for var in hw_vars}

    data = {}
    for var in hw_vars:
        raw = rw_funcs[var.name][0](*rw_funcs[var.name][1])
        if raw is None:
            value = True
        else:
            value = var.unpack(raw)
        data[var.name] = value

    apply_expr(vars, data, batch=False)
    return data


def continuous_rw_vars(probe: BaseProbe, vars: list[Var],
                       freq: float | None = None) -> tuple[list[float], dict]:
    hw_vars = [r for r in vars if not r.is_computed]
    rw_funcs = {var.name: probe.get_func_args(var) for var in hw_vars}

    vars = dict(stop=False)

    def sigint_handler(sig, frame):
        vars["stop"] = True

    prev_handler = signal.signal(signal.SIGINT, sigint_handler)

    if freq is not None and freq > 0:
        delta = 1 / freq
    else:
        delta = -1

    raw_data = {var.name: [] for var in hw_vars}
    print("start ... (press CTRL-C to exit)", end="", flush=True)
    times = [time.perf_counter()]
    while not vars["stop"]:
        if (time.perf_counter() - times[-1]) < delta:
            continue
        times.append(time.perf_counter())
        for var in hw_vars:
            val = rw_funcs[var.name][0](*rw_funcs[var.name][1])
            raw_data[var.name].append(val)
    print(" stop")
    signal.signal(signal.SIGINT, prev_handler)
    return times[1:], raw_data


def unpack_continuous_data(vars: list[Var], raw_data: dict) -> dict:
    hw_vars = [r for r in vars if not r.is_computed]
    data = {}
    for var in hw_vars:
        var_data = {}
        for raw in raw_data[var.name]:
            if raw is None:
                value = True
            else:
                value = var.unpack(raw)
            if isinstance(value, dict):
                for k, v in value.items():
                    a = var_data.get(k, [])
                    a.append(v)
                    var_data[k] = a
            else:
                a = var_data.get('_val', [])
                a.append(value)
                var_data['_val'] = a
        if '_val' in var_data:
            var_data = var_data['_val']
        data[var.name] = var_data
    apply_expr(vars, data, batch=True)
    return data
