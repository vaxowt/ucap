import pytest

from ucap.config import AttrDict, Config, Var, load_config, unpack_var_struct


class TestVarValidation:

    def test_minimal_var(self):
        v = Var(name='x', address=0x1000, format='<I')
        assert v.name == 'x'
        assert v.address == 0x1000
        assert v.format == '<I'

    def test_computed_var(self):
        v = Var(name='c', expr='a + b')
        assert v.is_computed
        assert v.address is None

    def test_write_var(self):
        v = Var(name='w', address=0x1000, format='<I', value=42)
        assert v.is_write
        assert v.value == 42

    def test_var_no_address_no_expr_raises(self):
        with pytest.raises(ValueError, match='address.*required'):
            Var(name='x')

    def test_var_no_format_no_expr_raises(self):
        with pytest.raises(ValueError, match='format.*required'):
            Var(name='x', address=0x1000)

    def test_var_expr_with_value_raises(self):
        with pytest.raises(ValueError, match='expr.*cannot be used with.*value'):
            Var(name='x', expr='y+1', value=42)

    def test_var_computed_dict_expr_raises(self):
        with pytest.raises(ValueError, match='pure computed.*string expr'):
            Var(name='x', expr={'a': 'y+1'})

    def test_var_address_with_computed_no_format_warns(self):
        with pytest.raises(ValueError, match='computed.*should not have.*address'):
            Var(name='x', address=0x1000, expr='y+1')


class TestVarProperties:

    def test_is_computed(self, sample_computed_var):
        assert sample_computed_var.is_computed

    def test_is_not_computed(self, sample_var):
        assert not sample_var.is_computed

    def test_is_write(self, sample_write_var):
        assert sample_write_var.is_write

    def test_is_not_write(self, sample_var):
        assert not sample_var.is_write

    def test_byte_order_with_prefix(self):
        v = Var(name='x', address=0x1000, format='<I')
        assert v.byte_order == '<'

    def test_byte_order_without_prefix(self):
        v = Var(name='x', address=0x1000, format='I')
        assert v.byte_order is None

    def test_n_bytes_single(self):
        v = Var(name='x', address=0x1000, format='<I')
        assert v.n_bytes == 4

    def test_n_bytes_multi(self):
        v = Var(name='x', address=0x1000, format='<II')
        assert v.n_bytes == 8

    def test_n_values_single(self):
        v = Var(name='x', address=0x1000, format='<I')
        assert v.n_values == 1

    def test_n_values_multi(self):
        v = Var(name='x', address=0x1000, format='<II')
        assert v.n_values == 2

    def test_type_value(self):
        v = Var(name='x', address=0x1000, format='<I')
        assert v.type == 'value'

    def test_type_dict_via_struct(self, sample_dict_var):
        assert sample_dict_var.type is dict

    def test_type_dict_via_n_values(self):
        v = Var(name='x', address=0x1000, format='<II')
        assert v.type is dict

    def test_type_dict_via_dict_expr(self):
        v = Var(name='x', expr={'a': 'y+1', 'b': 'y+2'},
                format='<II', address=0x1000)
        assert v.type is dict


class TestVarUnpack:

    def test_unpack_single(self, sample_var):
        raw = b'\x2a\x00\x00\x00'
        val = sample_var.unpack(raw)
        assert val == 42

    def test_unpack_multi(self):
        v = Var(name='x', address=0x1000, format='<II', struct=['a', 'b'])
        raw = b'\x2a\x00\x00\x00\x15\x00\x00\x00'
        val = v.unpack(raw)
        assert val == {'a': 42, 'b': 21}

    def test_unpack_from_list(self, sample_var):
        raw = [0x2a, 0x00, 0x00, 0x00]
        val = sample_var.unpack(raw)
        assert val == 42


class TestAttrDict:

    def test_attribute_access(self):
        d = AttrDict({'a': 1, 'b': 2})
        assert d.a == 1
        assert d.b == 2

    def test_dict_access(self):
        d = AttrDict({'a': 1})
        assert d['a'] == 1

    def test_int_key_mapping(self):
        d = AttrDict({'0': 10, '1': 20})
        assert d[0] == 10
        assert d[1] == 20

    def test_missing_attr_raises(self):
        d = AttrDict({'a': 1})
        with pytest.raises(AttributeError):
            _ = d.b

    def test_repr(self):
        d = AttrDict({'a': 1})
        assert 'AttrDict' in repr(d)


class TestUnpackVarStruct:

    def test_basic(self):
        struct = ['a', 'b', '_pad']
        values = [10, 20, 30]
        result = unpack_var_struct(struct, values)
        assert result == {'a': 10, 'b': 20}

    def test_empty(self):
        assert unpack_var_struct([], []) == {}


class TestConfigValidation:

    def test_minimal_config(self):
        cfg = Config(vars=[Var(name='x', address=0x1000, format='<I')])
        assert len(cfg.vars) == 1

    def test_duplicate_var_names_raises(self):
        with pytest.raises(ValueError, match='Duplicate'):
            Config(vars=[
                Var(name='x', address=0x1000, format='<I'),
                Var(name='x', address=0x1004, format='<I'),
            ])

    def test_duplicate_in_pre_vars_raises(self):
        with pytest.raises(ValueError, match='Duplicate.*pre_vars'):
            Config(
                pre_vars=[
                    Var(name='x', address=0x1000, format='<I'),
                    Var(name='x', address=0x1004, format='<I'),
                ],
                vars=[Var(name='y', address=0x2000, format='<I')],
            )

    def test_default_values(self):
        cfg = Config(vars=[Var(name='x', address=0x1000, format='<I')])
        assert cfg.log_level.value == 'info'
        assert cfg.rw_freq is None
        assert cfg.pre_delay == 0.0


class TestLoadConfig:

    def test_multi_line_inline_table(self, tmp_path):
        toml_content = """
vars = [
    { name = "temp", address = 0x1000, format = "<I" },
    { name = "humidity", address = 0x1004, format = "<I" },
]
mon = {
    view_window = 5.0,
    refresh_interval = 50,
}
"""
        p = tmp_path / 'config.toml'
        p.write_text(toml_content)
        cfg = load_config(p)
        assert len(cfg.vars) == 2
        assert cfg.vars[0].name == 'temp'
        assert cfg.mon.view_window == 5.0
        assert cfg.mon.refresh_interval == 50

    def test_multi_line_inline_table_nested(self, tmp_path):
        toml_content = """
vars = [
    { name = "x", address = 0x1000, format = "<I" },
]
plot = {
    show = false,
    figures = [
        { name = "main", axes = [["x"]], },
    ],
}
"""
        p = tmp_path / 'config.toml'
        p.write_text(toml_content)
        cfg = load_config(p)
        assert cfg.plot.show is False
        assert cfg.plot.figures[0].name == 'main'
        assert cfg.plot.figures[0].axes == [['x']]

    def test_multi_line_inline_table_trailing_comma(self, tmp_path):
        toml_content = """
vars = [
    { name = "a", address = 0x1000, format = "<I", },
    { name = "b", address = 0x1004, format = "<H", },
]
mon = {
    view_window = 10.0,
    theme = "dark",
    probe_interpolation = true,
}
"""
        p = tmp_path / 'config.toml'
        p.write_text(toml_content)
        cfg = load_config(p)
        assert len(cfg.vars) == 2
        assert cfg.mon.theme == 'dark'
        assert cfg.mon.probe_interpolation is True

    def test_multi_line_inline_list_vars(self, tmp_path):
        toml_content = """
vars = [
    { name = "a", address = 0x1000, format = "<I" },
    { name = "b", address = 0x1004, format = "<I" },
    { name = "c", address = 0x1008, format = "<I" },
    { name = "d", address = 0x100C, format = "<I" },
]
"""
        p = tmp_path / 'config.toml'
        p.write_text(toml_content)
        cfg = load_config(p)
        assert len(cfg.vars) == 4

    def test_multi_line_mixed_with_standard_tables(self, tmp_path):
        toml_content = r"""
log_level = "debug"
vars = [
    { name = "x", address = 0x1000, format = "<I" },
    { name = "y", address = 0x1004, format = "<I" },
]
mon = {
    view_window = 2.0,
    refresh_interval = 100,
    status_interval = 500,
}

[backend]
name = "mock"
freq = 1000000
"""
        p = tmp_path / 'config.toml'
        p.write_text(toml_content)
        cfg = load_config(p)
        assert cfg.log_level.value == 'debug'
        assert cfg.backend.name.value == 'mock'
        assert cfg.backend.freq == 1000000
        assert len(cfg.vars) == 2
        assert cfg.mon.view_window == 2.0
        assert cfg.mon.refresh_interval == 100
