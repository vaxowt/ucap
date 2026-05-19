from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ucap.config import Config, SaveConfig, Var


@pytest.fixture
def sample_var() -> Var:
    return Var(name='test', address=0x1000, format='<I')


@pytest.fixture
def sample_computed_var() -> Var:
    return Var(name='computed', expr='x * 2')


@pytest.fixture
def sample_dict_var() -> Var:
    return Var(name='dict_var', address=0x2000, format='<II',
              struct=['a', 'b'])


@pytest.fixture
def sample_write_var() -> Var:
    return Var(name='write_var', address=0x3000, format='<I', value=42)


@pytest.fixture
def sample_vars() -> list[Var]:
    return [
        Var(name='a', address=0x1000, format='<I'),
        Var(name='b', address=0x1004, format='<I'),
    ]


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    with TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def save_cfg(tmp_path: Path) -> SaveConfig:
    return SaveConfig(dir=str(tmp_path), auto_name=False, name='test_save')
