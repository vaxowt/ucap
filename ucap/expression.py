"""Expression evaluation for variable data transformation."""

import numpy as np

from ucap.config import AttrDict, Var

_SAFE_BUILTINS = {}

# Numpy math functions that work on both scalars and arrays.
# Exposed directly so that expr like 'sqrt(x)' works in batch mode.
_NUMPY_MATH_FUNCS = {
    'sqrt': np.sqrt,
    'cbrt': np.cbrt,
    'sin': np.sin,
    'cos': np.cos,
    'tan': np.tan,
    'arcsin': np.arcsin,
    'arccos': np.arccos,
    'arctan': np.arctan,
    'arctan2': np.arctan2,
    'hypot': np.hypot,
    'pow': np.pow,
    'exp': np.exp,
    'exp2': np.exp2,
    'log': np.log,
    'log2': np.log2,
    'log10': np.log10,
    'log1p': np.log1p,
    'abs': np.abs,
    'floor': np.floor,
    'ceil': np.ceil,
    'round': np.round,
    'sign': np.sign,
    'min': np.min,
    'max': np.max,
    'int': np.int64,
    'float': np.float64,
    'PI': np.pi,
    'E': np.e,
}


def eval_expr(expr: str, namespace: dict):
    """Safely evaluate a Python expression with numpy math access.

    Only numpy-compatible functions are available so that both
    single-shot (scalar) and batch (array) modes work correctly.

    Security: eval is restricted to a safe subset of builtins and numpy
    math functions. This mitigates arbitrary code execution from config
    files, but the config file itself is already trusted input.
    """
    ns = {'__builtins__': _SAFE_BUILTINS, **_NUMPY_MATH_FUNCS, **namespace}
    return eval(expr, ns)


def _wrap_single(value):
    """Wrap a single-shot var value for namespace use in expressions.

    Args:
        value: var value, can be int, dict, list, or None.
    """
    if isinstance(value, dict):
        return AttrDict({k: v[-1] if isinstance(v, list) else v
                         for k, v in value.items()})
    if isinstance(value, list):
        return value[-1] if value else None
    return value


def _wrap_batch(value):
    """Wrap a batch var value for namespace use in expressions.

    Converts to numpy arrays for vectorised evaluation.
    """
    if isinstance(value, dict):
        return AttrDict({k: np.array(v) for k, v in value.items()})
    return np.array(value) if value is not None else None


def _apply_var_expr(var: Var, raw_value, namespace: dict, batch: bool = False):
    """Apply expr to a var's value (single-shot or batch).

    Args:
        var: Var object with optional expr.
        raw_value: The var's raw/unpacked value, or None for computed vars.
        namespace: Dict of {name: wrapped_value} for referencing other vars.
        batch: If True, values are wrapped as numpy arrays and results
               are converted to plain lists via .tolist().

    Returns:
        The computed/transformed value.
    """
    if var.expr is None:
        return raw_value

    expr = var.expr
    wrap = _wrap_batch if batch else _wrap_single

    def _out(val):
        """Post-process eval output: convert ndarray→list in batch mode."""
        if batch and isinstance(val, np.ndarray):
            return val.tolist()
        return val

    if isinstance(expr, dict):
        # Per-member expr → result is always a dict
        # Members with a sub-expr are transformed; others pass through unchanged
        result = {}
        wrapped = wrap(raw_value) if raw_value is not None else AttrDict()
        # Determine all members (struct or list); pass through those not in expr
        if var.struct is not None:
            all_members = [m for m in var.struct if not m.startswith('_')]
        elif var.n_values > 1:
            all_members = [str(i) for i in range(var.n_values)]
        else:
            all_members = []
        # Pass through members not covered by expr
        for member in all_members:
            if member not in expr and member in wrapped:
                result[member] = _out(wrapped[member])
        # Apply expr to specified members
        for member, sub_expr in expr.items():
            ns = dict(namespace)
            if member in wrapped:
                ns['x'] = wrapped[member]
            result[member] = _out(eval_expr(sub_expr, ns))
        return result
    else:
        # Unified string expr
        if var.type is dict:
            # Struct/multi var → apply per member, return dict
            result = {}
            wrapped = wrap(raw_value) if raw_value is not None else AttrDict()
            if var.struct is not None:
                members = [m for m in var.struct if not m.startswith('_')]
            else:
                members = [str(i) for i in range(var.n_values)]
            for member in members:
                ns = dict(namespace)
                ns['x'] = wrapped[member]
                result[member] = _out(eval_expr(expr, ns))
            return result
        else:
            # Scalar
            ns = dict(namespace)
            ns['x'] = wrap(raw_value) if raw_value is not None else None
            return _out(eval_expr(expr, ns))


def apply_expr(vars: list[Var], data: dict, batch: bool = False) -> dict:
    """Apply expr transforms to var data (single-shot or batch).

    Modifies data in place and returns it.
    Handles read+transform vars and pure computed vars.
    Resolves dependencies via multi-pass resolution.
    """
    expr_vars = [r for r in vars if r.expr is not None and not r.is_write]
    if not expr_vars:
        return data

    wrap = _wrap_batch if batch else _wrap_single

    unresolved = list(expr_vars)
    for _ in range(len(expr_vars)):
        still_unresolved = []
        for var in unresolved:
            try:
                namespace = {name: wrap(val) for name, val in data.items()}
                raw_value = data.get(var.name)
                result = _apply_var_expr(var,
                                         raw_value,
                                         namespace,
                                         batch=batch)
                data[var.name] = result
            except (NameError, KeyError, AttributeError):
                still_unresolved.append(var)
        if not still_unresolved:
            break
        if len(still_unresolved) == len(unresolved):
            names = [v.name for v in still_unresolved]
            raise ValueError(
                f'Circular dependency or unresolved reference among vars: {names}'
            )
        unresolved = still_unresolved

    return data
