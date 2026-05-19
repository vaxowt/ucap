import json
import pickle
from pathlib import Path

import pytest

from ucap.config import Config, SaveConfig, Var
from ucap.export import build_save_data, resolve_save_path, save_data


class TestResolveSavePath:

    def test_disabled_returns_none(self):
        cfg = SaveConfig(enable=False)
        assert resolve_save_path(cfg) is None

    def test_auto_name_uses_timestamp(self, tmp_path):
        cfg = SaveConfig(dir=str(tmp_path), auto_name=True, name=None)
        path = resolve_save_path(cfg)
        assert path is not None
        assert path.parent == tmp_path

    def test_named_path(self, tmp_path):
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False, name='mysession')
        path = resolve_save_path(cfg)
        assert path is not None
        assert path.name == 'mysession'

    def test_override_suppresses_error(self, tmp_path):
        (tmp_path / 'existing').mkdir()
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False,
                         name='existing', override=True)
        path = resolve_save_path(cfg)
        assert path is not None
        assert path.name == 'existing'

    def test_non_empty_raises_without_handler(self, tmp_path):
        (tmp_path / 'existing').mkdir()
        (tmp_path / 'existing' / 'file.txt').write_text('x')
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False,
                         name='existing', override=False)
        with pytest.raises(FileExistsError):
            resolve_save_path(cfg)

    def test_conflict_handler_overwrite(self, tmp_path):
        (tmp_path / 'existing').mkdir()
        (tmp_path / 'existing' / 'file.txt').write_text('x')
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False,
                         name='existing', override=False)
        path = resolve_save_path(cfg, on_conflict=lambda p, d: 'overwrite')
        assert path is not None
        assert path.name == 'existing'

    def test_conflict_handler_cancel(self, tmp_path):
        (tmp_path / 'existing').mkdir()
        (tmp_path / 'existing' / 'file.txt').write_text('x')
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False,
                         name='existing', override=False)
        path = resolve_save_path(cfg, on_conflict=lambda p, d: None)
        assert path is None

    def test_conflict_handler_new_path(self, tmp_path):
        (tmp_path / 'existing').mkdir()
        (tmp_path / 'existing' / 'file.txt').write_text('x')
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False,
                         name='existing', override=False)
        new = tmp_path / 'newdir'
        path = resolve_save_path(cfg, on_conflict=lambda p, d: str(new))
        assert path == new

    def test_empty_dir_no_conflict(self, tmp_path):
        (tmp_path / 'empty').mkdir()
        cfg = SaveConfig(dir=str(tmp_path), auto_name=False,
                         name='empty', override=False)
        path = resolve_save_path(cfg)
        assert path is not None


class TestBuildSaveData:

    def test_basic_structure(self):
        cfg = Config(vars=[Var(name='x', address=0x1000, format='<I')])
        times = [0.0, 1.0, 2.0]
        vars_data = {'x': [10, 20, 30]}
        data, metadata = build_save_data(times, vars_data, cfg)
        assert data['times'] == times
        assert data['data'] == vars_data
        assert metadata['count'] == 3
        assert metadata['elapsed_time'] == 2.0
        assert abs(metadata['actual_rw_freq'] - 1.0) < 1e-6

    def test_single_sample(self):
        cfg = Config(vars=[Var(name='x', address=0x1000, format='<I')])
        times = [0.0]
        vars_data = {'x': [10]}
        data, metadata = build_save_data(times, vars_data, cfg)
        assert metadata['count'] == 1
        assert metadata['elapsed_time'] == 0.0
        assert metadata['actual_rw_freq'] == 0.0

    def test_extra_data_included(self):
        cfg = Config(vars=[Var(name='x', address=0x1000, format='<I')],
                     extra={'data': {'note': 'test'}})
        times = [0.0, 1.0]
        vars_data = {'x': [10, 20]}
        data, metadata = build_save_data(times, vars_data, cfg)
        assert data['extra'] == {'note': 'test'}
        assert metadata['extra'] == {}


class TestSaveData:

    def test_save_creates_files(self, tmp_path, save_cfg):
        save_path = tmp_path / 'session'
        data = {'times': [0.0, 1.0], 'data': {'x': [10, 20]}}
        metadata = {'count': 2}
        config_raw = b'[vars]\nname = "x"\n'
        save_data(save_cfg, save_path, config_raw, data, metadata, {})
        assert (save_path / 'data.pkl').exists()
        assert (save_path / 'metadata.json').exists()
        assert (save_path / 'config.toml').exists()

    def test_saved_data_is_readable(self, tmp_path, save_cfg):
        save_path = tmp_path / 'session'
        data = {'times': [0.0, 1.0], 'data': {'x': [10, 20]}}
        metadata = {'count': 2}
        save_data(save_cfg, save_path, b'', data, metadata, {})

        with open(save_path / 'data.pkl', 'rb') as f:
            loaded = pickle.load(f)
        assert loaded['times'] == [0.0, 1.0]

    def test_saved_metadata_is_json(self, tmp_path, save_cfg):
        save_cfg.save_config = False
        save_path = tmp_path / 'session'
        data = {'times': []}
        metadata = {'count': 0, 'note': 'test'}
        save_data(save_cfg, save_path, None, data, metadata, {})
        with open(save_path / 'metadata.json') as f:
            loaded = json.load(f)
        assert loaded['count'] == 0
        assert loaded['note'] == 'test'
