import struct
import tomlkit
from collections.abc import Iterable
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, model_validator

# https://docs.python.org/3/library/struct.html#byte-order-size-and-alignment
_BYTE_ORDER_CHARS = ['@', '=', '<', '>', '!']
# https://docs.python.org/3/library/struct.html#format-characters
_FORMAT_CHARS_SIZE = {
    'b': 1,
    'c': 1,
    '?': 1,
    'h': 2,
    'i': 4,
    'l': 4,
    'q': 8,
    'e': 2,
    'f': 4,
    'd': 8,  # double
}


class LogLevel(str, Enum):
    debug = 'debug'
    info = 'info'
    warning = 'warning'
    error = 'error'


class Backend(str, Enum):
    pyocd = 'pyocd'
    pyswd = 'pyswd'
    openocd = 'openocd'
    mock = 'mock'


class LinePlotConfig(BaseModel):
    axis: str = 'default'
    type: Literal['plot', 'stem', 'scatter'] = 'plot'
    kwargs: dict[str, Any] = {}


class AttrDict(dict):
    """Dict subclass allowing attribute access for expression dot syntax.

    Also supports integer key access mapped to string keys
    (e.g., d[0] → d['0']), useful for array member access in expr.
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __getitem__(self, key):
        if isinstance(key, int) and str(key) in self and key not in self:
            return super().__getitem__(str(key))
        return super().__getitem__(key)

    def __repr__(self):
        return f'AttrDict({dict.__repr__(self)})'


class Var(BaseModel):
    name: str
    address: int | str | None = None
    format: str | None = None
    value: int | float | list | None = None
    struct: list | None = None
    plot: LinePlotConfig | dict[str, LinePlotConfig] | bool = LinePlotConfig()
    expr: str | dict[str, str] | None = None

    @model_validator(mode='after')
    def _validate_var(self):
        # Write var with expr doesn't make sense
        if self.value is not None and self.expr is not None:
            raise ValueError(
                f"Var '{self.name}': 'expr' cannot be used with 'value' (write var)"
            )
        # Non-computed var must have address and format
        if self.address is None and self.expr is None:
            raise ValueError(
                f"Var '{self.name}': 'address' is required when 'expr' is not set"
            )
        if self.format is None and self.expr is None:
            raise ValueError(
                f"Var '{self.name}': 'format' is required when 'expr' is not set"
            )
        # Computed var should not have address/format
        if self.address is not None and self.expr is not None and self.format is None:
            raise ValueError(
                f"Var '{self.name}': computed var (no format) should not have 'address'"
            )
        # Computed var (expr only) must use string expr, not dict
        if self.is_computed and isinstance(self.expr, dict):
            raise ValueError(
                f"Var '{self.name}': pure computed var must use a string expr, not dict"
            )
        return self

    @property
    def is_computed(self) -> bool:
        """True when this var has no address — purely computed from expr."""
        return self.address is None

    @property
    def byte_order(self):
        if self.format is None:
            return None
        if self.format[0] in _BYTE_ORDER_CHARS:
            return self.format[0]
        else:
            return None

    @property
    def n_bytes(self):
        if self.format is None:
            return 0
        format_chars = self.format.lower()
        if format_chars[0] in _BYTE_ORDER_CHARS:
            format_chars = format_chars[1:]
        sizes = [_FORMAT_CHARS_SIZE[c] for c in format_chars]
        return sum(sizes)

    @property
    def n_values(self):
        if self.format is None:
            return 0
        format_chars = self.format.lower()
        if format_chars[0] in _BYTE_ORDER_CHARS:
            format_chars = format_chars[1:]
        return len(format_chars)

    @property
    def type(self):
        if self.struct:
            return dict
        elif isinstance(self.expr, dict):
            return dict
        elif self.format is not None and self.n_values > 1:
            return dict
        else:
            return 'value'

    @property
    def is_write(self):
        return self.value is not None

    def unpack(self, raw_data: bytes | list[int]) -> int | AttrDict:
        if isinstance(raw_data, list):
            byte_order = self.byte_order if self.byte_order is not None else ''
            raw_data = struct.pack(byte_order + 'B' * len(raw_data), *raw_data)
        data = struct.unpack(self.format, raw_data)
        if self.struct is not None:
            value = unpack_var_struct(self.struct, data)
        elif len(data) == 1:
            value = data[0]
        else:
            value = AttrDict({str(i): v for i, v in enumerate(data)})
        return value


class SaveConfig(BaseModel):
    enable: bool = True
    dir: str = 'data'
    name: str | None = None
    auto_name: bool = True
    override: bool = False
    data_filename: str = 'data'
    metadata_filename: str = 'metadata'
    config_filename: str = 'config'
    save_figure: bool = False
    save_config: bool = True
    metadata_indent: int | str | bool = 2


class ExtraConfig(BaseModel):
    metadata: dict = {}
    data: dict = {}


class FigureConfig(BaseModel):
    name: str
    axes: list[list[str | bool] | str | bool] | str
    figsize: tuple[float, ...] | None = None
    sharex: bool | Literal['none', 'all', 'row', 'col'] = False
    sharey: bool | Literal['none', 'all', 'row', 'col'] = False
    layout: None | Literal['constrained', 'compressed', 'tight',
                           'none'] = 'tight'


class AxisConfig(BaseModel):
    kwargs: dict[str, Any] = {}


class PlotConfig(BaseModel):
    show: bool = True
    figures: list[FigureConfig] = [
        FigureConfig(name='default', axes=['default'])
    ]
    axes: dict[str, AxisConfig] = {'default': AxisConfig()}


class MonConfig(BaseModel):
    view_window: float = 10.0
    refresh_interval: int = 10
    queue_size: int = 0
    linewidth: int = 2
    theme: Literal['light', 'dark'] = 'light'
    downsampling: bool = True
    antialias: bool = False
    use_opengl: bool = False
    status_interval: int = 1000
    probe_interpolation: bool = False


class PyOCDBackendConfig(BaseModel):
    target: str | None = None


class OpenOCDBackendConfig(BaseModel):
    host: str = 'localhost'
    port: int = 4444


class MockBackendConfig(BaseModel):
    sigma: float = 5.0


class BackendConfig(BaseModel):
    name: Backend | None = None
    serial_no: str = ''
    freq: int = 0
    pyocd: PyOCDBackendConfig = PyOCDBackendConfig()
    openocd: OpenOCDBackendConfig = OpenOCDBackendConfig()
    mock: MockBackendConfig = MockBackendConfig()


class Config(BaseModel):
    """Configuration class."""
    log_level: LogLevel = LogLevel.info
    save: SaveConfig = SaveConfig()
    rw_freq: float | None = None
    backend: BackendConfig = BackendConfig()
    rw_freq_warning_tolerance: float = 0.001
    rw_freq_error_tolerance: float = 0.01
    elf_file: str | None = None
    pre_delay: float = 0.
    post_delay: float = 0.
    pre_vars: list[Var] = []
    vars: list[Var]
    post_vars: list[Var] = []
    plot: PlotConfig = PlotConfig()
    mon: MonConfig = MonConfig()
    extra: ExtraConfig = ExtraConfig()

    @model_validator(mode='after')
    def _validate_config(self):
        for var_list, label in [(self.pre_vars, 'pre_vars'),
                                (self.vars, 'vars'),
                                (self.post_vars, 'post_vars')]:
            names = [v.name for v in var_list]
            seen = set()
            for name in names:
                if name in seen:
                    raise ValueError(f"Duplicate var name '{name}' in {label}")
                seen.add(name)
        return self


def unpack_var_struct(struct: Iterable, values: Iterable):
    data = {}
    for k, v in zip(struct, values):
        if not k.startswith('_'):
            data[k] = v
    return data


def load_config(path):
    with open(path) as f:
        config_dict = tomlkit.load(f).unwrap()
    config = Config(**config_dict)
    return config
