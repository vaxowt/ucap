import logging
import multiprocessing as mp
import pathlib
import sys
import time
from queue import Empty

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer

from ucap.config import Config
from ucap.constants import LOGGER_NAME, MON_GUI_DRAINING_DATA_LIMIT
from ucap.export import build_save_data, resolve_save_path, save_data
from ucap.monitor.model import (MonitorModel, build_mon_channels,
                                  channels_to_var_data, interpolate_at,
                                  reader_process, snap_at)
from ucap.monitor.view import MonitorWindow

logger = logging.getLogger(LOGGER_NAME)


class Monitor:
    """Orchestrates reader process, data flow, and view updates."""

    def __init__(self, cfg: Config, config_path: pathlib.Path):
        self._cfg = cfg
        self._channels = build_mon_channels(cfg.vars)
        self._config_path = config_path
        self._model = MonitorModel(self._channels)

        self._ctx = mp.get_context('spawn')
        self._queue: mp.Queue = self._ctx.Queue(
            maxsize=self._cfg.mon.queue_size)
        self._stop_event = self._ctx.Event()
        self._pause_event = self._ctx.Event()
        self._reader_process = None
        self._metadata = None

        self._is_paused = False
        self._is_draining = False
        self._probe_active = False
        self._last_tick_time = 0.0
        self._tick_fps = 0.0

    def start(self):
        self._reader_process = self._ctx.Process(
            target=reader_process,
            args=(self._cfg, self._queue, self._stop_event, self._pause_event),
            daemon=True,
        )
        self._reader_process.start()

        try:
            item = self._queue.get(timeout=self._cfg.pre_delay + 10)
            msg_type, payload = item
            if msg_type == 'error':
                logger.error(f'reader process error: {payload["message"]}')
                self.stop()
                sys.exit(1)
            self._metadata = payload
        except Exception as e:
            logger.error(f'failed to fetch init data: {e}')
            self.stop()
            sys.exit(1)

        app = pg.mkQApp()
        self._window = MonitorWindow(
            channels=self._channels,
            cfg=self._cfg,
        )
        self._window.x_range_changed.connect(self._x_range_changed)
        self._window.pause_requested.connect(self._toggle_pause)
        self._window.clear_requested.connect(self._clear)
        self._window.save_requested.connect(self._save)
        self._window.close_requested.connect(self.stop)
        self._window.view_all_requested.connect(self._on_view_all_requested)
        self._window.mode_changed.connect(self._on_mode_changed)
        self._window.show()

        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(self._cfg.mon.status_interval)

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._cfg.mon.refresh_interval)

        try:
            app.exec()
        finally:
            pass

    def stop(self):
        if hasattr(self, '_status_timer'):
            self._status_timer.stop()
        if hasattr(self, '_timer'):
            self._timer.stop()
        self._stop_event.set()
        self._pause_event.clear()
        if self._reader_process:
            self._reader_process.join(timeout=3)
            if self._reader_process.is_alive():
                self._reader_process.terminate()
                self._reader_process.join(timeout=1)

    def _on_mode_changed(self, mode: str):
        self._probe_active = (mode == 'probe')

    def _on_view_all_requested(self):
        if self._model.is_empty:
            return
        t_start = self._model.time_start
        t_end = self._model.time_end
        self._window.refresh_curves(t_start, t_end)

    # ================================================================
    # Timer tick — drain data and push to view
    # ================================================================

    def _tick(self):
        if self._stop_event.is_set():
            self._timer.stop()
            self._window.close()
            return

        now = time.perf_counter()
        dt = now - self._last_tick_time
        self._last_tick_time = now
        self._tick_fps = 1.0 / dt if dt > 0 else 0.0

        cnt = self._drain_queue()

        if self._is_draining and cnt == 0:
            self._window.close_drain_popup()
            self._is_draining = False
            self._window.set_pause_state(True)

        self._refresh_view()

    def _drain_queue(self) -> int:
        cnt = 0
        while True:
            try:
                timestamp, local_values = self._queue.get_nowait()
                self._model.append(timestamp, local_values)
                cnt += 1
                if cnt >= MON_GUI_DRAINING_DATA_LIMIT:
                    break
            except Empty:
                break
        return cnt

    def _refresh_view(self):
        if self._model.is_empty:
            return

        if not self._is_paused:
            t_end = self._model.time_end

            if self._window.is_view_all_checked():
                t_start = self._model.time_start
            else:
                t_start = t_end - self._cfg.mon.view_window
                if t_start < self._model.time_start:
                    t_start = self._model.time_start

            self._window.refresh_curves(t_start, t_end)
        if self._probe_active:
            self._update_probe()

    def _update_status(self):
        freq_hz = self._model.read_frequency()
        serial = (self._metadata or {}).get('serial', '')
        mem = self._model.memory_estimate()
        elapsed = self._model.elapsed()
        qs = self._queue.qsize()

        self._window.update_status(serial, freq_hz, self._tick_fps, mem,
                                   elapsed, qs)

    def _update_probe(self):
        x = self._window.get_probe_x()
        if x is None:
            return

        t_start, t_end = self._window.get_visible_range()
        idx_start = self._model.time_to_index(t_start)
        idx_end = self._model.time_to_index(t_end)

        times = self._model.get_times(idx_start, idx_end)
        if len(times) == 0:
            self._window.show_probe_label(0.0, {})
            return

        if self._cfg.mon.probe_interpolation:
            probe_x = x
            get_val = lambda arr_slice: interpolate_at(times, arr_slice, x)
        else:
            idx, probe_x = snap_at(times, x)
            self._window.set_probe_line_x(probe_x)
            get_val = lambda arr_slice: arr_slice[idx] if idx < len(arr_slice
                                                                     ) else None

        values = {}
        for ch_name in self._channels:
            if self._model.channel_size(ch_name) < idx_end:
                continue
            arr = self._model.get_data(ch_name, idx_start, idx_end)
            val = get_val(arr)
            if val is not None:
                values[ch_name] = val
        self._window.show_probe_label(probe_x, values)

    # ================================================================
    # User actions
    # ================================================================

    def _x_range_changed(self, _, range):
        if self._model.is_empty:
            return
        idx_start = self._model.time_to_index(range[0])
        idx_end = self._model.time_to_index(range[1])
        t_arr = np.array(self._model.get_times(idx_start, idx_end))
        for ch_name in self._channels:
            self._window.set_curve_data(
                ch_name, t_arr,
                np.array(self._model.get_data(ch_name, idx_start, idx_end)))

    def _toggle_pause(self):
        self._is_paused = not self._is_paused
        if self._is_paused:
            self._pause_event.set()
            if self._queue.qsize() > 0:
                self._is_draining = True
                self._window.show_drain_popup()
            else:
                self._window.set_pause_state(True)
        else:
            self._pause_event.clear()
            self._window.set_pause_state(False)

    def _clear(self):
        self._model.clear()
        self._window.clear_curves()

    def _save(self):
        n_total = self._model.size
        if not n_total:
            self._window.show_info('Save', 'No data to save.')
            return

        t_start, t_end = self._window.get_visible_range()
        idx_vis_start = self._model.time_to_index(t_start)
        idx_vis_end = self._model.time_to_index(t_end)
        n_vis = idx_vis_end - idx_vis_start
        choice = self._window.ask_save_choice(n_total, n_vis)
        if choice is None:
            return

        idx_start, idx_end = (0,
                              n_total) if choice == 'all' else (idx_vis_start,
                                                                idx_vis_end)
        times = self._model.get_times(idx_start, idx_end)
        ch_data = {
            ch: self._model.get_data(ch, idx_start, idx_end)
            for ch in self._channels
        }
        vars_data = channels_to_var_data(self._cfg.vars, times, ch_data)

        save_path = resolve_save_path(self._cfg.save,
                                      self._window.ask_overwrite_or_choose)
        if save_path is None:
            return

        data, metadata = build_save_data(times, vars_data, self._cfg)
        if self._metadata is not None:
            metadata.update(self._metadata)

        config_raw = None
        if self._cfg.save.save_config:
            try:
                config_raw = self._config_path.read_bytes()
            except Exception:
                pass

        try:
            save_data(self._cfg.save, save_path, config_raw, data, metadata,
                      {})
            self._window.show_info('Save', f'Data saved to:\n{save_path}')
        except Exception as e:
            self._window.show_error('Save Error', f'Failed to save:\n{e}')
