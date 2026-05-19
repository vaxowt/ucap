# uCap

> A non-invasive DAP-based tool for MCU data acquisition, monitoring, and visualization.

[中文文档](docs/README.zh.md)

<p align="center">
  <video src="https://github.com/user-attachments/assets/5b1926d9-4c7e-4628-97e3-223b6fda863d" controls width="500px"></video>
</p>

## Installation

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

### Read/Write Variables

Fill in a config file and run:

```bash
ucap rw -c path/to/config.toml
```

### Real-time Monitor

```bash
ucap mon -c path/to/config.toml
```

### Plot Captured Data

```bash
ucap show -d path/to/data_dir
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
