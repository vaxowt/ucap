"""CLI entry point for ucap."""

import logging
import os
import pathlib
import pickle
import sys
import time

import click
from click.shell_completion import (
    CompletionItem,
    ShellComplete,
    add_completion_class,
    split_arg_string,
)
import matplotlib.pyplot as plt
import numpy as np

from ucap.config import Config, load_config
from ucap.constants import CLI_NAME, LOG_FORMAT, LOGGER_NAME
from ucap.elf import list_symbols, resolve_symbol_address
from ucap.plot import create_figures_axes, is_default_axis_needed, plot_data
from ucap.probe import (ProbeConnectionError, continuous_rw_vars,
                          create_probe, rw_vars, unpack_continuous_data)
from ucap.export import resolve_save_path, save_data

logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

def _config_opt(*, required=False):
    return click.option('-c', '--config',
                        type=click.Path(exists=True, dir_okay=False),
                        required=required, help='configuration path')


def _elf_opt(*, required=False):
    return click.option('-e', '--elf',
                        type=click.Path(exists=True, dir_okay=False),
                        required=required, help='ELF file path')


def _set_verbose(ctx, _, value):
    ctx.ensure_object(dict)
    if value:
        ctx.obj['verbose'] = True
        logger.setLevel(logging.DEBUG)


_verbose_callback_opt = click.option('-v',
                                     '--verbose',
                                     is_flag=True,
                                     expose_value=False,
                                     is_eager=True,
                                     callback=_set_verbose,
                                     help='verbose output')


class _OrderedGroup(click.Group):
    def list_commands(self, ctx):
        return list(self.commands)


_SOURCE_POWERSHELL = '''\
$scriptBlock = {
    param($wordToComplete, $commandAst, $cursorPosition)

    $wordCount = $commandAst.CommandElements.Count

    if (-not $wordToComplete) {
        $compWords = $commandAst.Extent.Text + " "
        $compCword = $wordCount
    } else {
        $compWords = $commandAst.Extent.Text
        $compCword = $wordCount - 1
    }

    $oldWords = $env:COMP_WORDS
    $oldCword = $env:COMP_CWORD
    $oldComplete = $env:%(complete_var)s
    try {
        $env:COMP_WORDS = $compWords
        $env:COMP_CWORD = $compCword
        $env:%(complete_var)s = "powershell_complete"
        $response = %(prog_name)s 2> $null
    } finally {
        $env:COMP_WORDS = $oldWords
        $env:COMP_CWORD = $oldCword
        $env:%(complete_var)s = $oldComplete
    }

    if ($response) {
        $response | ForEach-Object {
            $_ -split "`n" | ForEach-Object {
                if ($_) {
                    $parts = $_ -split ",", 2
                    if ($parts.Length -eq 2) {
                        $value = ($parts[1] -split "`t")[0]
                        [System.Management.Automation.CompletionResult]::new($value, $value, "ParameterValue", $value)
                    }
                }
            }
        }
    }
}

Register-ArgumentCompleter -Native -CommandName %(prog_name)s -ScriptBlock $scriptBlock
'''


class PowerShellComplete(ShellComplete):
    name = "powershell"
    source_template = _SOURCE_POWERSHELL

    def get_completion_args(self) -> tuple[list[str], str]:
        cwords = split_arg_string(os.environ["COMP_WORDS"])
        cword = int(os.environ["COMP_CWORD"])
        args = cwords[1:cword]
        try:
            incomplete = cwords[cword]
        except IndexError:
            incomplete = ""
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        if item.help:
            return f"{item.type},{item.value}\t{item.help}"
        return f"{item.type},{item.value}"


add_completion_class(PowerShellComplete)


@click.group(CLI_NAME, cls=_OrderedGroup, invoke_without_command=True)
@click.option('-l', '--list', is_flag=True, help='list probes')
@_verbose_callback_opt
@click.version_option(package_name="python-ucap")
@click.pass_context
def cli(ctx, list):
    if list:
        logger.setLevel(logging.DEBUG)
        from pyocd.core.helpers import ConnectHelper
        ConnectHelper.list_connected_probes()
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command('rw', help='read & write variables')
@_config_opt(required=True)
@_elf_opt()
@click.option('-o',
              '--output-dir',
              type=click.Path(exists=False, file_okay=False),
              help='output dir')
@click.option('-n', '--name', type=str, help='output name')
@click.option('-f',
              '--force',
              is_flag=True,
              help='force override output dir contents')
@_verbose_callback_opt
@click.pass_context
def subcmd_rw(ctx, config, output_dir, name, force, elf):

    cfg: Config = load_config(config)

    if not ctx.obj.get('verbose'):
        logger.setLevel(cfg.log_level.upper())

    logger.debug(f'read config from {config}')
    logger.debug(cfg)

    if not cfg.save.enable:
        logger.warning('data will not be saved')

    config_raw = None
    if cfg.save.enable and cfg.save.save_config:
        with open(config, 'rb') as f:
            config_raw = f.read()

    if output_dir is not None:
        cfg.save.dir = output_dir
    if name is not None:
        cfg.save.name = name
    if force is not None:
        cfg.save.override = force
    try:
        save_path = resolve_save_path(cfg.save)
    except FileExistsError as e:
        logger.error(str(e))
        sys.exit(1)

    if elf is not None:
        cfg.elf_file = elf

    # resolve symbol address
    resolve_symbol_address(cfg)

    try:
        dev = create_probe(cfg)
    except ProbeConnectionError as e:
        logger.error(e)
        sys.exit(1)

    timestamp_pre = time.time()
    if cfg.pre_vars:
        pre_data = rw_vars(dev, cfg.pre_vars)
    else:
        pre_data = {}
    logger.debug(pre_data)

    if cfg.pre_delay > 0:
        logger.info(f'pre_delay (s): {cfg.pre_delay}')
        time.sleep(cfg.pre_delay)

    timestamp = time.time()
    times, raw_data = continuous_rw_vars(dev, cfg.vars, freq=cfg.rw_freq)
    logger.debug(raw_data)

    if cfg.post_delay > 0:
        logger.info(f'post_delay (s): {cfg.post_delay}')
        time.sleep(cfg.post_delay)

    timestamp_post = time.time()
    if cfg.post_vars:
        post_data = rw_vars(dev, cfg.post_vars)
    else:
        post_data = {}
    logger.debug(post_data)

    dev.close()

    if len(times) >= 2:
        actual_rw_freq = 1 / np.mean(np.diff(times))
        logger.info(
            f'rw_freq (Hz): target={cfg.rw_freq} actual={round(actual_rw_freq, 2)}'
        )
        if cfg.rw_freq:
            rw_freq_error_percent = abs(actual_rw_freq - cfg.rw_freq) / cfg.rw_freq
            if rw_freq_error_percent > cfg.rw_freq_error_tolerance:
                logger.error(
                    f'the rw_freqs diff too much: {round(rw_freq_error_percent * 100, 4)}% (tolerance={cfg.rw_freq_error_tolerance * 100}%)'
                )
                sys.exit(1)
            elif rw_freq_error_percent > cfg.rw_freq_warning_tolerance:
                logger.warning(
                    f'the rw_freqs diff too much: {round(rw_freq_error_percent * 100, 4)}% (tolerance={cfg.rw_freq_warning_tolerance * 100}%)'
                )
    else:
        logger.warning('too few samples to compute rw_freq')

    elapsed_time = times[-1] - times[0]
    logger.info(f'stats: elapsed={round(elapsed_time, 2)}s count={len(times)}')

    times = (np.array(times) - times[0]).tolist()
    vars_data = unpack_continuous_data(cfg.vars, raw_data)
    logger.debug(vars_data)

    if cfg.plot.show or (cfg.save.enable and cfg.save.save_figure):
        keep_default_axis = is_default_axis_needed(cfg.vars)
        figures, axes = create_figures_axes(cfg.plot, keep_default_axis)
        plot_data(cfg.vars, axes, times, vars_data)
    else:
        figures = {}

    metadata = {
        'timestamp_pre': timestamp_pre,
        'timestamp': timestamp,
        'timestamp_post': timestamp_post,
        'elapsed_time': elapsed_time,
        'count': len(times),
        'actual_rw_freq': actual_rw_freq,
        'pre_data': pre_data,
        'post_data': post_data,
        'extra': cfg.extra.metadata
    }
    data = {
        'times': times,
        'data': vars_data,
        'extra': cfg.extra.data,
    }
    save_data(cfg.save, save_path, config_raw, data, metadata, figures)

    if cfg.plot.show:
        plt.show()


@cli.command('mon', help='monitor variables in real-time')
@_config_opt(required=True)
@_elf_opt()
@_verbose_callback_opt
@click.pass_context
def subcmd_mon(ctx, config, elf):
    from ucap.monitor import Monitor

    cfg: Config = load_config(config)

    if not ctx.obj.get('verbose'):
        logger.setLevel(cfg.log_level.upper())

    logger.debug(f'read config from {config}')
    logger.debug(cfg)

    if elf is not None:
        cfg.elf_file = elf

    # resolve symbol address
    resolve_symbol_address(cfg)

    monitor = Monitor(cfg, pathlib.Path(config))
    try:
        monitor.start()
    finally:
        monitor.stop()


@cli.command('show', help='show the recorded data')
@click.option('-d',
              '--data-dir',
              type=click.Path(exists=False, file_okay=False),
              required=True,
              help='data dir')
@_config_opt()
@_verbose_callback_opt
@click.pass_context
def subcmd_show(ctx, data_dir, config):
    data_dir = pathlib.Path(data_dir)
    if config is None:
        config = data_dir / 'config.toml'
    else:
        config = pathlib.Path(config)
    if not config.exists():
        logger.error(f'config file not found: {config}')
        sys.exit(1)

    logger.debug(f'read config from {config}')
    cfg: Config = load_config(config)
    if not ctx.obj.get('verbose'):
        logger.setLevel(cfg.log_level.upper())
    logger.debug(cfg)

    data_path = data_dir / f'{cfg.save.data_filename}.pkl'
    if not data_path.exists():
        logger.error(f'data file not found: {data_path}')
        sys.exit()

    with open(data_path, 'rb') as f:
        data = pickle.load(f)
    times = data['times']
    vars_data = data['data']
    logger.debug(data)

    keep_default_axis = is_default_axis_needed(cfg.vars)
    _, axes = create_figures_axes(cfg.plot, keep_default_axis)
    plot_data(cfg.vars, axes, times, vars_data)

    if cfg.plot.show:
        plt.show()


@cli.command('sym', help='list symbols in ELF file')
@_elf_opt(required=True)
@click.argument('pattern', required=False)
@_verbose_callback_opt
def subcmd_symbols(elf, pattern):
    list_symbols(elf, pattern)


@cli.command('completion', help='print shell completion script')
@click.argument('shell',
                type=click.Choice(['bash', 'zsh', 'fish', 'powershell']),
                required=False)
def subcmd_completion(shell):
    from click.shell_completion import get_completion_class

    if shell is None:
        shell = os.path.basename(os.environ.get('SHELL', '')) or 'bash'

    prog_name = CLI_NAME
    comp_cls = get_completion_class(shell)
    if comp_cls is None:
        click.echo(f'unsupported shell: {shell}', err=True)
        return

    complete_var = f'_{prog_name.upper().replace("-", "_")}_COMPLETE'
    comp = comp_cls(cli, {}, prog_name, complete_var)
    click.echo(comp.source())


if __name__ == '__main__':
    cli()
