# uCap

> A non-invasive DAP-based tool for MCU data acquisition, monitoring, and visualization.

[中文文档](docs/README.zh.md)

<p align="center">
  <video src="https://github.com/user-attachments/assets/5b1926d9-4c7e-4628-97e3-223b6fda863d" controls width="500px"></video>
</p>

## Features

- **Non-invasive** — reads/writes MCU memory via DAP (SWD/JTAG); no code changes or debug printf required
- **Dual modes** — headless CLI (`ucap rw`) for fast batch acquisition, or GUI monitor (`ucap mon`) for live visualization
- **Multiple backends** — pyOCD, pySWD, OpenOCD; works with ST-Link, DAP-Link, and more
- **On-the-fly expressions** — transform raw register values with math expressions (scaling, unit conversion, formulas)
- **Struct-aware** — unpack packed C structs into named fields automatically
- **ELF symbol resolution** — use variable names from your firmware instead of raw addresses
- **Rich plotting** — multi-figure / multi-axis layouts with line, stem, and scatter plot types
- **Save & replay** — captured data is saved and can be re-plotted offline

## Installation

```bash
pip install python-ucap
```

If using ST-Link V3 with pyswd backend, you need to install the [latest pyswd](https://github.com/cortexm/pyswd):

```bash
git clone https://github.com/cortexm/pyswd
cd pyswd
pip install .
```

## Quick Start

Connect your MCU debugger (e.g. ST-Link, DAP-Link) to the target board, then create a config file `my_config.toml`. Set `target` to match your MCU (use `pyocd list --targets` to list supported chips; `cortex_m` is a generic fallback):

```toml
rw_freq = 100

[backend]
name = 'pyocd'

[backend.pyocd]
target = 'cortex_m'

[save]
enable = true
dir = 'data'
name = 'session1'
auto_name = false

[plot]
show = true

[[vars]]
name = 'sensor'
address = 0x20000000
format = '<f'
```

Run data acquisition (press Ctrl+C to stop):

```bash
ucap rw -c my_config.toml
```

A matplotlib window will open after completion.

Re-plot saved data anytime:

```bash
ucap show -d data/session1
```

See [`examples/simple.toml`](examples/simple.toml) for a minimal config, [`docs/config-reference.toml`](docs/config-reference.toml) for all available options, and [`docs/data-format.md`](docs/data-format.md) for the captured data structure.

## Concepts

### Variables

A `[[vars]]` entry in config describes a variable in the target MCU's memory space that ucap will read and/or write. The `address` field accepts a raw hex address, a peripheral register name (e.g. `ADC1->DR`, `TIM2->CNT`), or a C global variable name — peripheral register and global variable symbols are all resolved from the ELF/DWARF debug info when an ELF file is specified via the `--elf` CLI option or the `elf_file` config key.

| Field     | Description                                                                                                      |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| `name`    | Identifier used in saved data and plots                                                                          |
| `address` | Hex address, peripheral register name, or C global variable name (resolved via `--elf` / `elf_file` in config)    |
| `format`  | [struct format string](https://docs.python.org/3/library/struct.html#format-strings) for packing/unpacking bytes |
| `value`   | If set, the variable is **write-only** (written every cycle); omit for read                                      |
| `struct`  | List of field names to unpack multi-field data into a dict                                                       |
| `expr`    | Expression to transform the read value (e.g. `'x * 3.3 / 4096'`); can reference other vars                       |
| `plot`    | Axis assignment and plot type (line / stem / scatter)                                                            |

**Read vs Write**: Without `value`, the variable is read from the target each cycle. With `value`, it is written to the target each cycle.

**Struct**: When a variable occupies multiple fields (e.g. a C struct or packed flags), use `struct` to split it:

```toml
[[vars]]
name = 'status'
address = 0x20000040
format = '<BBH'
struct = ['flags', '_pad0', 'counter']
```

Fields starting with `_` are discarded. The remaining fields become separately plottable.

**Expression**: Apply scaling or computation on the fly. See [`docs/expression.md`](docs/expression.md) for the full reference of supported math functions and expression modes:

```toml
[[vars]]
name = 'temperature'
address = 0x4001204C
format = '<H'
expr = '(x * 3.3 / 4096 - 0.76) / 0.0025 + 25'
```

**Symbol name instead of raw address**: Set `elf_file` in config (or pass `--elf` on the CLI) to resolve C variable names to addresses automatically:

```toml
[[vars]]
name = 'adc_value'
address = 'ADC1->DR'    # resolved from ELF/DWARF
format = '<H'

[[vars]]
name = 'system_tick'
address = 'sys_tick_count'   # any global variable works
format = '<I'
```

No need to look up datasheet memory maps or update addresses after firmware changes — the symbol name follows the code. Use `ucap sym -e firmware.elf` to explore available symbols.

### Pre / Post Variables

`[[pre_vars]]` and `[[post_vars]]` are single-shot variable groups read before (or after) the continuous acquisition loop. Useful for capturing static configuration or calibration values:

```toml
[[pre_vars]]
name = 'device_id'
address = 0xE0042000
format = '<I'

[[post_vars]]
name = 'status_at_end'
address = 0x200000F0
format = '<H'
```

Pre/post data is saved in `metadata.json` under `pre_data` and `post_data`.

## Usage

### `ucap rw` — Continuous Read/Write

Headless batch-mode data acquisition. Reads/writes target variables continuously at the configured frequency. No GUI overhead — the fastest mode. Press **Ctrl+C** to stop; then saves data and plots with matplotlib.

```bash
ucap rw -c path/to/config.toml
```

You can specify the ELF file via the `--elf` CLI option or the `elf_file` config key, so configs can use C variable names in `address` instead of raw hex:

```bash
ucap rw -c path/to/config.toml --elf path/to/firmware.elf
```

```toml
# config.toml
elf_file = 'path/to/firmware.elf'
```

This makes configs more readable and resilient — addresses update automatically when firmware changes, and there's no need to cross-check linker maps or datasheet memory layouts.

### `ucap mon` — Real-time Monitor

Real-time read/write with live plotting GUI.

```bash
ucap mon -c path/to/config.toml
```

### `ucap show` — Plot Saved Data

Re-plots data previously captured by `ucap rw` or `ucap mon` using matplotlib. The config is auto-loaded from the data directory if available.

```bash
ucap show -d path/to/data_dir
```

### `ucap sym` — List ELF Symbols

Lists all global variables (and their types / struct members) from an ELF file. Useful for finding variable addresses when writing configs.

```bash
ucap sym -e path/to/firmware.elf
```

Filter by regex pattern:

```bash
ucap sym -e path/to/firmware.elf "TIM|ADC"
```

Interactive filtering with fzf:

```bash
ucap sym -e path/to/firmware.elf | fzf
```

## Shell Completion

Tab completion is supported for bash / zsh / fish / powershell:

```bash
# bash
eval "$(ucap completion bash)"

# zsh
eval "$(ucap completion zsh)"

# fish
ucap completion fish | source

# powershell
ucap completion powershell | Out-String | Invoke-Expression
```

Add the eval line to `~/.bashrc`, `~/.zshrc`, fish config, or PowerShell `$PROFILE` to enable permanently.

## Backend Support

| Backend   | Description                                  | Dependency                                |
| --------- | -------------------------------------------- | ----------------------------------------- |
| `pyocd`   | Default, versatile, supports many debuggers  | [pyocd](https://github.com/pyocd/pyOCD)   |
| `pyswd`   | Lightweight and fast, **ST-Link only**       | [pyswd](https://github.com/cortexm/pyswd) |
| `openocd` | Requires a pre-started OpenOCD daemon (TCP)  | [openocd](https://openocd.org/)           |
| `mock`    | In-memory simulation for development/testing | _(built-in)_                              |

## Example Configs

The `examples/` directory provides config templates for various scenarios:

| File           | Description                                                               |
| -------------- | ------------------------------------------------------------------------- |
| [`simple.toml`](examples/simple.toml)  | Minimal config, quick start                                               |
| [`full.toml`](examples/full.toml)      | Comprehensive example covering scalar / array / struct / computed / write |
| [`symbol.toml`](examples/symbol.toml)  | ELF symbol resolution — use variable names instead of raw addresses       |
| [`plot.toml`](examples/plot.toml)      | Plotting config (multi-figure / multi-layout / plot / stem / scatter)     |
| [`pyocd.toml`](examples/pyocd.toml)    | pyOCD backend connecting to a specific target chip                        |
| [`pyswd.toml`](examples/pyswd.toml)    | pySWD backend (ST-Link)                                                   |
| [`openocd.toml`](examples/openocd.toml)| OpenOCD backend, requires manually starting the daemon                    |

For a full reference of all config options, see [`docs/config-reference.toml`](docs/config-reference.toml).
