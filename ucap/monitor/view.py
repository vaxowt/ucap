from typing import Any, cast

import pyqtgraph as pg
import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame,
                             QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                             QPushButton, QScrollArea, QStatusBar, QVBoxLayout,
                             QWidget)

from ucap.config import Config
from ucap.constants import (FORMATTED_CLI_NAME, MON_CURVE_COLORS,
                              MON_GUI_ICON_SIZE, MON_GUI_THEMES, QSS_PATH,
                              SHORTCUTS)


def _set_channel_checkbox_color(color: str) -> str:
    return (
        f"QCheckBox {{ color: {color}; }}"
        f"QCheckBox::indicator:checked {{ background: {color}; border-color: {color}; }}"
    )


def _create_toolbar_button(text: str,
                           callback,
                           *,
                           width: int | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("variant", "toolbar")
    if width is not None:
        btn.setFixedWidth(width)
    btn.setIconSize(QSize(MON_GUI_ICON_SIZE, MON_GUI_ICON_SIZE))
    btn.clicked.connect(callback)
    return btn


def _create_status_label(text: str, obj_name: str, tooltip: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(obj_name)
    lbl.setToolTip(tooltip)
    return lbl


class ShortcutManager:

    def __init__(self, widget: QWidget):
        self._widget = widget
        self._actions: dict[str, QAction] = {}

    def bind(self, name: str, callback) -> QAction | None:
        cfg = SHORTCUTS[name]
        if cfg.sequence == '':
            return None
        action = QAction(self._widget)
        action.setShortcut(QKeySequence(cfg.sequence))
        action.triggered.connect(callback)
        self._widget.addAction(action)
        self._actions[name] = action
        return action

    def tooltip(self, name: str) -> str:
        cfg = SHORTCUTS[name]
        if cfg.sequence == '':
            return cfg.description
        else:
            return (f"{cfg.description} ({cfg.sequence})")


class MonitorWindow(QMainWindow):
    """pyqtgraph-based real-time monitor window (pure view)."""

    mode_changed = pyqtSignal(str)
    x_range_changed = pyqtSignal(object, object)
    pause_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    save_requested = pyqtSignal()
    close_requested = pyqtSignal()
    view_all_requested = pyqtSignal()

    def __init__(self, channels: list[str], cfg: Config, parent=None):
        super().__init__(parent)
        self._is_paused = False
        self._cfg = cfg

        self._ch_color: dict[str, str] = {}
        self._qss = QSS_PATH.read_text(encoding="utf-8")
        self._theme = self._cfg.mon.theme

        self.setWindowTitle(f'{FORMATTED_CLI_NAME} monitor')
        self.resize(1200, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._pause_btn = _create_toolbar_button(' Pause',
                                                 self.pause_requested.emit,
                                                 width=110)
        self._clear_btn = _create_toolbar_button(' Clear',
                                                 self.clear_requested.emit,
                                                 width=90)
        self._save_btn = _create_toolbar_button(' Save',
                                                self.save_requested.emit,
                                                width=90)

        self._sep1 = QFrame()
        self._sep1.setFrameShape(QFrame.Shape.VLine)
        self._sep1.setProperty("variant", "separator")

        self._zoom_btn = _create_toolbar_button(' Zoom',
                                                self._on_zoom_btn,
                                                width=90)
        self._zoom_btn.setCheckable(True)
        self._zoom_btn.setEnabled(False)

        self._viewall_btn = _create_toolbar_button(' View All',
                                                   self._on_view_all,
                                                   width=90)
        self._viewall_btn.setCheckable(True)

        self._auto_y_btn = _create_toolbar_button(' Auto Y',
                                                   self._on_auto_y,
                                                   width=90)
        self._auto_y_btn.setEnabled(False)

        self._sep2 = QFrame()
        self._sep2.setFrameShape(QFrame.Shape.VLine)
        self._sep2.setProperty("variant", "separator")

        self._probe_btn = _create_toolbar_button(' Probe',
                                                 self._on_probe_btn,
                                                 width=90)
        self._probe_btn.setCheckable(True)

        toolbar.addWidget(self._pause_btn)
        toolbar.addWidget(self._clear_btn)
        toolbar.addWidget(self._save_btn)
        toolbar.addWidget(self._sep1)
        toolbar.addWidget(self._zoom_btn)
        toolbar.addWidget(self._viewall_btn)
        toolbar.addWidget(self._auto_y_btn)
        toolbar.addWidget(self._sep2)
        toolbar.addWidget(self._probe_btn)
        toolbar.addStretch()

        self._theme_btn = _create_toolbar_button('',
                                                 self._toggle_theme,
                                                 width=32)
        toolbar.addWidget(self._theme_btn)

        main_layout.addLayout(toolbar)

        # Content
        content = QHBoxLayout()

        pg.setConfigOptions(antialias=self._cfg.mon.antialias,
                            useOpenGL=self._cfg.mon.use_opengl)
        self._plot_widget = pg.PlotWidget()
        # hide auto-range 'A' button
        cast(pg.PlotItem, self._plot_widget.plotItem).hideButtons()
        self._plot_widget.setClipToView(self._cfg.mon.downsampling)
        self._plot_widget.setObjectName("plot-widget")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.4)
        self._plot_widget.setLabel('bottom', 'Time', units='s')
        content.addWidget(self._plot_widget, stretch=5)

        self._probe_label = QLabel(self._plot_widget)
        self._probe_label.setAlignment(Qt.AlignmentFlag.AlignLeft
                                       | Qt.AlignmentFlag.AlignTop)
        self._probe_label.setProperty("variant", "probe")
        self._probe_label.hide()
        self._probe_vline = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen(color=MON_GUI_THEMES[self._theme]['accent'],
                         style=Qt.PenStyle.DashLine,
                         width=1))
        self._plot_widget.addItem(self._probe_vline)
        self._probe_vline.hide()

        # Right panel
        panel = QWidget()
        panel.setObjectName("channel-panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(4)
        panel_label = QLabel('Channels')
        panel_label.setProperty('variant', 'panel-title')
        panel_layout.addWidget(panel_label)

        self._toggle_all_btn = QPushButton('Deselect All')
        self._toggle_all_btn.setProperty("variant", "panel-btn")
        self._toggle_all_btn.setFixedHeight(26)
        self._toggle_all_btn.clicked.connect(self._toggle_all_channels)
        panel_layout.addWidget(self._toggle_all_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(200)
        scroll_content = QWidget()
        scroll_content.setObjectName("channel-panel-scroll")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(2, 2, 2, 2)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}

        for i, ch_name in enumerate(channels):
            color = MON_CURVE_COLORS[i % len(MON_CURVE_COLORS)]
            self._ch_color[ch_name] = color
            pen = pg.mkPen(color=color, width=self._cfg.mon.linewidth)
            curve = self._plot_widget.plot(pen=pen, name=ch_name)
            if self._cfg.mon.downsampling:
                curve.setDownsampling(auto=True, method='peak')
            self._curves[ch_name] = curve

            cb = QCheckBox(ch_name)
            cb.setChecked(True)
            cb.setStyleSheet(_set_channel_checkbox_color(color))
            cb.toggled.connect(
                lambda checked, cn=ch_name: self._toggle_curve(cn, checked))
            cb.toggled.connect(lambda _: self._update_toggle_all_btn())
            scroll_layout.addWidget(cb)
            self._checkboxes[ch_name] = cb

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        panel_layout.addWidget(scroll)
        content.addWidget(panel, stretch=1)
        main_layout.addLayout(content)

        # Status bar
        sb = cast(QStatusBar, self.statusBar())
        sb.setSizeGripEnabled(False)
        self._sb_serial = _create_status_label('Probe: N/A',
                                               'status-serial',
                                               'Probe serial number')
        sb.addWidget(self._sb_serial)

        self._sb_elapsed: QLabel
        self._sb_queue: QLabel
        self._sb_mem: QLabel
        self._sb_freq: QLabel
        self._sb_fps: QLabel

        sb_labels = [
            ('_sb_elapsed', 'Elapsed: 0.0s', 'status-elapsed',
             'Elapsed acquisition time'),
            ('_sb_queue', 'Queue: 0', 'status-queue',
             'Queue backlog (higher = performance bottleneck)'),
            ('_sb_mem', 'Mem: --', 'status-memory',
             'Memory usage of buffered data'),
            ('_sb_freq', 'rw_freq: -- Hz', 'status-frequency',
             'Actual read/write frequency'),
            ('_sb_fps', 'GUI: -- fps', 'status-fps', 'GUI refresh rate'),
        ]
        for attr, text, obj_name, tip in sb_labels:
            lbl = _create_status_label(text, obj_name, tip)
            setattr(self, attr, lbl)
            sb.addPermanentWidget(lbl)

        self._apply_theme()

        # Interaction state
        self._set_mode('pan')

        self._probe_scene_pos: Any | None = None
        self._drain_popup: QDialog | None = None

        _scene = self._plot_widget.scene()
        if _scene is None:
            _scene = pg.GraphicsScene()
            self._plot_widget.setScene(_scene)
        self._proxy = pg.SignalProxy(cast(Any, _scene).sigMouseMoved,
                                     rateLimit=60,
                                     slot=self._on_mouse_moved)

        self._plot_widget.getViewBox().sigRangeChangedManually.connect(
            self._on_range_changed_manually)

        self._plot_widget.getViewBox().sigXRangeChanged.connect(
            self.x_range_changed.emit)

        # Shortcuts
        self._shortcuts = ShortcutManager(self)
        shortcut_buttons = [
            ('pause', '_pause_btn'),
            ('clear', '_clear_btn'),
            ('save', '_save_btn'),
            ('zoom', '_zoom_btn'),
            ('view_all', '_viewall_btn'),
            ('auto_y', '_auto_y_btn'),
            ('probe', '_probe_btn'),
            ('theme', '_theme_btn'),
        ]
        for name, attr in shortcut_buttons:
            btn = getattr(self, attr)
            self._shortcuts.bind(name, btn.click)
            btn.setToolTip(self._shortcuts.tooltip(name))

    # ================================================================
    # Public API — called by controller
    # ================================================================

    def set_pause_state(self, paused: bool):
        self._is_paused = paused
        theme = MON_GUI_THEMES[self._theme]
        icon_color = theme['text_secondary']

        if paused:
            self._pause_btn.setIcon(qta.icon('mdi.play', color=icon_color))
            self._pause_btn.setText(' Continue')
            self._zoom_btn.setEnabled(True)
            self._auto_y_btn.setEnabled(True)
            self._on_view_all()
        else:
            self._pause_btn.setIcon(qta.icon('mdi.pause', color=icon_color))
            self._pause_btn.setText(' Pause')
            self._zoom_btn.setEnabled(False)
            self._auto_y_btn.setEnabled(False)
            if self._mode == 'zoom':
                self._set_mode('pan')

        if self._mode in ('pan', 'probe'):
            self._plot_widget.setMouseEnabled(x=paused, y=paused)

    def update_status(self, serial: str, freq_hz: float, fps: float,
                      mem_bytes: int, elapsed: float, queue_size: int):
        self._sb_serial.setText(f'Probe: {serial}' if serial else 'Probe: N/A')
        self._sb_elapsed.setText(f'Elapsed: {elapsed:.1f}s')
        self._sb_queue.setText(f'Queue: {queue_size}')
        self._sb_freq.setText(
            f'rw_freq: {freq_hz:.1f} Hz' if freq_hz else 'rw_freq: -- Hz')
        self._sb_fps.setText(f'GUI: {fps:.0f} fps')
        if mem_bytes < 1024:
            mem_str = f'{mem_bytes} B'
        elif mem_bytes < 1024 * 1024:
            mem_str = f'{mem_bytes / 1024:.1f} KB'
        else:
            mem_str = f'{mem_bytes / 1024 / 1024:.1f} MB'
        self._sb_mem.setText(f'Mem: {mem_str}')

    def refresh_curves(self, t_start, t_end):
        vb = self._plot_widget.getViewBox()
        vb.setRange(xRange=(t_start, t_end), padding=0.0, update=True)
        self._plot_widget.enableAutoRange(axis='y')
        self._plot_widget.disableAutoRange(axis='x')

    def clear_curves(self):
        for curve in self._curves.values():
            curve.setData([], [])
        self._probe_label.hide()
        self._probe_vline.hide()
        self._probe_scene_pos = None

    def is_view_all_checked(self) -> bool:
        return self._viewall_btn.isChecked()

    def get_visible_range(self) -> tuple[float, float]:
        return self._plot_widget.getViewBox().viewRange()[0]

    def set_curve_data(self, ch_name: str, time, data):
        curve = self._curves.get(ch_name)
        if curve:
            curve.setData(time, data)

    def show_drain_popup(self):
        popup = QDialog(self)
        popup.setWindowFlags(Qt.WindowType.FramelessWindowHint
                             | Qt.WindowType.Window)
        popup.setModal(True)
        layout = QVBoxLayout(popup)
        layout.addWidget(QLabel("draining data ..."))
        popup.show()
        self._drain_popup = popup

    def close_drain_popup(self):
        if self._drain_popup is not None:
            self._drain_popup.close()
            self._drain_popup = None

    # ---- Save dialogs ----

    def ask_save_choice(self, n_total, n_vis) -> str | None:
        msg = QMessageBox(self)
        msg.setWindowTitle('Save Data')
        msg.setText('Save which data?')
        all_btn = msg.addButton(f'All data ({n_total} samples)',
                                QMessageBox.ButtonRole.AcceptRole)
        vis_btn = msg.addButton(f'Visible range ({n_vis} samples)',
                                QMessageBox.ButtonRole.AcceptRole)
        msg.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(all_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == all_btn:
            return 'all'
        if clicked == vis_btn:
            return 'visible'
        return None

    def ask_overwrite_or_choose(self, save_path, save_dir) -> str | None:
        msg = QMessageBox(self)
        msg.setWindowTitle('Directory Not Empty')
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(f'Output directory is not empty:\n{save_path}\n\n'
                    'What would you like to do?')
        overwrite_btn = msg.addButton('Overwrite',
                                      QMessageBox.ButtonRole.AcceptRole)
        choose_btn = msg.addButton('Choose Path...',
                                   QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(cancel_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is None:
            return None
        if clicked == overwrite_btn:
            return 'overwrite'
        if clicked == choose_btn:
            new_dir = QFileDialog.getExistingDirectory(
                self, 'Choose Save Directory', str(save_dir))
            if not new_dir:
                return None
            return new_dir
        return None

    def show_info(self, title, text):
        QMessageBox.information(self, title, text)

    def show_error(self, title, text):
        QMessageBox.critical(self, title, text)

    # ================================================================
    # Mode buttons
    # ================================================================

    def _set_mode(self, mode: str):
        self._mode = mode
        pw = self._plot_widget

        self._zoom_btn.blockSignals(True)
        self._probe_btn.blockSignals(True)
        self._zoom_btn.setChecked(mode == 'zoom')
        self._probe_btn.setChecked(mode == 'probe')
        self._zoom_btn.blockSignals(False)
        self._probe_btn.blockSignals(False)

        if mode == 'zoom':
            pw.setMouseEnabled(x=False, y=False)
            pw.getViewBox().setMouseMode(pg.ViewBox.RectMode)
            pw.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'probe':
            pw.setMouseEnabled(x=self._is_paused, y=self._is_paused)
            pw.getViewBox().setMouseMode(pg.ViewBox.PanMode)
            pw.unsetCursor()
        else:
            pw.setMouseEnabled(x=self._is_paused, y=self._is_paused)
            pw.getViewBox().setMouseMode(pg.ViewBox.PanMode)
            pw.unsetCursor()

        if mode != 'probe':
            self._probe_label.hide()
            self._probe_vline.hide()
            self._probe_scene_pos = None

        self.mode_changed.emit(mode)

    def _on_zoom_btn(self):
        if not self._zoom_btn.isEnabled():
            return
        if self._zoom_btn.isChecked():
            self._set_mode('zoom')
        else:
            self._set_mode('pan')

    def _on_probe_btn(self):
        if self._probe_btn.isChecked():
            self._set_mode('probe')
        else:
            self._set_mode('pan')

    def _on_auto_y(self):
        visible = [
            curve for ch_name, curve in self._curves.items()
            if self._checkboxes[ch_name].isChecked()
        ]
        vb = self._plot_widget.getViewBox()
        bounds = vb.childrenBounds(items=visible)
        y_min, y_max = bounds[1]
        if y_min is not None and y_max is not None:
            padding = (y_max - y_min) * 0.05 or 1.0
            vb.setRange(yRange=(y_min - padding, y_max + padding))

    def _on_view_all(self):
        if self._viewall_btn.isChecked():
            if self._is_paused:
                self.view_all_requested.emit()
                self._viewall_btn.blockSignals(True)
                self._viewall_btn.setChecked(False)
                self._viewall_btn.blockSignals(False)

    def _on_range_changed_manually(self):
        if self._mode == 'pan':
            self._viewall_btn.blockSignals(True)
            self._viewall_btn.setChecked(False)
            self._viewall_btn.blockSignals(False)

    # ================================================================
    # Channel visibility
    # ================================================================

    def _toggle_curve(self, ch_name: str, visible: bool):
        curve = self._curves.get(ch_name)
        if curve:
            curve.setVisible(visible)

    def _all_channels_checked(self) -> bool:
        return all(cb.isChecked() for cb in self._checkboxes.values())

    def _toggle_all_channels(self):
        new_state = not self._all_channels_checked()
        for cb in self._checkboxes.values():
            cb.setChecked(new_state)
        self._toggle_all_btn.setText(
            'Select All' if not new_state else 'Deselect All')

    def _update_toggle_all_btn(self):
        self._toggle_all_btn.setText(
            'Select All'
            if not self._all_channels_checked() else 'Deselect All')

    # ================================================================
    # Theme
    # ================================================================

    def _toggle_theme(self):
        self._theme = 'dark' if self._theme == 'light' else 'light'
        self._apply_theme()

    def _apply_theme(self):
        theme = MON_GUI_THEMES[self._theme]
        icon_color = theme['text_secondary']

        self.setStyleSheet(self._qss % theme)

        self._pause_btn.setIcon(
            qta.icon('mdi.play' if self._is_paused else 'mdi.pause',
                     color=icon_color))
        self._clear_btn.setIcon(
            qta.icon('mdi.delete-outline', color=icon_color))
        self._save_btn.setIcon(
            qta.icon('mdi.content-save-outline', color=icon_color))
        self._zoom_btn.setIcon(qta.icon('mdi.crop-free', color=icon_color))
        self._viewall_btn.setIcon(
            qta.icon('mdi.home-outline', color=icon_color))
        self._auto_y_btn.setIcon(
            qta.icon('mdi.arrow-expand-vertical', color=icon_color))
        self._probe_btn.setIcon(
            qta.icon('mdi.crosshairs-gps', color=icon_color))

        if self._theme == 'dark':
            self._theme_btn.setIcon(
                qta.icon('mdi.weather-sunny', color=icon_color))
        else:
            self._theme_btn.setIcon(
                qta.icon('mdi.weather-night', color=icon_color))

        self._plot_widget.setBackground(theme['plot_bg'])
        axis_pen = pg.mkPen(color=theme['plot_grid'], width=1)
        axis_text = pg.mkColor(theme['plot_axis'])
        for axis in ('bottom', 'left'):
            ax = self._plot_widget.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(axis_text)

        self._probe_vline.setPen(
            pg.mkPen(color=theme['accent'],
                     style=Qt.PenStyle.DashLine,
                     width=1))

        for ch_name, cb in self._checkboxes.items():
            cb.setStyleSheet(
                _set_channel_checkbox_color(self._ch_color[ch_name]))

    # ================================================================
    # Probe — view only: scene→data coord mapping, label rendering
    # ================================================================

    def _on_mouse_moved(self, evt):
        if self._mode != 'probe':
            return

        pos = evt[0]
        if pos is None:
            return

        self._probe_scene_pos = pos

    def get_probe_x(self) -> float | None:
        if self._mode != 'probe':
            return None
        if self._probe_scene_pos is None:
            return None
        vb = self._plot_widget.getViewBox()
        mouse_point = vb.mapSceneToView(self._probe_scene_pos)
        x = mouse_point.x()
        self._probe_vline.setPos(x)
        return x

    def set_probe_line_x(self, x: float):
        self._probe_vline.setPos(x)

    def show_probe_label(self, probe_x: float, values: dict[str, float]):
        lines = [f't = {probe_x:.6f} s']
        for ch_name, val in values.items():
            cb = self._checkboxes.get(ch_name)
            if cb is not None and cb.isChecked():
                lines.append(f'<span style="color:{self._ch_color[ch_name]}">'
                             f'{ch_name}: {val:.6g}</span>')
        self._show_label_text(lines)

    def _show_label_text(self, lines: list[str]):
        pos = self._probe_scene_pos
        if pos is None:
            return
        self._probe_vline.show()
        self._probe_label.setText('<br>'.join(lines))
        self._probe_label.adjustSize()
        label_w = self._probe_label.width()
        label_h = self._probe_label.height()
        plot_w = self._plot_widget.width()
        plot_h = self._plot_widget.height()
        sx = pos.x() + 15
        sy = pos.y() + 15
        if sx + label_w > plot_w - 5:
            sx = pos.x() - label_w - 10
        if sy + label_h > plot_h - 5:
            sy = pos.y() - label_h - 10
        self._probe_label.move(int(sx), int(sy))
        self._probe_label.show()

    # ================================================================
    # Close
    # ================================================================

    def closeEvent(self, a0):
        self.close_requested.emit()
        super().closeEvent(a0)
