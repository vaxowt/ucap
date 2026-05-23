# uCap

> A non-invasive DAP-based tool for MCU data acquisition, monitoring, and visualization.

[中文文档](docs/README.zh.md)

<p align="center">
  <video src="https://github.com/user-attachments/assets/5b1926d9-4c7e-4628-97e3-223b6fda863d" controls width="500px"></video>
</p>

## Features

- **Non-invasive** — reads/writes MCU memory via DAP (SWD/JTAG); no code changes or debug printf required
- **Dual modes** — headless CLI (`ucap rw`) for fast batch acquisition, or GUI monitor (`ucap mon`) for live visualization
- **Multiple backends** — pyOCD, pySWD, OpenOCD; works with ST-Link, J-Link, DAP-Link, and more
- **On-the-fly expressions** — transform raw register values with math expressions (scaling, unit conversion, sensor formulas)
- **Struct-aware** — unpack packed C structs into named fields automatically
- **ELF symbol resolution** — use variable names from your firmware instead of raw addresses
- **Rich plotting** — multi-figure / multi-axis layouts with line, stem, and scatter plot types
- **Save & replay** — captured data is saved and can be re-plotted offline

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

## Variables

A `[[vars]]` entry describes a variable in the target MCU's memory space that ucap will read and/or write:

| Field       | Description                                                         |
| ----------- | ------------------------------------------------------------------- |
| `name`      | Identifier used in saved data and plots                             |
| `address`   | Memory address (hex) or symbol name resolved via `--elf`            |
| `format`    | [struct format string](https://docs.python.org/3/library/struct.html#format-strings) for packing/unpacking bytes |
| `value`     | If set, the variable is **write-only** (written every cycle); omit for read |
| `struct`    | List of field names to unpack multi-field data into a dict          |
| `expr`      | Expression to transform the read value (e.g. `'x * 3.3 / 4096'`); can reference other vars |
| `plot`      | Axis assignment and plot type (line / stem / scatter)               |

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

**Expression**: Apply scaling or computation on the fly:

```toml
[[vars]]
name = 'temperature'
address = 0x4001204C
format = '<H'
expr = '(x * 3.3 / 4096 - 0.76) / 0.0025 + 25'
```

See [`docs/config-reference.toml`](docs/config-reference.toml) for the full variable specification.

```bash
pip install python-ucap
```

If using ST-Link V3, you need to install the [latest pyswd](https://github.com/cortexm/pyswd):

```bash
git clone https://github.com/cortexm/pyswd
cd pyswd
pip install .
```

## Usage

### `ucap rw` — Continuous Read/Write

Continuously reads/writes target variables at the configured frequency. No GUI overhead — the fastest mode. Press **Ctrl+C** to stop; then saves data and plots with matplotlib.

```bash
ucap rw -c path/to/config.toml
```

Optionally resolve addresses from an ELF file with `--elf`:

```bash
ucap rw -c path/to/config.toml --elf path/to/firmware.elf
```

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

| Backend   | Description                          | Dependency                                 |
| --------- | ------------------------------------ | ------------------------------------------ |
| `pyocd`   | Default, versatile, supports many debuggers | [pyocd](https://github.com/pyocd/pyOCD)  |
| `pyswd`   | Lightweight and fast, **ST-Link only** | [pyswd](https://github.com/cortexm/pyswd) |
| `openocd` | Requires a pre-started OpenOCD daemon | [openocd](https://openocd.org/)            |

## Example Configs

The `examples/` directory provides config templates for various scenarios:

| File              | Description                                                               |
| ----------------- | ------------------------------------------------------------------------- |
| `simple.toml`     | Minimal config, quick start                                               |
| `full.toml`       | Comprehensive example covering scalar / array / struct / computed / write |
| `plot.toml`       | Plotting config (multi-figure / multi-layout / plot / stem / scatter)     |
| `pyocd.toml`      | pyOCD backend connecting to a specific target chip                        |
| `pyswd.toml`      | pySWD backend (ST-Link)                                                   |
| `openocd.toml`    | OpenOCD backend, requires manually starting the daemon                    |

For a full reference of all config options, see [`docs/config-reference.toml`](docs/config-reference.toml).
