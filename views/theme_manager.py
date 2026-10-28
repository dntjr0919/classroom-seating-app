"""
교실 자리 배치 프로그램 - 테마(라이트/다크/시스템 연동) 관리 모듈 (views/theme_manager.py)
시스템 다크 모드 설정으로 인해 QComboBox 팝업, QTableWidget, QInputDialog 등의
글자색과 배경색이 섞여 보이지 않는 현상을 원천 차단하고,
사용자가 라이트 모드 / 다크 모드를 자유롭게 선택할 수 있도록 통합 QPalette 및 QSS를 제공합니다.
"""

from __future__ import annotations

import os
import sys
from typing import Optional, Tuple

from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPalette, QPixmap, QPolygon
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from models import ThemeMode


def show_saved_file_message(
    parent: Optional[QWidget],
    title: str,
    message: str,
    file_path: str,
) -> None:
    """
    파일 저장 완료 안내 대화상자를 표시합니다.
    '확인' 버튼 왼쪽에 '열기' 버튼을 제공하여 방금 저장한 파일을 기본 프로그램으로 즉시 엽니다.
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(QMessageBox.Icon.Information)

    # YesRole을 사용하여 Windows UI 레이아웃상 '확인'(AcceptRole)의 왼쪽에 '열기' 버튼 배치
    btn_open = msg_box.addButton("열기", QMessageBox.ButtonRole.YesRole)
    btn_open.setToolTip("방금 저장한 파일을 연결된 기본 프로그램으로 엽니다.")
    btn_ok = msg_box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    msg_box.setDefaultButton(btn_ok)

    msg_box.exec()

    if msg_box.clickedButton() == btn_open:
        try:
            os.startfile(os.path.abspath(file_path))
        except Exception as err:
            QMessageBox.warning(
                parent,
                "파일 열기 실패",
                f"파일을 여는 중 오류가 발생했습니다:\n{err}",
            )


class ThemeManager:
    """애플리케이션 전역 테마(Light / Dark / System) 상태 및 스타일시트 관리자"""

    SETTINGS_ORG = "ClassroomSeatingApp"
    SETTINGS_APP = "UISettings"
    SETTINGS_KEY = "theme_mode"

    _current_mode: ThemeMode = ThemeMode.LIGHT
    _resolved_dark: bool = False

    @classmethod
    def load_saved_mode(cls) -> ThemeMode:
        """저장된 테마 모드를 QSettings에서 불러옵니다 (기본값: LIGHT)."""
        settings = QSettings(cls.SETTINGS_ORG, cls.SETTINGS_APP)
        raw = settings.value(cls.SETTINGS_KEY, ThemeMode.LIGHT.value, type=str)
        try:
            return ThemeMode(raw)
        except ValueError:
            return ThemeMode.LIGHT

    @classmethod
    def save_mode(cls, mode: ThemeMode) -> None:
        """선택한 테마 모드를 QSettings에 영구 저장합니다."""
        settings = QSettings(cls.SETTINGS_ORG, cls.SETTINGS_APP)
        settings.setValue(cls.SETTINGS_KEY, mode.value)
        settings.sync()

    @classmethod
    def detect_system_dark(cls) -> bool:
        """운영체제(Windows 등)의 다크 모드 활성화 여부를 감지합니다."""
        try:
            app = QGuiApplication.instance()
            if app is not None and hasattr(app, "styleHints"):
                hints = app.styleHints()
                if hints is not None and hasattr(hints, "colorScheme"):
                    scheme = hints.colorScheme()
                    if scheme == Qt.ColorScheme.Dark:
                        return True
                    if scheme == Qt.ColorScheme.Light:
                        return False
        except Exception:
            pass

        # Windows 레지스트리 폴백 확인
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return val == 0
        except Exception:
            return False

    @classmethod
    def current_mode(cls) -> ThemeMode:
        return cls._current_mode

    @classmethod
    def is_dark(cls) -> bool:
        """현재 실제 적용 중인 테마가 다크 모드인지 여부를 반환합니다."""
        return cls._resolved_dark

    @classmethod
    def apply_theme(cls, app: Optional[QApplication], mode: ThemeMode) -> bool:
        """
        지정된 테마 모드를 QApplication의 스타일, QPalette, 전역 QSS에 일괄 적용합니다.
        반환값: 실제 적용된 다크 모드 여부 (True=다크, False=라이트)
        """
        cls._current_mode = mode
        cls.save_mode(mode)

        if mode == ThemeMode.DARK:
            cls._resolved_dark = True
        elif mode == ThemeMode.LIGHT:
            cls._resolved_dark = False
        else:
            cls._resolved_dark = cls.detect_system_dark()

        if app is None:
            app_inst = QApplication.instance()
            if isinstance(app_inst, QApplication):
                app = app_inst

        if app is not None:
            # Windows 11 네이티브 스타일이 QComboBox 팝업의 텍스트 색상만 다크 팔레트로 바꾸고
            # 배경은 흰색으로 강제하는 현상을 방지하기 위해 Fusion 스타일 + 명시적 QPalette 적용
            app.setStyle("Fusion")
            palette = cls._build_palette(cls._resolved_dark)
            app.setPalette(palette)
            app.setStyleSheet(cls.get_global_stylesheet(cls._resolved_dark))

        return cls._resolved_dark

    @classmethod
    def _build_palette(cls, is_dark: bool) -> QPalette:
        """OS 설정에 휘둘리지 않는 완전한 QPalette를 생성합니다."""
        palette = QPalette()
        if is_dark:
            win_bg = QColor("#0F172A")
            base_bg = QColor("#1E293B")
            alt_bg = QColor("#26334D")
            text_fg = QColor("#F8FAFC")
            sub_fg = QColor("#94A3B8")
            btn_bg = QColor("#1E293B")
            highlight_bg = QColor("#2563EB")
            highlight_fg = QColor("#FFFFFF")
            tooltip_bg = QColor("#1E293B")
            tooltip_fg = QColor("#F8FAFC")
        else:
            win_bg = QColor("#F8FAFC")
            base_bg = QColor("#FFFFFF")
            alt_bg = QColor("#F1F5F9")
            text_fg = QColor("#0F172A")
            sub_fg = QColor("#64748B")
            btn_bg = QColor("#FFFFFF")
            highlight_bg = QColor("#2563EB")
            highlight_fg = QColor("#FFFFFF")
            tooltip_bg = QColor("#1E293B")
            tooltip_fg = QColor("#FFFFFF")

        palette.setColor(QPalette.ColorRole.Window, win_bg)
        palette.setColor(QPalette.ColorRole.WindowText, text_fg)
        palette.setColor(QPalette.ColorRole.Base, base_bg)
        palette.setColor(QPalette.ColorRole.AlternateBase, alt_bg)
        palette.setColor(QPalette.ColorRole.ToolTipBase, tooltip_bg)
        palette.setColor(QPalette.ColorRole.ToolTipText, tooltip_fg)
        palette.setColor(QPalette.ColorRole.Text, text_fg)
        palette.setColor(QPalette.ColorRole.PlaceholderText, sub_fg)
        palette.setColor(QPalette.ColorRole.Button, btn_bg)
        palette.setColor(QPalette.ColorRole.ButtonText, text_fg)
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Highlight, highlight_bg)
        palette.setColor(QPalette.ColorRole.HighlightedText, highlight_fg)
        palette.setColor(QPalette.ColorRole.Link, QColor("#3B82F6"))

        # 비활성(Disabled) 상태 색상
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, sub_fg)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, sub_fg)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, sub_fg)

        return palette

    @classmethod
    def get_arrow_icon_paths(cls) -> Tuple[str, str, str, str]:
        """
        QSpinBox용 고대비 벡터 화살표 아이콘 경로(up_dark, down_dark, up_light, down_light)를 반환합니다.
        아이콘 파일이 없으면 자동으로 생성합니다.
        """
        base_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        assets_dir = os.path.join(base_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        up_dark = os.path.join(assets_dir, "arrow_up_dark.png")
        down_dark = os.path.join(assets_dir, "arrow_down_dark.png")
        up_light = os.path.join(assets_dir, "arrow_up_light.png")
        down_light = os.path.join(assets_dir, "arrow_down_light.png")

        def make_arrow(path: str, color_hex: str, point_up: bool) -> None:
            if not os.path.exists(path):
                pix = QPixmap(16, 16)
                pix.fill(QColor(0, 0, 0, 0))
                painter = QPainter(pix)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QColor(color_hex))
                painter.setPen(Qt.PenStyle.NoPen)
                if point_up:
                    poly = QPolygon([QPoint(8, 4), QPoint(13, 11), QPoint(3, 11)])
                else:
                    poly = QPolygon([QPoint(3, 5), QPoint(13, 5), QPoint(8, 12)])
                painter.drawPolygon(poly)
                painter.end()
                pix.save(path)

        make_arrow(up_dark, "#F8FAFC", True)
        make_arrow(down_dark, "#F8FAFC", False)
        make_arrow(up_light, "#1E293B", True)
        make_arrow(down_light, "#1E293B", False)

        return (
            up_dark.replace("\\", "/"),
            down_dark.replace("\\", "/"),
            up_light.replace("\\", "/"),
            down_light.replace("\\", "/"),
        )

    @classmethod
    def get_global_stylesheet(cls, is_dark: bool) -> str:
        """라이트/다크 모드별 전체 위젯(QComboBox 팝업, QMenu, QDialog, QTableWidget 등) 스타일시트"""
        up_dark, down_dark, up_light, down_light = cls.get_arrow_icon_paths()
        if is_dark:
            return f"""
            QMainWindow, QDialog, QMessageBox, QInputDialog {{
                background-color: #0F172A;
                color: #F8FAFC;
            }}
            QWidget {{
                color: #F8FAFC;
            }}
            QLabel {{
                color: #E2E8F0;
                background: transparent;
            }}
            QFrame#ToolbarFrame, QFrame#FormFrame {{
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 6px;
            }}
            QPushButton {{
                background-color: #1E293B;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 7px 14px;
                color: #F8FAFC;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #334155;
                border-color: #64748B;
            }}
            QPushButton:disabled {{
                background-color: #0F172A;
                border-color: #1E293B;
                color: #64748B;
            }}
            QPushButton#PrimaryButton {{
                background-color: #2563EB;
                border: 1px solid #3B82F6;
                color: #FFFFFF;
            }}
            QPushButton#PrimaryButton:hover {{
                background-color: #1D4ED8;
            }}
            QPushButton#AccentButton {{
                background-color: #059669;
                border: 1px solid #10B981;
                color: #FFFFFF;
            }}
            QPushButton#AccentButton:hover {{
                background-color: #047857;
            }}
            QComboBox {{
                background-color: #1E293B;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px 10px;
                color: #F8FAFC;
                font-weight: 600;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: #64748B;
                background-color: #26334D;
            }}
            QComboBox:disabled {{
                background-color: #0F172A;
                border-color: #1E293B;
                color: #64748B;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #475569;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
                outline: 0px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 10px;
                color: #F8FAFC;
                background-color: #1E293B;
            }}
            QComboBox QAbstractItemView::item:selected,
            QComboBox QAbstractItemView::item:hover {{
                background-color: #2563EB;
                color: #FFFFFF;
            }}
            QMenu {{
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #475569;
                border-radius: 6px;
                font-size: 13px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 16px;
                color: #F8FAFC;
                background-color: transparent;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #2563EB;
                color: #FFFFFF;
            }}
            QMenu::separator {{
                height: 1px;
                background: #334155;
                margin: 4px 8px;
            }}
            QCheckBox {{
                color: #E2E8F0;
                font-weight: 600;
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox:disabled {{
                color: #64748B;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #64748B;
                background-color: #0F172A;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2563EB;
                border-color: #3B82F6;
            }}
            QGroupBox {{
                font-weight: bold;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #1E293B;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #F8FAFC;
            }}
            QTableWidget {{
                background-color: #1E293B;
                alternate-background-color: #26334D;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                gridline-color: #334155;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
            }}
            QTableWidget::item {{
                color: #F8FAFC;
            }}
            QHeaderView::section {{
                background-color: #0F172A;
                color: #F8FAFC;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #334155;
            }}
            QLineEdit, QKeySequenceEdit {{
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #475569;
                border-radius: 5px;
                padding: 5px 8px;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
            }}
            QSpinBox {{
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #475569;
                border-radius: 6px;
                padding-left: 8px;
                padding-right: 28px;
                padding-top: 4px;
                padding-bottom: 4px;
                font-size: 13px;
                font-weight: 600;
                min-height: 28px;
            }}
            QSpinBox:hover {{
                border-color: #60A5FA;
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 26px;
                height: 15px;
                border-left: 1px solid #475569;
                border-bottom: 1px solid #475569;
                border-top-right-radius: 5px;
                background-color: #1E293B;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 26px;
                height: 15px;
                border-left: 1px solid #475569;
                border-bottom-right-radius: 5px;
                background-color: #1E293B;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: #334155;
            }}
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: #2563EB;
            }}
            QSpinBox::up-arrow {{
                image: url({up_dark});
                width: 10px;
                height: 8px;
            }}
            QSpinBox::down-arrow {{
                image: url({down_dark});
                width: 10px;
                height: 8px;
            }}
            QStatusBar {{
                background-color: #0F172A;
                color: #94A3B8;
                border-top: 1px solid #1E293B;
            }}
            QToolTip {{
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #475569;
                padding: 4px 6px;
            }}
            """
        else:
            return f"""
            QMainWindow, QDialog, QMessageBox, QInputDialog {{
                background-color: #F8FAFC;
                color: #0F172A;
            }}
            QWidget {{
                color: #0F172A;
            }}
            QLabel {{
                color: #1E293B;
                background: transparent;
            }}
            QFrame#ToolbarFrame, QFrame#FormFrame {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 6px;
            }}
            QPushButton {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 7px 14px;
                color: #1E293B;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #F1F5F9;
                border-color: #94A3B8;
            }}
            QPushButton:disabled {{
                background-color: #F1F5F9;
                border-color: #E2E8F0;
                color: #94A3B8;
            }}
            QPushButton#PrimaryButton {{
                background-color: #2563EB;
                border: 1px solid #1D4ED8;
                color: #FFFFFF;
            }}
            QPushButton#PrimaryButton:hover {{
                background-color: #1D4ED8;
            }}
            QPushButton#AccentButton {{
                background-color: #059669;
                border: 1px solid #047857;
                color: #FFFFFF;
            }}
            QPushButton#AccentButton:hover {{
                background-color: #047857;
            }}
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #1E293B;
                font-weight: 600;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: #94A3B8;
                background-color: #F8FAFC;
            }}
            QComboBox:disabled {{
                background-color: #F1F5F9;
                border-color: #E2E8F0;
                color: #94A3B8;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                selection-background-color: #DBEAFE;
                selection-color: #1E3A8A;
                outline: 0px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 10px;
                color: #0F172A;
                background-color: #FFFFFF;
            }}
            QComboBox QAbstractItemView::item:selected,
            QComboBox QAbstractItemView::item:hover {{
                background-color: #DBEAFE;
                color: #1E3A8A;
            }}
            QMenu {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                font-size: 13px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 16px;
                color: #0F172A;
                background-color: transparent;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #DBEAFE;
                color: #1E3A8A;
            }}
            QMenu::separator {{
                height: 1px;
                background: #E2E8F0;
                margin: 4px 8px;
            }}
            QCheckBox {{
                color: #1E293B;
                font-weight: 600;
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox:disabled {{
                color: #94A3B8;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #94A3B8;
                background-color: #FFFFFF;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2563EB;
                border-color: #1D4ED8;
            }}
            QGroupBox {{
                font-weight: bold;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #FFFFFF;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #0F172A;
            }}
            QTableWidget {{
                background-color: #FFFFFF;
                alternate-background-color: #F8FAFC;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                gridline-color: #E2E8F0;
                selection-background-color: #DBEAFE;
                selection-color: #1E3A8A;
            }}
            QTableWidget::item {{
                color: #0F172A;
            }}
            QHeaderView::section {{
                background-color: #1E293B;
                color: #FFFFFF;
                padding: 6px;
                font-weight: bold;
                border: none;
            }}
            QLineEdit, QKeySequenceEdit {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 5px 8px;
                selection-background-color: #DBEAFE;
                selection-color: #1E3A8A;
            }}
            QSpinBox {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding-left: 8px;
                padding-right: 28px;
                padding-top: 4px;
                padding-bottom: 4px;
                font-size: 13px;
                font-weight: 600;
                min-height: 28px;
            }}
            QSpinBox:hover {{
                border-color: #2563EB;
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 26px;
                height: 15px;
                border-left: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                border-top-right-radius: 5px;
                background-color: #F1F5F9;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 26px;
                height: 15px;
                border-left: 1px solid #CBD5E1;
                border-bottom-right-radius: 5px;
                background-color: #F1F5F9;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: #E2E8F0;
            }}
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: #CBD5E1;
            }}
            QSpinBox::up-arrow {{
                image: url({up_light});
                width: 10px;
                height: 8px;
            }}
            QSpinBox::down-arrow {{
                image: url({down_light});
                width: 10px;
                height: 8px;
            }}
            QStatusBar {{
                background-color: #F8FAFC;
                color: #475569;
                border-top: 1px solid #E2E8F0;
            }}
            QToolTip {{
                background-color: #1E293B;
                color: #FFFFFF;
                border: 1px solid #334155;
                padding: 4px 6px;
            }}
            """

