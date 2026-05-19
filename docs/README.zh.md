# uCap

> A non-invasive DAP-based tool for MCU data acquisition, monitoring, and visualization.

<p align="center">
  <video src="https://github.com/user-attachments/assets/5b1926d9-4c7e-4628-97e3-223b6fda863d" controls width="500px"></video>
</p>

## Installation

```bash
pip install python-ucap
```

若使用 ST-Link V3，需要安装[最新版的 pyswd](https://github.com/cortexm/pyswd)

```bash
git clone https://github.com/cortexm/pyswd
cd pyswd
pip install .
```

## Usage

### 读写全局变量/寄存器

填写配置文件，运行

```bash
ucap rw -c path/to/config.toml
```

### 实时监测

```bash
ucap mon -c path/to/config.toml
```

### 为已采集的数据绘图

```bash
ucap show -d path/to/data_dir
```

## Shell 补全

支持 bash / zsh / fish / powershell 的 Tab 补全：

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

将 eval 行添加到 `~/.bashrc`、`~/.zshrc`、fish 配置或 PowerShell `$PROFILE` 即可永久启用。

## Backend 支持

| Backend   | 说明                           | 依赖                                      |
| --------- | ------------------------------ | ----------------------------------------- |
| `pyocd`   | 默认，通用性强，支持多种调试器 | [pyocd](https://github.com/pyocd/pyOCD)   |
| `pyswd`   | 轻量快速，**仅支持 ST-Link**   | [pyswd](https://github.com/cortexm/pyswd) |
| `openocd` | 需预先启动 OpenOCD 守护进程    | [openocd](https://openocd.org/)           |

## 示例配置

`examples/` 目录提供了多种场景的配置模板：

| 配置文件       | 说明                                                                       |
| -------------- | -------------------------------------------------------------------------- |
| `simple.toml`  | 最小配置，快速上手                                                         |
| `full.toml`    | 全功能综合示例，涵盖 scalar / array / struct / computed / write 各类变量   |
| `plot.toml`    | 绘图配置专题（多 figure / 多 layout / plot / stem / scatter）              |
| `pyocd.toml`   | pyOCD 后端连接指定目标芯片                                                 |
| `pyswd.toml`   | pySWD 后端（ST-Link）                                                      |
| `openocd.toml` | OpenOCD 后端，需手动启动守护进程                                           |
