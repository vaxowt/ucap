# uCap

> 基于 DAP (SWD/JTAG) 的非侵入式 MCU 数据采集、监测与可视化工具。

<p align="center">
  <video src="https://github.com/user-attachments/assets/5b1926d9-4c7e-4628-97e3-223b6fda863d" controls width="500px"></video>
</p>

## 特性

- **非侵入式** — 通过 DAP (SWD/JTAG) 读写 MCU 内存，无需修改固件代码或添加调试 printf
- **双模式** — 无头 CLI 模式 (`ucap rw`) 高速批量采集；GUI 实时监测模式 (`ucap mon`) 动态可视化
- **多后端支持** — pyOCD、pySWD、OpenOCD；兼容 ST-Link、DAP-Link 等调试器
- **即时表达式** — 对原始寄存器值进行数学变换（缩放、单位换算、公式）
- **结构体感知** — 自动将 C 结构体数据解包为命名字段
- **ELF 符号解析** — 使用固件变量名代替原始地址
- **丰富绘图** — 多图形 / 多坐标轴布局，支持 line、stem、scatter 三种图类型
- **保存与回放** — 采集的数据可保存，随时用 matplotlib 离线重绘

## 安装

```bash
pip install python-ucap
```

若使用 ST-Link V3 + pyswd 后端，需安装[最新版 pyswd](https://github.com/cortexm/pyswd)：

```bash
git clone https://github.com/cortexm/pyswd
cd pyswd
pip install .
```

## 快速开始

将 MCU 调试器（如 ST-Link、DAP-Link）连接到目标板，创建配置文件 `my_config.toml`。`target` 设为匹配的 MCU 型号（`pyocd list --targets` 查看支持的芯片；`cortex_m` 是通用后备）：

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

运行数据采集（按 Ctrl+C 停止）：

```bash
ucap rw -c my_config.toml
```

采集完成后将自动弹出 matplotlib 绘图窗口。

随时回放已保存的数据：

```bash
ucap show -d data/session1
```

参考 [`examples/simple.toml`](../examples/simple.toml) 获取最小配置示例，[`docs/config-reference.toml`](config-reference.toml) 查看全部配置选项，[`docs/data-format.md`](data-format.md) 了解数据文件结构。

## 核心概念

### 变量（Variables）

配置中的 `[[vars]]` 条目描述目标 MCU 内存空间中 ucap 将读取和/或写入的变量。`address` 字段可接受原始十六进制地址、外设寄存器名（如 `ADC1->DR`、`TIM2->CNT`）或 C 全局变量名——外设寄存器和全局变量符号均通过 `--elf` CLI 选项或 `elf_file` 配置项指定的 ELF 文件解析。

| 字段      | 说明                                                                                    |
| --------- | --------------------------------------------------------------------------------------- |
| `name`    | 用于保存数据和绘图的标识符                                                              |
| `address` | 十六进制地址、外设寄存器名或 C 全局变量名（通过 `--elf` / `elf_file` 解析）              |
| `format`  | [struct 格式字符串](https://docs.python.org/3/library/struct.html#format-strings)        |
| `value`   | 若设置，则为**只写**变量（每周期写入）；不设置则为只读                                  |
| `struct`  | 将多字段数据解包为字典的字段名列表                                                      |
| `expr`    | 变换读取值的表达式（如 `'x * 3.3 / 4096'`）；可引用其他变量                              |
| `plot`    | 坐标轴分配和绘图类型（line / stem / scatter）                                            |

**读取 vs 写入**：没有 `value` 时每周期读取该变量；有 `value` 时每周期写入该值。

**结构体解析**：当变量包含多个字段时（如 C 结构体或打包标志位），用 `struct` 拆分：

```toml
[[vars]]
name = 'status'
address = 0x20000040
format = '<BBH'
struct = ['flags', '_pad0', 'counter']
```

以 `_` 开头的字段将被丢弃。其余字段可分别绘图。

**表达式**：对读取值进行实时计算。支持的数学函数和用法详见 [`docs/expression.md`](expression.md)：

```toml
[[vars]]
name = 'temperature'
address = 0x4001204C
format = '<H'
expr = '(x * 3.3 / 4096 - 0.76) / 0.0025 + 25'
```

**用符号名代替原始地址**：在配置中设置 `elf_file`（或 CLI 传入 `--elf`）即可自动将 C 变量名解析为地址：

```toml
[[vars]]
name = 'adc_value'
address = 'ADC1->DR'      # 从 ELF/DWARF 解析
format = '<H'

[[vars]]
name = 'system_tick'
address = 'sys_tick_count'  # 任意全局变量
format = '<I'
```

无需查阅数据手册内存映射，固件变更后地址自动跟随代码。使用 `ucap sym -e firmware.elf` 浏览可用符号。

### 采集前 / 后变量

`[[pre_vars]]` 和 `[[post_vars]]` 是在连续采集循环之前（或之后）单次读取的变量组。适用于采集静态配置或校准值：

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

pre/post 数据保存在 `metadata.json` 的 `pre_data` 和 `post_data` 中。

## 使用方法

### `ucap rw` — 连续读写

无头批量采集模式。以配置频率连续读写目标变量，无 GUI 开销，速度最快。按 **Ctrl+C** 停止，然后保存数据并用 matplotlib 绘图。

```bash
ucap rw -c path/to/config.toml
```

可通过 `--elf` CLI 选项或 `elf_file` 配置项指定 ELF 文件，从而在 `address` 中使用 C 变量名：

```bash
ucap rw -c path/to/config.toml --elf path/to/firmware.elf
```

```toml
# config.toml
elf_file = 'path/to/firmware.elf'
```

配置文件更易读且更健壮——固件变更后地址自动跟随，无需对照链接脚本或数据手册。

### `ucap mon` — 实时监测

实时读写 + 动态绘图 GUI。

```bash
ucap mon -c path/to/config.toml
```

### `ucap show` — 回绘已保存数据

用 matplotlib 重新绘制之前由 `ucap rw` 或 `ucap mon` 采集的数据。如果数据目录中包含配置文件则会自动加载。

```bash
ucap show -d path/to/data_dir
```

### `ucap sym` — 列出 ELF 符号

列出 ELF 文件中的所有全局变量（含类型、结构体成员）。编写配置时查找变量地址非常实用。

```bash
ucap sym -e path/to/firmware.elf
```

按正则表达式过滤：

```bash
ucap sym -e path/to/firmware.elf "TIM|ADC"
```

配合 fzf 交互过滤：

```bash
ucap sym -e path/to/firmware.elf | fzf
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

## 后端支持

| 后端       | 说明                                          | 依赖                                        |
| ---------- | --------------------------------------------- | ------------------------------------------- |
| `pyocd`    | 默认，通用性强，支持多种调试器                 | [pyocd](https://github.com/pyocd/pyOCD)     |
| `pyswd`    | 轻量快速，**仅支持 ST-Link**                  | [pyswd](https://github.com/cortexm/pyswd)   |
| `openocd`  | 需预先启动 OpenOCD 守护进程（TCP 连接）       | [openocd](https://openocd.org/)             |
| `mock`     | 内存仿真，开发测试用                           | _（内置）_                                   |

## 示例配置

`examples/` 目录提供了多种场景的配置模板：

| 配置文件              | 说明                                                                       |
| --------------------- | -------------------------------------------------------------------------- |
| [`simple.toml`](../examples/simple.toml)   | 最小配置，快速上手                                                         |
| [`full.toml`](../examples/full.toml)       | 综合示例，涵盖 scalar / array / struct / computed / write 各类变量         |
| [`symbol.toml`](../examples/symbol.toml)   | ELF 符号解析——用变量名代替原始地址                                          |
| [`plot.toml`](../examples/plot.toml)       | 绘图配置专题（多 figure / 多 layout / plot / stem / scatter）              |
| [`pyocd.toml`](../examples/pyocd.toml)     | pyOCD 后端连接指定目标芯片                                                 |
| [`pyswd.toml`](../examples/pyswd.toml)     | pySWD 后端（ST-Link）                                                      |
| [`openocd.toml`](../examples/openocd.toml) | OpenOCD 后端，需手动启动守护进程                                           |

完整配置选项请参见 [`docs/config-reference.toml`](config-reference.toml)。
