"""Matplotlib plotting functions."""

import logging
from collections.abc import Iterable

import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from ucap.config import FigureConfig, LinePlotConfig, PlotConfig, Var
from ucap.constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def create_figures_axes(plot_config: PlotConfig, keep_default_axis: bool):
    figures_cfg = plot_config.figures
    for fig in figures_cfg:
        if fig.name == 'default':
            keep_default_axis = False
            break
    if keep_default_axis:
        figures_cfg.append(FigureConfig(name='default', axes='default'))
    figures = {}
    axes = {}
    for fig in plot_config.figures:
        axes_layout = fig.axes
        if not isinstance(fig.axes, list):
            axes_layout = [axes_layout]
        if not isinstance(fig.axes[0], list):
            axes_layout = [axes_layout]

        nrows = len(axes_layout)
        ncols = len(axes_layout[0])
        figure, ax = plt.subplots(nrows,
                                  ncols,
                                  squeeze=False,
                                  sharex=fig.sharex,
                                  sharey=fig.sharey,
                                  figsize=fig.figsize,
                                  layout=fig.layout)
        if fig.name:
            figure.canvas.manager.set_window_title(fig.name)
        figures[fig.name] = figure
        for row in range(nrows):
            for col in range(ncols):
                ax_name = axes_layout[row][col]
                axis: Axes = ax[row][col]
                if ax_name is False:
                    plt.sca(axis)
                    plt.axis('off')
                    continue
                if axis_cfg := plot_config.axes.get(ax_name):
                    axis.set(**axis_cfg.kwargs)
                axes[ax_name] = axis
    return figures, axes


def is_default_axis_needed(vars: list[Var]):
    needed = False
    for var in vars:
        if isinstance(var.plot, dict):
            for _, v in var.plot.items():
                if v.axis == 'default':
                    needed = True
                    break
        elif isinstance(var.plot, LinePlotConfig):
            if var.plot.axis == 'default':
                needed = True
                break
    return needed


def plot_data(vars: list[Var], axes, times: Iterable, data: dict):
    for var in vars:
        if var.is_write or var.plot is False:
            continue
        plot_cfg = {}
        var_data = data[var.name]
        if var.type is dict:
            if isinstance(var.plot, LinePlotConfig):
                for k in var_data.keys():
                    plot_cfg[k] = var.plot
            elif isinstance(var.plot, dict):
                plot_cfg = var.plot
        else:
            var_data = {var.name: var_data}
            plot_cfg[var.name] = var.plot

        for k, v in var_data.items():
            cfg = plot_cfg.get(k)
            if cfg is None:
                continue
            ax = axes.get(cfg.axis)
            if ax is None:
                logger.warning(
                    f"axis '{cfg.axis}' is used by '{k}', but it's not defined"
                )
                continue
            kwargs = cfg.kwargs.copy()
            if 'label' not in kwargs:
                if var.type is dict:
                    kwargs['label'] = f'{var.name}.{k}'
                else:
                    kwargs['label'] = f'{var.name}'
            plt.sca(ax)
            getattr(plt, cfg.type)(times, v, **kwargs)
            plt.legend()
