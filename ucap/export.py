"""Data save/load helpers."""

import json
import logging
import pathlib
import pickle
import time

from ucap.config import Config, SaveConfig
from ucap.constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def resolve_save_path(save_config: SaveConfig,
                       on_conflict=None) -> pathlib.Path | None:
    """Resolve save path with optional interactive conflict handler.

    on_conflict(save_path, save_dir) -> 'overwrite' | new_path | None
    """
    if not save_config.enable:
        return None
    save_dir = pathlib.Path(save_config.dir)
    save_name = str(time.time()) if save_config.auto_name else save_config.name
    if not save_name:
        save_name = str(time.time())
    save_path = save_dir / save_name
    if save_path.exists() and list(save_path.iterdir()):
        if not save_config.override:
            if on_conflict is None:
                raise FileExistsError(f'output dir is not empty: {save_path}')
            result = on_conflict(save_path, save_dir)
            if result is None:
                return None
            if result != 'overwrite':
                save_path = pathlib.Path(result)
    return save_path


def build_save_data(times: list[float], vars_data: dict, cfg: Config
                    ) -> tuple[dict, dict]:
    """Build data and metadata dicts in standard save format."""
    n = len(times)
    elapsed = times[-1] - times[0] if n >= 2 else 0.0
    actual_freq = (n - 1) / elapsed if elapsed > 0 else 0.0
    data = {
        'times': times,
        'data': vars_data,
        'extra': cfg.extra.data,
    }
    metadata = {
        'timestamp_pre': None,
        'timestamp': None,
        'timestamp_post': None,
        'elapsed_time': elapsed,
        'count': n,
        'actual_rw_freq': actual_freq,
        'pre_data': {},
        'post_data': {},
        'extra': cfg.extra.metadata,
    }
    return data, metadata


def save_data(save_config: SaveConfig, save_path: pathlib.Path | None, config,
              data, metadata, figures):
    if save_config.enable:
        assert save_path is not None
        save_path.mkdir(exist_ok=True, parents=True)
        data_path = save_path / f'{save_config.data_filename}.pkl'
        metadata_path = save_path / f'{save_config.metadata_filename}.json'
        with open(data_path, 'wb') as f:
            pickle.dump(data, f)
            logger.debug(f'data saved to: {data_path}')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=save_config.metadata_indent)
            logger.debug(f'metadata saved to: {metadata_path}')

        if save_config.save_config:
            config_path = save_path / f'{save_config.config_filename}.toml'
            with open(config_path, 'wb') as f:
                f.write(config)
            logger.debug(f'config saved to: {config_path}')

        if save_config.save_figure:
            for n, figure in figures.items():
                figure_path = save_path / f'{n}.png'
                figure.savefig(figure_path)
                logger.debug(f'figure saved to: {figure_path}')
        logger.info(f'saved to: {save_path}')
