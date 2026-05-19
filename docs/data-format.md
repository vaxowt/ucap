## 采集数据文件结构

* `config.save.dir/config.save.name/`
  * `metadata.json`: 元数据，json 格式
  * `data.pkl`: 数据，pickle 格式
  * `config.toml` (optional): 配置，toml 格式
  * `figure_name.png` (optional, multiple): 图片，png 格式

## 数据内容格式

### metadata

```python
{
    'timestamp_pre': float,
    'timestamp': float,
    'timestamp_post': float,
    'elapsed_time': float,
    'count': len(data['times']),
    'actual_rw_freq': float,
    'pre_data': VarData,
    'post_data': VarData,
    'extra': config.extra.metadata
}
```

### data

```python
{
    'times': [t1, t2, ..., tn],
    'data': VarData,
    'extra': config.extra.data,
}
```

### 数据结构定义

```python
VarData = {
    'var_single_value': [v1, v2, ..., vn],
    # 多值 var（有 struct 或无 struct），统一为 dict 格式
    'var_multi_value': {
        'field_or_index_0': [v1, v2, ..., vn],   # struct 成员名或索引字符串
        'field_or_index_1': [v1, v2, ..., vn],
    },
    # 带有 expr 的 var，数据格式取决于 var.type:
    # - 标量 expr: 与 single_value 相同
    # - dict expr 或 struct+expr 或 multi+expr: 与 var_multi_value 相同
    ...
}
```

