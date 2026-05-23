# Expressions

uCap expressions let you transform raw variable values on the fly using Python math syntax. Expressions are evaluated with NumPy functions and can reference other variables, making them suitable for scaling, unit conversion, sensor linearization, and computed signals.

## Expression Modes

### Uniform String Expression

A single expression applied to the whole variable. For scalar vars it transforms the single value; for multi-value or struct vars it applies the same transformation to every member.

```toml
[[vars]]
name = 'temperature'
address = 0x4001204C
format = '<H'
expr = '(x * 3.3 / 4096 - 0.76) / 0.0025 + 25'
```

In the expression, `x` represents the raw value read from the target.

### Per-member Dict Expression

Different expressions for different members of a struct or multi-value variable. Unspecified members pass through unchanged.

```toml
[[vars]]
name = 'accel'
address = 0x20000020
format = '<hhh'
struct = ['ax', 'ay', 'az']
expr = { ax = 'x * 9.81', ay = 'x * 9.81', az = 'x * 9.81 + 1' }
```

For multi-value vars without struct, use index strings as keys:

```toml
[[vars]]
name = 'gyro'
address = 0x20000030
format = '<hhh'
expr = { 0 = 'x * 0.01', 1 = 'x * 0.01' }
# Index 2 is kept as-is
```

### Computed-only Variables

A variable with only `expr` (no `address` or `format`) is derived entirely from other variables. Useful for creating combined signals without consuming memory bandwidth.

```toml
[[vars]]
name = 'power'
expr = 'voltage * current'
```

## Cross-variable References

Expressions can reference any other variable by name. The referenced variable must be defined earlier in the config or be resolvable through multi-pass dependency resolution.

```toml
[[vars]]
name = 'voltage'
address = 0x20000010
format = '<H'
expr = 'x * 3.3 / 4096'

[[vars]]
name = 'current'
address = 0x20000014
format = '<H'
expr = 'x * 0.01'

[[vars]]
name = 'power'
expr = 'voltage * current'
```

For multi-value and struct variables, individual members can be accessed by index or field name:

```toml
[[vars]]
name = 'accel_magnitude'
expr = 'sqrt(accel[0] ** 2 + accel[1] ** 2 + accel[2] ** 2)'
```

## Batch Evaluation

During continuous acquisition (`ucap rw`), expressions are evaluated in **batch mode** — the entire history of each variable is passed as a NumPy array. This is transparent to the user: the same expression syntax works for both single-shot (`ucap mon` per-cycle) and batch (`ucap rw`) evaluation.

## Circular Dependency Detection

If variable A depends on B and B depends on A (directly or indirectly), uCap will detect the circular dependency and raise an error:

```
Circular dependency or unresolved reference among vars: ['A', 'B']
```

## Supported Functions

All functions are NumPy implementations and work on both scalars (monitor mode) and arrays (batch mode).

### Arithmetic & Power

| Function   | Description                |
| ---------- | -------------------------- |
| `sqrt(x)`  | Square root                |
| `cbrt(x)`  | Cube root                  |
| `pow(x,y)` | x raised to power of y     |
| `hypot(x,y)` | Euclidean norm, sqrt(x²+y²) |
| `exp(x)`   | e^x                        |
| `exp2(x)`  | 2^x                        |
| `log(x)`   | Natural logarithm          |
| `log2(x)`  | Base-2 logarithm           |
| `log10(x)` | Base-10 logarithm          |
| `log1p(x)` | log(1+x), accurate for small x |

### Trigonometric

| Function         | Description            |
| ---------------- | ---------------------- |
| `sin(x)`         | Sine (radians)         |
| `cos(x)`         | Cosine (radians)       |
| `tan(x)`         | Tangent (radians)      |
| `arcsin(x)`      | Arc sine               |
| `arccos(x)`      | Arc cosine             |
| `arctan(x)`      | Arc tangent            |
| `arctan2(y, x)`  | Arc tangent of y/x     |

### Rounding & Sign

| Function   | Description            |
| ---------- | ---------------------- |
| `abs(x)`   | Absolute value         |
| `floor(x)` | Round down             |
| `ceil(x)`  | Round up               |
| `round(x)` | Round to nearest       |
| `sign(x)`  | Sign (-1, 0, 1)        |
| `int(x)`   | Convert to integer     |
| `float(x)` | Convert to float       |

### Statistics

| Function     | Description            |
| ------------ | ---------------------- |
| `min(a, b)`  | Minimum of two values  |
| `max(a, b)`  | Maximum of two values  |

### Constants

| Constant | Value            |
| -------- | ---------------- |
| `PI`     | π ≈ 3.1415926535 |
| `E`      | e ≈ 2.7182818284 |

## Examples

**Scaling and offset:**
```
expr = 'x * 3.3 / 4096'
```

**Sensor linearization (thermistor):**
```
expr = '(x * 3.3 / 4096 - 0.76) / 0.0025 + 25'
```

**Unit conversion:**
```
expr = 'x * 0.001'          # milli → base unit
expr = 'x * 9.81'           # G → m/s²
```

**Combined signal:**
```
expr = 'voltage * current'
expr = 'sqrt(x**2 + y**2 + z**2)'
```

**Conditional-like via sign:**
```
expr = 'x * (1 - sign(x-1000))'   # zero out values above 1000
```

## Security

Expression evaluation uses a restricted safe subset of Python builtins (`__builtins__` is empty) and only exposes the math functions listed above. Arbitrary code execution from config files is mitigated, though the config file itself is already a trusted input.
