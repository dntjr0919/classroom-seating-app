"""
사용자 정의 단축키 설정 대화상자 및 단축키 관리 모듈 (shortcut_dialog.py)
PyQt6의 QKeySequenceEdit을 활용하여 기능별 단축키를 확인, 변경, 초기화하고
QSettings를 통해 애플리케이션 재실행 후에도 영구 유지합니다.
"""

from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme_manager import ThemeManager

# 단축키 기능 키 상수
ACTION_RUN_PLACEMENT = "run_placement"
ACTION_ROSTER_MGMT = "roster_mgmt"
ACTION_LAYOUT_MGMT = "layout_mgmt"
ACTION_CLEAR_ASSIGNMENT = "clear_assignment"
ACTION_OPEN_EXPORT_MENU = "open_export_menu"
ACTION_EXPORT_PRINT_PDF = "export_print_pdf"
ACTION_SAVE_EXCEL = "save_excel"
ACTION_LOAD_EXCEL = "load_excel"
ACTION_SHORTCUT_SETTINGS = "shortcut_settings"

# 기본 단축키 및 설명 정의 (순서 보장)
DEFAULT_SHORTCUTS: Dict[str, tuple[str, str]] = {
    ACTION_RUN_PLACEMENT: ("자리 배치 실행", "F5"),
    ACTION_ROSTER_MGMT: ("학생 명단 관리", "Ctrl+R"),
    ACTION_LAYOUT_MGMT: ("책상 레이아웃 설정", "Ctrl+L"),
    ACTION_CLEAR_ASSIGNMENT: ("배정 초기화", "Ctrl+Backspace"),
    ACTION_OPEN_EXPORT_MENU: ("내보내기 메뉴 열기", "Ctrl+E"),
    ACTION_EXPORT_PRINT_PDF: ("인쇄 또는 PDF 문서 내보내기", "Ctrl+P"),
    ACTION_SAVE_EXCEL: ("자리 배치 엑셀 저장", "Ctrl+S"),
    ACTION_LOAD_EXCEL: ("자리 배치 엑셀 불러오기", "Ctrl+O"),
    ACTION_SHORTCUT_SETTINGS: ("단축키 설정", "Ctrl+K"),
}

SETTINGS_ORG = "ClassroomSeatingApp"
SETTINGS_APP = "ShortcutSettings"


class ShortcutManager:
    """단축키 설정 영구 저장(QSettings) 및 조회를 관리하는 헬퍼 클래스"""

    @classmethod
    def get_defaults(cls) -> Dict[str, str]:
        """기본 단축키 매핑 (action_id -> key_sequence_string) 반환"""
        return {action_id: default_seq for action_id, (_, default_seq) in DEFAULT_SHORTCUTS.items()}

    @classmethod
    def load_shortcuts(cls) -> Dict[str, str]:
        """
        QSettings에서 저장된 단축키 설정을 불러옵니다.
        저장된 값이 없으면 기본값을 반환합니다.
        """
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        shortcuts = {}
        defaults = cls.get_defaults()
        for action_id, default_seq in defaults.items():
            val = settings.value(f"shortcuts/{action_id}", default_seq, type=str)
            shortcuts[action_id] = str(val).strip()
        return shortcuts

    @classmethod
    def save_shortcuts(cls, shortcuts: Dict[str, str]) -> None:
        """단축키 설정을 QSettings에 영구 저장합니다."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        for action_id, seq in shortcuts.items():
            settings.setValue(f"shortcuts/{action_id}", seq.strip())
        settings.sync()

    @classmethod
    def reset_to_defaults(cls) -> Dict[str, str]:
        """저장된 단축키 설정을 모두 지우고 기본값으로 복원합니다."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        settings.remove("shortcuts")
        settings.sync()
        return cls.get_defaults()


class ShortcutSettingsDialog(QDialog):
    """사용자 정의 단축키 확인, 편집, 중복 검증 및 초기화 대화상자"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("단축키 설정 (Keyboard Shortcuts)")
        self.setMinimumWidth(480)
        self.resize(520, 480)
        self.setModal(True)

        self.editors: Dict[str, QKeySequenceEdit] = {}
        self.current_shortcuts = ShortcutManager.load_shortcuts()

        self._init_ui()

    def _init_ui(self) -> None:
        is_dark = ThemeManager.is_dark()
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        # 안내 상자
        info_label = QLabel(
            "각 기능의 단축키를 클릭하고 원하는 키 조합을 입력하세요.\n"
            "단축키를 없애려면 우측 '지우기' 버튼을 클릭하세요."
        )
        info_color = "#CBD5E1" if is_dark else "#475569"
        info_label.setStyleSheet(f"color: {info_color}; font-size: 12px; margin-bottom: 4px;")
        root_layout.addWidget(info_label)

        # 단축키 폼 영역
        form_frame = QFrame()
        form_frame.setObjectName("FormFrame")
        form_layout = QFormLayout(form_frame)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setSpacing(10)

        lbl_color = "#F8FAFC" if is_dark else "#1E293B"
        for action_id, (label_text, _) in DEFAULT_SHORTCUTS.items():
            current_seq_str = self.current_shortcuts.get(action_id, "")

            seq_edit = QKeySequenceEdit(QKeySequence(current_seq_str))
            seq_edit.setMinimumWidth(160)
            self.editors[action_id] = seq_edit

            btn_clear = QPushButton("🧹")
            btn_clear.setToolTip("단축키를 미지정(해제)합니다.")
            btn_clear.setFixedWidth(38)
            btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_clear.setStyleSheet("font-size: 14px; padding: 2px 0;")
            btn_clear.clicked.connect(lambda _, edit=seq_edit: edit.clear())

            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            row_layout.addWidget(seq_edit, stretch=1)
            row_layout.addWidget(btn_clear)

            row_container = QWidget()
            row_container.setLayout(row_layout)

            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-weight: 600; color: {lbl_color};")
            form_layout.addRow(lbl, row_container)

        root_layout.addWidget(form_frame)

        # 하단 버튼 영역 (기본값 복원 | 취소, 저장)
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("기본값 복원")
        btn_reset.setToolTip("모든 단축키를 최초 기본값으로 복원합니다.")
        btn_reset.clicked.connect(self._reset_to_defaults)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch(1)

        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("저장 및 적용")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._validate_and_save)
        btn_layout.addWidget(btn_save)

        root_layout.addLayout(btn_layout)

    def _reset_to_defaults(self) -> None:
        """에디터 위젯들의 값을 모두 기본값으로 채웁니다 (아직 저장은 안 됨)."""
        reply = QMessageBox.question(
            self,
            "기본값 복원 확인",
            "모든 단축키를 초기 기본값으로 복원하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            defaults = ShortcutManager.get_defaults()
            for action_id, seq_str in defaults.items():
                if action_id in self.editors:
                    self.editors[action_id].setKeySequence(QKeySequence(seq_str))

    def _validate_and_save(self) -> None:
        """중복된 단축키가 있는지 검증하고, 문제가 없으면 저장하고 닫습니다."""
        new_shortcuts: Dict[str, str] = {}
        used_sequences: Dict[str, str] = {}  # seq_str -> action_name

        for action_id, edit in self.editors.items():
            seq: QKeySequence = edit.keySequence()
            seq_str = seq.toString(QKeySequence.SequenceFormat.NativeText).strip()
            action_name = DEFAULT_SHORTCUTS[action_id][0]

            if seq_str:
                if seq_str in used_sequences:
                    dup_action = used_sequences[seq_str]
                    QMessageBox.warning(
                        self,
                        "단축키 중복 오류",
                        f"단축키 '{seq_str}'(이)가 이미 다음 두 기능에 중복 지정되었습니다:\n\n"
                        f"• {dup_action}\n"
                        f"• {action_name}\n\n"
                        f"서로 다른 단축키를 지정하거나 중복을 해제해 주세요.",
                    )
                    edit.setFocus()
                    return
                used_sequences[seq_str] = action_name

            new_shortcuts[action_id] = seq_str

        # 검증 통과: 저장
        ShortcutManager.save_shortcuts(new_shortcuts)
        self.accept()
