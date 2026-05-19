import pytest

from ucap.config import Var
from ucap.monitor.model import (MonitorModel, build_mon_channels,
                                  channels_to_var_data, interpolate_at,
                                  snap_at)


class TestBuildMonChannels:

    def test_single_var(self):
        vars = [Var(name='x', address=0x1000, format='<I')]
        channels = build_mon_channels(vars)
        assert channels == ['x']

    def test_dict_var_with_struct(self):
        vars = [
            Var(name='pt', address=0x1000, format='<II', struct=['a', 'b'])
        ]
        channels = build_mon_channels(vars)
        assert channels == ['pt.a', 'pt.b']

    def test_dict_var_with_struct_skips_private(self):
        vars = [
            Var(name='pt', address=0x1000, format='<II',
                struct=['a', '_pad'])
        ]
        channels = build_mon_channels(vars)
        assert channels == ['pt.a']

    def test_write_var_excluded(self):
        vars = [Var(name='w', address=0x1000, format='<I', value=42)]
        channels = build_mon_channels(vars)
        assert channels == []

    def test_mixed(self):
        vars = [
            Var(name='x', address=0x1000, format='<I'),
            Var(name='w', address=0x2000, format='<I', value=1),
        ]
        channels = build_mon_channels(vars)
        assert channels == ['x']


class TestChannelsToVarData:

    def test_single_var(self):
        vars = [Var(name='x', address=0x1000, format='<I')]
        times = [0.0, 1.0]
        ch_data = {'x': [10, 20]}
        result = channels_to_var_data(vars, times, ch_data)
        assert result == {'x': [10, 20]}

    def test_dict_var(self):
        vars = [
            Var(name='pt', address=0x1000, format='<II', struct=['a', 'b'])
        ]
        times = [0.0, 1.0]
        ch_data = {'pt.a': [10, 20], 'pt.b': [30, 40]}
        result = channels_to_var_data(vars, times, ch_data)
        assert result == {'pt': {'a': [10, 20], 'b': [30, 40]}}

    def test_write_var_skipped(self):
        vars = [
            Var(name='x', address=0x1000, format='<I'),
            Var(name='w', address=0x2000, format='<I', value=42),
        ]
        times = [0.0]
        ch_data = {'x': [10]}
        result = channels_to_var_data(vars, times, ch_data)
        assert 'w' not in result


class TestInterpolateAt:

    def test_empty_returns_none(self):
        assert interpolate_at([], [], 0.0) is None

    def test_single_point(self):
        assert interpolate_at([1.0], [5.0], 2.0) == 5.0

    def test_exact_match(self):
        assert interpolate_at([0.0, 1.0, 2.0], [0, 10, 20], 1.0) == 10.0

    def test_linear_interpolation(self):
        result = interpolate_at([0.0, 2.0], [0, 20], 1.0)
        assert result == 10.0

    def test_before_first(self):
        assert interpolate_at([1.0, 2.0], [10, 20], 0.0) == 10.0

    def test_after_last(self):
        assert interpolate_at([1.0, 2.0], [10, 20], 3.0) == 20.0


class TestSnapAt:

    def test_empty(self):
        idx, t = snap_at([], 0.0)
        assert idx == 0
        assert t == 0.0

    def test_exact_match(self):
        idx, t = snap_at([0.0, 1.0, 2.0], 1.0)
        assert idx == 1
        assert t == 1.0

    def test_nearest_left(self):
        idx, t = snap_at([0.0, 2.0], 0.5)
        assert idx == 0
        assert t == 0.0

    def test_nearest_right(self):
        idx, t = snap_at([0.0, 2.0], 1.5)
        assert idx == 1
        assert t == 2.0

    def test_before_first(self):
        idx, t = snap_at([1.0, 2.0], 0.0)
        assert idx == 0
        assert t == 1.0

    def test_after_last(self):
        idx, t = snap_at([1.0, 2.0], 5.0)
        assert idx == 1
        assert t == 2.0

    def test_tie_goes_right(self):
        idx, t = snap_at([0.0, 2.0], 1.0)
        assert idx == 1
        assert t == 2.0


class TestMonitorModel:

    def test_empty_on_init(self):
        model = MonitorModel(['a', 'b'])
        assert model.is_empty
        assert model.size == 0
        assert model.time_start == 0.0
        assert model.time_end == 0.0

    def test_append(self):
        model = MonitorModel(['a', 'b'])
        model.append(1.0, {'a': 10, 'b': 20})
        assert not model.is_empty
        assert model.size == 1
        assert model.time_start == 1.0
        assert model.time_end == 1.0

    def test_multiple_append(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(1.0, {'a': 10})
        model.append(2.0, {'a': 20})
        assert model.size == 3
        assert model.time_start == 0.0
        assert model.time_end == 2.0

    def test_clear(self):
        model = MonitorModel(['a'])
        model.append(1.0, {'a': 10})
        model.clear()
        assert model.is_empty
        assert model.size == 0

    def test_time_to_index(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(1.0, {'a': 10})
        model.append(2.0, {'a': 20})
        assert model.time_to_index(0.5) == 1
        assert model.time_to_index(1.5) == 2
        assert model.time_to_index(3.0) == 3

    def test_get_times(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(1.0, {'a': 10})
        model.append(2.0, {'a': 20})
        assert model.get_times(0, 2) == [0.0, 1.0]

    def test_get_data(self):
        model = MonitorModel(['a', 'b'])
        model.append(0.0, {'a': 0, 'b': 100})
        model.append(1.0, {'a': 10, 'b': 200})
        assert model.get_data('a', 0, 2) == [0, 10]
        assert model.get_data('b', 1, 2) == [200]

    def test_channel_size(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(1.0, {'a': 10})
        assert model.channel_size('a') == 2
        assert model.channel_size('nonexistent') == 0

    def test_memory_estimate(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(1.0, {'a': 10})
        # 2 times * 8 + 2 values * 8 = 32
        assert model.memory_estimate() == 32

    def test_read_frequency(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(1.0, {'a': 10})
        model.append(2.0, {'a': 20})
        # 2 samples / 2 second span = 1.0 Hz
        assert model.read_frequency() == 1.0

    def test_read_frequency_insufficient_data(self):
        model = MonitorModel(['a'])
        assert model.read_frequency() == 0.0
        model.append(0.0, {'a': 0})
        assert model.read_frequency() == 0.0

    def test_elapsed(self):
        model = MonitorModel(['a'])
        model.append(0.0, {'a': 0})
        model.append(2.0, {'a': 10})
        assert model.elapsed() == 2.0

    def test_elapsed_insufficient_data(self):
        model = MonitorModel(['a'])
        assert model.elapsed() == 0.0
        model.append(0.0, {'a': 0})
        assert model.elapsed() == 0.0
