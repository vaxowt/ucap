import pytest

from ucap.config import BackendConfig, Var
from ucap.probe.mock import MockProbe


@pytest.fixture
def mock_cfg() -> BackendConfig:
    return BackendConfig(mock={'sigma': 0.0})


@pytest.fixture
def mock_probe(mock_cfg) -> MockProbe:
    return MockProbe(mock_cfg)


class TestMockProbeBasic:

    def test_read_mem(self, mock_probe):
        data = mock_probe.read_mem(0x1000, 4)
        assert len(data) == 4
        assert all(b == 0 for b in data)

    def test_write_then_read(self, mock_probe):
        mock_probe.write_mem(0x1000, [0x2a, 0x00, 0x00, 0x00])
        data = mock_probe.read_mem(0x1000, 4)
        assert data == [0x2a, 0x00, 0x00, 0x00]

    def test_write_multi_byte(self, mock_probe):
        mock_probe.write_mem(0x1000, [1, 2, 3, 4, 5, 6, 7, 8])
        data = mock_probe.read_mem(0x1000, 8)
        assert data == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_overlapping_write(self, mock_probe):
        mock_probe.write_mem(0x1000, [1, 2, 3, 4])
        mock_probe.write_mem(0x1002, [0xff, 0xfe])
        data = mock_probe.read_mem(0x1000, 4)
        assert data == [1, 2, 0xff, 0xfe]

    def test_get_serial_no(self, mock_probe):
        assert mock_probe.get_serial_no() == 'MOCK-00000000'


class TestMockProbeWithMemory:

    def test_preset_memory(self):
        memory = {0x1000: [0x2a, 0x00, 0x00, 0x00]}
        cfg = BackendConfig(mock={'sigma': 0.0})
        probe = MockProbe(cfg, memory=memory)
        data = probe.read_mem(0x1000, 4)
        assert data == [0x2a, 0x00, 0x00, 0x00]

    def test_preset_then_extend(self):
        memory = {0x1000: [0x2a]}
        cfg = BackendConfig(mock={'sigma': 0.0})
        probe = MockProbe(cfg, memory=memory)
        data = probe.read_mem(0x1000, 2)
        assert data[0] == 0x2a
        assert data[1] == 0  # auto-initialized


class TestMockProbeGetFuncArgs:

    def test_read_var(self, mock_cfg):
        probe = MockProbe(mock_cfg)
        var = Var(name='x', address=0x1000, format='<I')
        func, args = probe.get_func_args(var)
        assert callable(func)
        data = func(*args)
        assert len(data) == 4

    def test_write_var(self, mock_cfg):
        probe = MockProbe(mock_cfg)
        var = Var(name='w', address=0x1000, format='<I', value=42)
        func, args = probe.get_func_args(var)
        assert callable(func)
        func(*args)
        data = probe.read_mem(0x1000, 4)
        # 42 in little-endian uint32
        assert data == [0x2a, 0x00, 0x00, 0x00]

    def test_custom_serial(self):
        cfg = BackendConfig(serial_no='CUSTOM-001')
        probe = MockProbe(cfg)
        assert probe.get_serial_no() == 'CUSTOM-001'
