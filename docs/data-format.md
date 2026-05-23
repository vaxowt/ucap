## Captured Data File Structure

* `config.save.dir/config.save.name/`
  * `metadata.json`: Metadata, JSON format
  * `data.pkl`: Data, pickle format
  * `config.toml` (optional): Configuration, TOML format
  * `figure_name.png` (optional, multiple): Plot image, PNG format

## Data Content Format

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

### Data Structure Definition

```python
VarData = {
    'var_single_value': [v1, v2, ..., vn],
    # Multi-value var (with or without struct), normalized to dict format
    'var_multi_value': {
        'field_or_index_0': [v1, v2, ..., vn],   # struct member name or index string
        'field_or_index_1': [v1, v2, ..., vn],
    },
    # Var with expr, data format depends on var.type:
    # - Scalar expr: same as single_value
    # - dict expr or struct+expr or multi+expr: same as var_multi_value
    ...
}
```

