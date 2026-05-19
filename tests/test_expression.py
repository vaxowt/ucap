import numpy as np
import pytest

from ucap.config import AttrDict, Var
from ucap.expression import (_apply_var_expr, apply_expr, eval_expr)


class TestEvalExpr:

    def test_basic_arithmetic(self):
        assert eval_expr('x + 1', {'x': 5}) == 6

    def test_multi_var(self):
        assert eval_expr('a + b', {'a': 3, 'b': 4}) == 7

    def test_numpy_math(self):
        result = eval_expr('sqrt(x)', {'x': 9})
        assert result == 3.0

    def test_trig(self):
        result = eval_expr('sin(PI / 2)', {})
        assert abs(result - 1.0) < 1e-10

    def test_constants(self):
        assert abs(eval_expr('PI', {}) - np.pi) < 1e-10
        assert abs(eval_expr('E', {}) - np.e) < 1e-10

    def test_abs(self):
        assert eval_expr('abs(x)', {'x': -5}) == 5

    def test_unsafe_builtin_not_available(self):
        with pytest.raises(NameError):
            eval_expr('__import__("os")', {})


class TestApplyVarExprSingle:

    def test_no_expr(self, sample_var):
        result = _apply_var_expr(sample_var, 42, {})
        assert result == 42

    def test_scalar_expr(self, sample_computed_var):
        result = _apply_var_expr(sample_computed_var, 5, {'x': 5})
        assert result == 10

    def test_dict_expr(self):
        var = Var(name='d', address=0x1000, format='<II',
                  struct=['a', 'b'],
                  expr={'a': 'x * 2', 'b': 'x + 1'})
        raw = {'a': 5, 'b': 5}
        result = _apply_var_expr(var, raw, {})
        assert result['a'] == 10
        assert result['b'] == 6

    def test_dict_member_pass_through(self):
        var = Var(name='d', address=0x1000, format='<II',
                  struct=['a', 'b'],
                  expr={'a': 'x * 2'})
        raw = {'a': 5, 'b': 10}
        result = _apply_var_expr(var, raw, {})
        assert result['a'] == 10
        assert result['b'] == 10  # pass through unchanged

    def test_reference_other_var(self):
        var = Var(name='c', expr='a + b')
        result = _apply_var_expr(var, None, {'a': 3, 'b': 4})
        assert result == 7


class TestApplyVarExprBatch:

    def test_batch_scalar(self):
        var = Var(name='c', expr='x * 2')
        raw = [1, 2, 3]
        result = _apply_var_expr(var, raw, {}, batch=True)
        assert result == [2.0, 4.0, 6.0]

    def test_batch_dict(self):
        var = Var(name='d', address=0x1000, format='<II',
                  struct=['a', 'b'],
                  expr={'a': 'x * 2'})
        raw = {'a': [1, 2, 3], 'b': [4, 5, 6]}
        result = _apply_var_expr(var, raw, {}, batch=True)
        assert result['a'] == [2.0, 4.0, 6.0]
        assert result['b'] == [4, 5, 6]


class TestApplyExpr:

    def test_no_expr_vars(self, sample_vars):
        data = {'a': 1, 'b': 2}
        result = apply_expr(sample_vars, data)
        assert result == data

    def test_simple_transform(self):
        vars = [
            Var(name='a', address=0x1000, format='<I'),
            Var(name='b', expr='a * 2'),
        ]
        data = {'a': 5}
        result = apply_expr(vars, data)
        assert result['b'] == 10

    def test_chained_transform(self):
        vars = [
            Var(name='a', address=0x1000, format='<I'),
            Var(name='b', expr='a * 2'),
            Var(name='c', expr='b + 1'),
        ]
        data = {'a': 5}
        result = apply_expr(vars, data)
        assert result['b'] == 10
        assert result['c'] == 11

    def test_circular_dependency_raises(self):
        vars = [
            Var(name='a', expr='b + 1'),
            Var(name='b', expr='a + 1'),
        ]
        data = {}
        with pytest.raises(ValueError, match='Circular'):
            apply_expr(vars, data)

    def test_batch_mode(self):
        vars = [
            Var(name='a', address=0x1000, format='<I'),
            Var(name='b', expr='a * 2'),
        ]
        data = {'a': [1, 2, 3]}
        result = apply_expr(vars, data, batch=True)
        assert result['b'] == [2.0, 4.0, 6.0]
