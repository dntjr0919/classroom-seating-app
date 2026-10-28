"""
교실 자리 배치 프로그램 - 교사용 히든 관리자 대화상자 (views/hidden_admin_dialog.py)
학생들에게 노출되지 않는 비공개 관리 창으로, 다음 3개 탭으로 구성됩니다:
1. [단축키 & 보안 설정]: 히든 메뉴 단축키, 1회성 강제배치 트리거 단축키, 4자리 마스터 PIN 변경
2. [강제 배치 프리셋 설정]: 현재 교실 격자 기반 미니 그리드에서 특정 좌석에 학생 사전 매핑,
   드래그 앤 드롭 자리 이동/맞바꾸기, 현재 메인 자리 배치 원클릭 불러오기 및 1회 강제 적용 플래그 제어
3. [근거리 배치 제외 목록]: 상하/좌우/대각선 1칸 이내(체비쇼프 거리 <= 1) 인접 배치 금지 학생 쌍 등록/삭제
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QMimeData, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QDrag, QKeySequence, QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models import CellState, ClassroomGrid, Student
from services.secret_config_service import (
    DEFAULT_FORCE_SHORTCUT,
    DEFAULT_MENU_SHORTCUT,
    SecretConfigService,
    format_coord_key,
    parse_coord_key,
)
from .theme_manager import ThemeManager

MIME_PRESET_SEAT_COORD = "application/x-preset-seat-coord"


class MiniPresetSeatButton(QPushButton):
    """
    강제 배치 프리셋 미니 그리드의 개별 좌석 버튼 위젯.
    - 활성 책상 클릭 시: 사전 배정할 학생 선택 팝업 호출
    - 우클릭 시: 학생 지정 또는 해당 좌석 프리셋 비우기 컨텍스트 메뉴 호출
    - 드래그 앤 드롭 시: 다른 활성 좌석으로 학생 이동(Move) 또는 맞바꾸기(Swap) 수행
    """

    seat_clicked = pyqtSignal(int, int)                        # (row, col)
    seat_swap_requested = pyqtSignal(int, int, int, int)       # (from_r, from_c, to_r, to_c)
    seat_clear_requested = pyqtSignal(int, int)                # (row, col)

    def __init__(
        self,
        row: int,
        col: int,
        state: CellState,
        assigned_student: Optional[Student] = None,
        is_orphan_id: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.row = row
        self.col = col
        self.state = state
        self.assigned_student = assigned_student
        self.orphan_id = is_orphan_id
        self._drag_start_pos: Optional[QPoint] = None
        self._is_drag_over: bool = False

        self.setMinimumSize(92, 58)
        if self.state == CellState.ACTIVE:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setAcceptDrops(True)
        else:
            self.setEnabled(False)
            self.setAcceptDrops(False)

        self.refresh_appearance()

    def set_preset_student(
        self,
        student: Optional[Student],
        orphan_id: Optional[str] = None,
    ) -> None:
        self.assigned_student = student
        self.orphan_id = orphan_id
        self.refresh_appearance()

    def refresh_appearance(self) -> None:
        coord_text = f"{self.row + 1}행 {self.col + 1}열"
        is_dark = ThemeManager.is_dark()

        if self.state == CellState.AISLE:
            self.setText(f"{coord_text}\n[통로]")
            if is_dark:
                self.setStyleSheet(
                    "QPushButton { background-color: #0F172A; border: 1px dashed #334155; "
                    "border-radius: 6px; color: #475569; font-size: 10px; }"
                )
            else:
                self.setStyleSheet(
                    "QPushButton { background-color: #F8FAFC; border: 1px dashed #CBD5E1; "
                    "border-radius: 6px; color: #94A3B8; font-size: 10px; }"
                )
            return

        if self.state == CellState.DISABLED:
            self.setText(f"{coord_text}\n[비활성]")
            if is_dark:
                self.setStyleSheet(
                    "QPushButton { background-color: #1E293B; border: 1px solid #334155; "
                    "border-radius: 6px; color: #475569; font-size: 10px; }"
                )
            else:
                self.setStyleSheet(
                    "QPushButton { background-color: #E2E8F0; border: 1px solid #CBD5E1; "
                    "border-radius: 6px; color: #94A3B8; font-size: 10px; }"
                )
            return

        # 드래그 오버(드롭 타깃 하이라이트) 상태 스타일
        if self._is_drag_over:
            if self.assigned_student is not None:
                self.setText(f"🔄 {coord_text}\n{self.assigned_student.display_label()}")
            elif self.orphan_id:
                self.setText(f"🔄 {coord_text}\n(미등록: {self.orphan_id})")
            else:
                self.setText(f"📥 {coord_text}\n(여기로 이동)")

            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #064E3B;
                        border: 2px dashed #34D399;
                        border-radius: 6px;
                        color: #ECFDF5;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #D1FAE5;
                        border: 2px dashed #059669;
                        border-radius: 6px;
                        color: #065F46;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px;
                    }
                    """
                )
            return

        # 일반 활성 책상 (CellState.ACTIVE)
        if self.assigned_student is not None:
            self.setText(f"🎯 {coord_text}\n{self.assigned_student.display_label()}")
            self.setToolTip(
                f"{coord_text}: {self.assigned_student.display_label()}\n"
                "• 클릭: 다른 학생으로 변경 또는 해제\n"
                "• 드래그: 다른 좌석으로 이동 또는 맞바꾸기\n"
                "• 우클릭: 빠른 메뉴"
            )
            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #3B0764;
                        border: 2px solid #A855F7;
                        border-radius: 6px;
                        color: #FAF5FF;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px;
                    }
                    QPushButton:hover {
                        background-color: #581C87;
                        border-color: #C084FC;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #F3E8FF;
                        border: 2px solid #9333EA;
                        border-radius: 6px;
                        color: #581C87;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px;
                    }
                    QPushButton:hover {
                        background-color: #E9D5FF;
                        border-color: #7E22CE;
                    }
                    """
                )
        elif self.orphan_id:
            self.setText(f"⚠ {coord_text}\n(미등록: {self.orphan_id})")
            self.setToolTip(f"{coord_text}: 현재 학생 명단에 없는 ID({self.orphan_id})")
            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #451A03;
                        border: 1px solid #F59E0B;
                        border-radius: 6px;
                        color: #FDE68A;
                        font-size: 10px;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #FEF3C7;
                        border: 1px solid #D97706;
                        border-radius: 6px;
                        color: #92400E;
                        font-size: 10px;
                    }
                    """
                )
        else:
            self.setText(f"{coord_text}\n(미지정)")
            self.setToolTip(
                f"{coord_text} (비어 있음)\n"
                "• 클릭하여 이 좌석에 사전 배정할 학생을 선택하거나,\n"
                "• 다른 좌석의 학생을 이 좌석으로 드래그하세요."
            )
            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #1E293B;
                        border: 1px solid #475569;
                        border-radius: 6px;
                        color: #CBD5E1;
                        font-size: 11px;
                        padding: 4px;
                    }
                    QPushButton:hover {
                        background-color: #334155;
                        border-color: #60A5FA;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #FFFFFF;
                        border: 1px solid #CBD5E1;
                        border-radius: 6px;
                        color: #334155;
                        font-size: 11px;
                        padding: 4px;
                    }
                    QPushButton:hover {
                        background-color: #EFF6FF;
                        border-color: #2563EB;
                    }
                    """
                )

    # ------------------------------------------------------------------
    # 마우스 클릭 / 우클릭 메뉴 / 드래그 앤 드롭 이벤트 핸들러
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        if event is None or self.state != CellState.ACTIVE:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        if (
            event is None
            or self.state != CellState.ACTIVE
            or self._drag_start_pos is None
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            return

        # 학생이 배정된 좌석(또는 미등록 ID가 있는 좌석)만 드래그 시작 가능
        if self.assigned_student is None and not self.orphan_id:
            return

        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        self._drag_start_pos = None
        self.setDown(False)

        drag = QDrag(self)
        mime_data = QMimeData()
        coord_bytes = f"{self.row},{self.col}".encode("utf-8")
        mime_data.setData(MIME_PRESET_SEAT_COORD, coord_bytes)
        drag.setMimeData(mime_data)

        pixmap: QPixmap = self.grab()
        drag.setPixmap(pixmap.scaled(104, 64, Qt.AspectRatioMode.KeepAspectRatio))
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        if event is not None and self.state == CellState.ACTIVE:
            if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos is not None:
                self._drag_start_pos = None
                self.setDown(False)
                if self.rect().contains(event.pos()):
                    self.seat_clicked.emit(self.row, self.col)
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        if event is None or self.state != CellState.ACTIVE:
            return
        menu = QMenu(self)
        act_select = QAction("👤 이 좌석에 프리셋 학생 지정/변경...", self)
        act_select.triggered.connect(lambda: self.seat_clicked.emit(self.row, self.col))
        menu.addAction(act_select)

        if self.assigned_student is not None or self.orphan_id:
            menu.addSeparator()
            act_clear = QAction("🗑 이 좌석 프리셋 비우기", self)
            act_clear.triggered.connect(lambda: self.seat_clear_requested.emit(self.row, self.col))
            menu.addAction(act_clear)

        menu.exec(event.globalPos())

    def dragEnterEvent(self, event) -> None:
        if (
            event is not None
            and self.state == CellState.ACTIVE
            and event.mimeData() is not None
            and event.mimeData().hasFormat(MIME_PRESET_SEAT_COORD)
        ):
            raw = bytes(event.mimeData().data(MIME_PRESET_SEAT_COORD)).decode("utf-8")
            try:
                from_r, from_c = [int(x) for x in raw.split(",")]
                if (from_r, from_c) != (self.row, self.col):
                    self._is_drag_over = True
                    self.refresh_appearance()
            except ValueError:
                pass
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        if self._is_drag_over:
            self._is_drag_over = False
            self.refresh_appearance()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        if self._is_drag_over:
            self._is_drag_over = False
            self.refresh_appearance()

        if (
            event is None
            or self.state != CellState.ACTIVE
            or event.mimeData() is None
            or not event.mimeData().hasFormat(MIME_PRESET_SEAT_COORD)
        ):
            return

        raw = bytes(event.mimeData().data(MIME_PRESET_SEAT_COORD)).decode("utf-8")
        try:
            from_r, from_c = [int(x) for x in raw.split(",")]
            to_r, to_c = self.row, self.col
            event.acceptProposedAction()
            if (from_r, from_c) != (to_r, to_c):
                QTimer.singleShot(
                    0, lambda: self.seat_swap_requested.emit(from_r, from_c, to_r, to_c)
                )
        except ValueError:
            return


class HiddenAdminDialog(QDialog):
    """
    교사용 비공개 히든 관리자 설정 대화상자.
    """

    def __init__(
        self,
        secret_service: SecretConfigService,
        grid: ClassroomGrid,
        roster: List[Student],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔒 교사용 히든 관리자 설정 (Hidden Admin Menu)")
        self.resize(860, 650)
        self.setModal(True)

        self.secret_service = secret_service
        self.secret_service.load()
        self.grid = grid
        self.roster = list(roster)
        self.roster_by_id: Dict[str, Student] = {s.student_id: s for s in self.roster}
        self.sorted_roster: List[Student] = sorted(self.roster, key=lambda s: s.sort_key())

        # 대화상자 내 작업 사본 데이터
        self._working_pin: str = self.secret_service.get_pin()
        self._working_preset_map: Dict[str, str] = dict(self.secret_service.get_preset_map())
        self._working_forbidden_pairs: List[Tuple[str, str]] = list(
            self.secret_service.get_forbidden_pairs()
        )
        self._mini_buttons: Dict[Tuple[int, int], MiniPresetSeatButton] = {}

        self._init_ui()
        self._refresh_preset_grid()
        self._refresh_forbidden_table()

    def _init_ui(self) -> None:
        is_dark = ThemeManager.is_dark()
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        # 상단 보안 안내 배너
        banner = QFrame()
        if is_dark:
            banner.setStyleSheet(
                "background-color: #1E1B4B; border: 1px solid #6366F1; border-radius: 8px; padding: 6px;"
            )
            banner_text_color = "#E0E7FF"
        else:
            banner.setStyleSheet(
                "background-color: #EEF2FF; border: 1px solid #6366F1; border-radius: 8px; padding: 6px;"
            )
            banner_text_color = "#1E1B4B"

        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(10, 4, 10, 4)
        lbl_banner = QLabel(
            "🕵️ <b>교사용 비공개 제어 메뉴</b> — 이곳에서 설정한 강제 프리셋과 근거리 제외 조건은 "
            "일반 화면이나 고정석(📌) 표시로 전혀 노출되지 않습니다."
        )
        lbl_banner.setStyleSheet(f"color: {banner_text_color}; font-size: 12px;")
        banner_layout.addWidget(lbl_banner)
        root_layout.addWidget(banner)

        # 메인 탭 위젯 (3개 탭)
        self.tabs = QTabWidget()
        self.tab_security = QWidget()
        self.tab_preset = QWidget()
        self.tab_forbidden = QWidget()

        self.tabs.addTab(self.tab_security, "🔑 1. 단축키 & 보안 설정")
        self.tabs.addTab(self.tab_preset, "🎯 2. 강제 배치 프리셋 설정")
        self.tabs.addTab(self.tab_forbidden, "🚫 3. 근거리 배치 제외 목록")

        self._init_tab_security()
        self._init_tab_preset()
        self._init_tab_forbidden()

        root_layout.addWidget(self.tabs, stretch=1)

        # 하단 취소 / 저장 버튼
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)

        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)

        btn_save = QPushButton("💾 설정 저장 및 닫기")
        btn_save.setObjectName("PrimaryButton")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save_all)
        bottom_layout.addWidget(btn_save)

        root_layout.addLayout(bottom_layout)

    # ------------------------------------------------------------------
    # 탭 1: 단축키 & 보안 설정
    # ------------------------------------------------------------------
    def _init_tab_security(self) -> None:
        is_dark = ThemeManager.is_dark()
        layout = QVBoxLayout(self.tab_security)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        sub_color = "#94A3B8" if is_dark else "#475569"

        # 1. 비공개 단축키 설정 그룹
        grp_shortcuts = QGroupBox("비공개 단축키 설정 (QKeySequenceEdit)")
        sc_layout = QVBoxLayout(grp_shortcuts)
        sc_layout.setSpacing(10)

        lbl_sc_desc = QLabel(
            "• <b>히든 메뉴 열기 단축키</b>: 누르면 PIN 입력창이 열리고 이 관리 메뉴로 진입합니다.\n"
            "• <b>1회성 강제 배치 트리거 단축키</b>: 누르면 화면에 아무런 표시 없이 '다음 1회 강제 배치'를 무음으로 켜거나 끕니다."
        )
        lbl_sc_desc.setStyleSheet(f"color: {sub_color}; font-size: 12px;")
        sc_layout.addWidget(lbl_sc_desc)

        form_sc = QFormLayout()
        form_sc.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_sc.setSpacing(12)

        # 히든 메뉴 열기 단축키
        self.edit_menu_shortcut = QKeySequenceEdit(
            QKeySequence(self.secret_service.get_menu_shortcut())
        )
        self.edit_menu_shortcut.setMinimumWidth(200)
        btn_reset_menu_sc = QPushButton("기본값 (Ctrl+Shift+H)")
        btn_reset_menu_sc.clicked.connect(
            lambda: self.edit_menu_shortcut.setKeySequence(QKeySequence(DEFAULT_MENU_SHORTCUT))
        )
        row_menu_sc = QHBoxLayout()
        row_menu_sc.setContentsMargins(0, 0, 0, 0)
        row_menu_sc.addWidget(self.edit_menu_shortcut, stretch=1)
        row_menu_sc.addWidget(btn_reset_menu_sc)
        w_menu_sc = QWidget()
        w_menu_sc.setLayout(row_menu_sc)
        form_sc.addRow(QLabel("<b>히든 메뉴 열기 단축키:</b>"), w_menu_sc)

        # 1회성 강제배치 트리거 단축키
        self.edit_force_shortcut = QKeySequenceEdit(
            QKeySequence(self.secret_service.get_force_shortcut())
        )
        self.edit_force_shortcut.setMinimumWidth(200)
        btn_reset_force_sc = QPushButton("기본값 (Ctrl+Shift+F)")
        btn_reset_force_sc.clicked.connect(
            lambda: self.edit_force_shortcut.setKeySequence(QKeySequence(DEFAULT_FORCE_SHORTCUT))
        )
        row_force_sc = QHBoxLayout()
        row_force_sc.setContentsMargins(0, 0, 0, 0)
        row_force_sc.addWidget(self.edit_force_shortcut, stretch=1)
        row_force_sc.addWidget(btn_reset_force_sc)
        w_force_sc = QWidget()
        w_force_sc.setLayout(row_force_sc)
        form_sc.addRow(QLabel("<b>1회성 강제배치 트리거 단축키:</b>"), w_force_sc)

        sc_layout.addLayout(form_sc)
        layout.addWidget(grp_shortcuts)

        # 2. 4자리 마스터 PIN 번호 변경 그룹
        grp_pin = QGroupBox("보안 마스터 PIN 번호 변경 (4자리 숫자)")
        pin_layout = QVBoxLayout(grp_pin)
        pin_layout.setSpacing(10)

        lbl_pin_desc = QLabel(
            "히든 메뉴 진입 시 요구되는 4자리 숫자 PIN 번호를 변경합니다 (초기 기본값: 0000).\n"
            "변경하지 않으려면 아래 입력란을 비워 두세요."
        )
        lbl_pin_desc.setStyleSheet(f"color: {sub_color}; font-size: 12px;")
        pin_layout.addWidget(lbl_pin_desc)

        form_pin = QFormLayout()
        form_pin.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_pin.setSpacing(10)

        self.edit_new_pin = QLineEdit()
        self.edit_new_pin.setMaxLength(4)
        self.edit_new_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_new_pin.setPlaceholderText("새 4자리 숫자 PIN 입력 (예: 1234)")

        self.edit_confirm_pin = QLineEdit()
        self.edit_confirm_pin.setMaxLength(4)
        self.edit_confirm_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_confirm_pin.setPlaceholderText("새 4자리 숫자 PIN 다시 입력")

        btn_apply_pin = QPushButton("🔑 PIN 즉시 변경")
        btn_apply_pin.clicked.connect(self._on_change_pin_clicked)

        pin_btn_row = QHBoxLayout()
        pin_btn_row.setContentsMargins(0, 0, 0, 0)
        pin_btn_row.addWidget(self.edit_confirm_pin, stretch=1)
        pin_btn_row.addWidget(btn_apply_pin)
        w_pin_confirm = QWidget()
        w_pin_confirm.setLayout(pin_btn_row)

        form_pin.addRow(QLabel("<b>새 PIN 번호 (4자리):</b>"), self.edit_new_pin)
        form_pin.addRow(QLabel("<b>새 PIN 번호 확인:</b>"), w_pin_confirm)

        pin_layout.addLayout(form_pin)
        layout.addWidget(grp_pin)
        layout.addStretch(1)

    def _on_change_pin_clicked(self) -> None:
        """[PIN 즉시 변경] 버튼 클릭 시 4자리 숫자 유효성을 검사하고 반영합니다."""
        new_pin = self.edit_new_pin.text().strip()
        confirm_pin = self.edit_confirm_pin.text().strip()

        if len(new_pin) != 4 or not new_pin.isdigit():
            QMessageBox.warning(
                self,
                "PIN 형식 오류",
                "마스터 PIN 번호는 반드시 4자리 숫자(예: 0000 ~ 9999)여야 합니다.",
            )
            self.edit_new_pin.setFocus()
            return

        if new_pin != confirm_pin:
            QMessageBox.warning(
                self,
                "PIN 불일치",
                "새 PIN 번호와 확인 입력값이 일치하지 않습니다.",
            )
            self.edit_confirm_pin.setFocus()
            return

        self._working_pin = new_pin
        self.secret_service.set_pin(new_pin)
        self.edit_new_pin.clear()
        self.edit_confirm_pin.clear()
        QMessageBox.information(
            self,
            "PIN 변경 완료",
            "마스터 PIN 번호가 성공적으로 변경되었습니다.",
        )

    # ------------------------------------------------------------------
    # 탭 2: 강제 배치 프리셋 설정
    # ------------------------------------------------------------------
    def _init_tab_preset(self) -> None:
        is_dark = ThemeManager.is_dark()
        layout = QVBoxLayout(self.tab_preset)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 상단 컨트롤 바: 1회 강제 적용 체크박스 + 요약 표시
        top_bar = QHBoxLayout()
        self.chk_force_next = QCheckBox("✅ 다음 1회 배치 시 강제 적용 (단축키로도 무음 토글 가능)")
        self.chk_force_next.setChecked(self.secret_service.is_force_next_assignment())
        if is_dark:
            self.chk_force_next.setStyleSheet(
                "QCheckBox { font-size: 13px; font-weight: bold; color: #C084FC; }"
            )
        else:
            self.chk_force_next.setStyleSheet(
                "QCheckBox { font-size: 13px; font-weight: bold; color: #7E22CE; }"
            )
        top_bar.addWidget(self.chk_force_next)
        top_bar.addStretch(1)

        self.lbl_preset_summary = QLabel("")
        self.lbl_preset_summary.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_bar.addWidget(self.lbl_preset_summary)
        layout.addLayout(top_bar)

        guide_color = "#94A3B8" if is_dark else "#475569"
        lbl_guide = QLabel(
            "💡 <b>클릭:</b> 좌석에 학생 직접 배정 | <b>드래그 앤 드롭:</b> 좌석 간 학생 이동·맞바꾸기 | "
            "<b>우클릭:</b> 개별 비우기 (1회 배치 완료 후 체크박스는 자동 해제됨)"
        )
        lbl_guide.setStyleSheet(f"color: {guide_color}; font-size: 12px;")
        layout.addWidget(lbl_guide)

        # 교탁 배너
        podium = QFrame()
        podium.setStyleSheet(
            "background-color: #334155; color: #FFFFFF; border-radius: 6px; padding: 4px;"
        )
        podium_layout = QHBoxLayout(podium)
        podium_layout.setContentsMargins(8, 2, 8, 2)
        lbl_podium = QLabel("칠 판 / 교 탁 (교실 앞쪽)")
        lbl_podium.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_podium.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 12px;")
        podium_layout.addWidget(lbl_podium)
        layout.addWidget(podium)

        # 미니 그리드 스크롤 영역
        self.preset_scroll = QScrollArea()
        self.preset_scroll.setWidgetResizable(True)
        board_bg = "#0B1120" if is_dark else "#F1F5F9"
        board_bd = "#334155" if is_dark else "#CBD5E1"
        self.preset_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {board_bg}; border: 1px solid {board_bd}; border-radius: 8px; }}"
        )

        self.preset_grid_container = QWidget()
        self.preset_grid_container.setStyleSheet(f"background-color: {board_bg};")
        self.preset_grid_layout = QGridLayout(self.preset_grid_container)
        self.preset_grid_layout.setSpacing(6)
        self.preset_scroll.setWidget(self.preset_grid_container)
        layout.addWidget(self.preset_scroll, stretch=1)

        # 하단 액션 바: 좌측 하단 [현재 자리 배치 불러오기] 버튼 + 우측 하단 [프리셋 전체 해제] 버튼
        preset_bottom_bar = QHBoxLayout()
        self.btn_load_current_seating = QPushButton("📥 현재 자리 배치 불러오기")
        self.btn_load_current_seating.setObjectName("AccentButton")
        self.btn_load_current_seating.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_current_seating.setToolTip(
            "현재 메인 화면에 배치되어 있는 학생들의 좌석 위치를 그대로 읽어와 강제 배치 프리셋으로 일괄 복사합니다."
        )
        self.btn_load_current_seating.clicked.connect(self._on_load_current_seating_to_preset)
        preset_bottom_bar.addWidget(self.btn_load_current_seating)

        preset_bottom_bar.addStretch(1)

        self.btn_clear_presets = QPushButton("🧹 프리셋 전체 해제")
        self.btn_clear_presets.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_presets.setToolTip("사전 매핑된 모든 강제 배치 좌석을 초기화합니다.")
        self.btn_clear_presets.clicked.connect(self._on_clear_all_presets)
        preset_bottom_bar.addWidget(self.btn_clear_presets)

        layout.addLayout(preset_bottom_bar)

    def _refresh_preset_grid(self) -> None:
        """현재 교실 격자(행/열)와 _working_preset_map을 기준으로 미니 그리드를 갱신합니다."""
        while self.preset_grid_layout.count():
            item = self.preset_grid_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

        self._mini_buttons.clear()

        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                seat = self.grid.get_seat(r, c)
                key = format_coord_key(r, c)
                st_id = self._working_preset_map.get(key)
                assigned_st = self.roster_by_id.get(st_id) if st_id else None
                orphan = st_id if (st_id and assigned_st is None) else None

                btn = MiniPresetSeatButton(
                    row=r,
                    col=c,
                    state=seat.state,
                    assigned_student=assigned_st,
                    is_orphan_id=orphan,
                    parent=self.preset_grid_container,
                )
                if seat.is_active_desk:
                    btn.seat_clicked.connect(self._on_mini_seat_clicked)
                    btn.seat_swap_requested.connect(self._on_swap_or_move_preset_seats)
                    btn.seat_clear_requested.connect(self._on_clear_single_preset_seat)

                self.preset_grid_layout.addWidget(btn, r, c)
                self._mini_buttons[(r, c)] = btn

        self._update_preset_summary()

    def _refresh_single_mini_button(self, row: int, col: int) -> None:
        """특정 (row, col) 미니 그리드 버튼의 표시 상태를 _working_preset_map 기준으로 갱신합니다."""
        btn = self._mini_buttons.get((row, col))
        if btn is None or btn.state != CellState.ACTIVE:
            return
        key = format_coord_key(row, col)
        st_id = self._working_preset_map.get(key)
        assigned_st = self.roster_by_id.get(st_id) if st_id else None
        orphan = st_id if (st_id and assigned_st is None) else None
        btn.set_preset_student(assigned_st, orphan_id=orphan)

    def _update_preset_summary(self) -> None:
        valid_count = 0
        for raw_key, st_id in self._working_preset_map.items():
            coord = parse_coord_key(raw_key)
            if (
                coord is not None
                and 0 <= coord[0] < self.grid.rows
                and 0 <= coord[1] < self.grid.cols
                and self.grid.get_seat(coord[0], coord[1]).is_active_desk
                and st_id in self.roster_by_id
            ):
                valid_count += 1
        self.lbl_preset_summary.setText(f"사전 지정 좌석: {valid_count}석")

    def _on_load_current_seating_to_preset(self) -> None:
        """
        메인 화면(self.grid)의 활성 책상에 현재 배치되어 있는 학생들의 위치(행, 열)를 그대로 읽어와
        미니 그리드의 강제 배치 프리셋 상태(_working_preset_map)로 일괄 복사·동기화합니다.
        """
        assigned_seats = [
            seat
            for seat in self.grid.active_desks()
            if seat.student is not None
        ]
        if not assigned_seats:
            QMessageBox.information(
                self,
                "현재 배치된 학생 없음",
                "현재 메인 화면에 배치된 학생이 없습니다.\n"
                "먼저 메인 화면에서 자리를 배치한 뒤 불러오거나, 미니 그리드에서 직접 좌석을 클릭해 지정해 주세요.",
            )
            return

        new_map: Dict[str, str] = {}
        seen_students: set[str] = set()
        for seat in assigned_seats:
            assert seat.student is not None
            st_id = seat.student.student_id
            if st_id not in seen_students:
                seen_students.add(st_id)
                new_map[format_coord_key(seat.row, seat.col)] = st_id

        self._working_preset_map = new_map
        for r, c in self._mini_buttons:
            self._refresh_single_mini_button(r, c)
        self._update_preset_summary()

    def _on_swap_or_move_preset_seats(
        self,
        from_r: int,
        from_c: int,
        to_r: int,
        to_c: int,
    ) -> None:
        """
        프리셋 미니 그리드 내 두 활성 좌석 간 드래그 앤 드롭 시
        학생 이동(빈 좌석으로 드래그) 또는 맞바꾸기(학생이 있는 좌석으로 드래그)를 수행합니다.
        """
        if (from_r, from_c) == (to_r, to_c):
            return
        if (from_r, from_c) not in self._mini_buttons or (to_r, to_c) not in self._mini_buttons:
            return
        if (
            self._mini_buttons[(from_r, from_c)].state != CellState.ACTIVE
            or self._mini_buttons[(to_r, to_c)].state != CellState.ACTIVE
        ):
            return

        from_key = format_coord_key(from_r, from_c)
        to_key = format_coord_key(to_r, to_c)

        st_from = self._working_preset_map.get(from_key)
        st_to = self._working_preset_map.get(to_key)

        if st_from is None and st_to is None:
            return

        if st_from is not None and st_to is None:
            # 빈 좌석으로 이동
            self._working_preset_map.pop(from_key, None)
            self._working_preset_map[to_key] = st_from
        elif st_from is not None and st_to is not None:
            # 두 좌석의 학생 맞바꾸기(Swap)
            self._working_preset_map[from_key] = st_to
            self._working_preset_map[to_key] = st_from
        elif st_from is None and st_to is not None:
            # 역방향 이동
            self._working_preset_map.pop(to_key, None)
            self._working_preset_map[from_key] = st_to

        self._refresh_single_mini_button(from_r, from_c)
        self._refresh_single_mini_button(to_r, to_c)
        self._update_preset_summary()

    def _on_clear_single_preset_seat(self, row: int, col: int) -> None:
        """우클릭 메뉴에서 특정 좌석의 프리셋 배정을 해제합니다."""
        coord_key = format_coord_key(row, col)
        if coord_key in self._working_preset_map:
            self._working_preset_map.pop(coord_key, None)
            self._refresh_single_mini_button(row, col)
            self._update_preset_summary()

    def _on_mini_seat_clicked(self, row: int, col: int) -> None:
        """미니 그리드의 특정 활성 좌석 클릭 시 학생 선택 대화상자를 엽니다."""
        if not self.sorted_roster:
            QMessageBox.information(
                self,
                "학생 명단 없음",
                "현재 등록된 학생이 없습니다. 먼저 [학생 명단 관리]에서 학생을 등록해 주세요.",
            )
            return

        coord_key = format_coord_key(row, col)
        current_st_id = self._working_preset_map.get(coord_key)

        # 다른 좌석에 이미 프리셋으로 지정된 학생 표시 안내
        coord_by_st_id: Dict[str, Tuple[int, int]] = {}
        for k, sid in self._working_preset_map.items():
            parsed = parse_coord_key(k)
            if parsed is not None:
                coord_by_st_id[sid] = parsed

        items: List[str] = ["(선택 해제 / 좌석 비우기)"]
        current_idx = 0
        for idx, st in enumerate(self.sorted_roster, start=1):
            label = st.display_label()
            if st.student_id in coord_by_st_id:
                pr, pc = coord_by_st_id[st.student_id]
                label += f"  (현재 프리셋: {pr + 1}행 {pc + 1}열)"
            items.append(label)
            if current_st_id == st.student_id:
                current_idx = idx

        choice, ok = QInputDialog.getItem(
            self,
            f"강제 배치 프리셋 지정 ({row + 1}행 {col + 1}열)",
            f"[{row + 1}행 {col + 1}열] 좌석에 강제 배정할 학생을 선택하세요:",
            items,
            current_idx,
            False,
        )
        if not ok:
            return

        if choice == items[0]:
            self._working_preset_map.pop(coord_key, None)
        else:
            chosen_idx = items.index(choice) - 1
            chosen_student = self.sorted_roster[chosen_idx]
            # 이미 다른 프리셋 좌석에 지정되어 있었다면 기존 좌석 매핑 제거
            keys_to_remove = [
                k
                for k, v in self._working_preset_map.items()
                if v == chosen_student.student_id and k != coord_key
            ]
            for k in keys_to_remove:
                self._working_preset_map.pop(k, None)
                old_coord = parse_coord_key(k)
                if old_coord:
                    self._refresh_single_mini_button(old_coord[0], old_coord[1])

            self._working_preset_map[coord_key] = chosen_student.student_id

        # 클릭한 버튼 갱신
        self._refresh_single_mini_button(row, col)
        self._update_preset_summary()

    def _on_clear_all_presets(self) -> None:
        if not self._working_preset_map:
            return
        self._working_preset_map.clear()
        for btn in self._mini_buttons.values():
            if btn.state == CellState.ACTIVE:
                btn.set_preset_student(None)
        self._update_preset_summary()

    # ------------------------------------------------------------------
    # 탭 3: 근거리 배치 제외 목록
    # ------------------------------------------------------------------
    def _init_tab_forbidden(self) -> None:
        is_dark = ThemeManager.is_dark()
        layout = QVBoxLayout(self.tab_forbidden)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        guide_color = "#94A3B8" if is_dark else "#475569"
        lbl_desc = QLabel(
            "🚫 아래 목록에 등록된 두 학생은 자리 배치 시 <b>상하·좌우·대각선 8방향 1칸 이내"
            "(체비쇼프 거리 ≤ 1)</b>에 절대 인접하지 않도록 자동 분리 배치됩니다."
        )
        lbl_desc.setStyleSheet(f"color: {guide_color}; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # 학생 2명 선택 및 추가 컨트롤 바
        add_group = QGroupBox("근거리 배치 제외 학생 쌍 추가")
        add_layout = QHBoxLayout(add_group)
        add_layout.setSpacing(8)

        add_layout.addWidget(QLabel("학생 A:"))
        self.combo_student_a = QComboBox()
        self.combo_student_a.setMinimumWidth(180)
        add_layout.addWidget(self.combo_student_a, stretch=1)

        add_layout.addWidget(QLabel("↔  학생 B:"))
        self.combo_student_b = QComboBox()
        self.combo_student_b.setMinimumWidth(180)
        add_layout.addWidget(self.combo_student_b, stretch=1)

        for st in self.sorted_roster:
            self.combo_student_a.addItem(st.display_label(), st.student_id)
            self.combo_student_b.addItem(st.display_label(), st.student_id)
        if len(self.sorted_roster) >= 2:
            self.combo_student_b.setCurrentIndex(1)

        btn_add_pair = QPushButton("➕ 제외 쌍 추가")
        btn_add_pair.setObjectName("PrimaryButton")
        btn_add_pair.clicked.connect(self._on_add_forbidden_pair)
        add_layout.addWidget(btn_add_pair)

        layout.addWidget(add_group)

        # 등록된 제외 쌍 목록 테이블
        self.table_forbidden = QTableWidget(0, 4)
        self.table_forbidden.setHorizontalHeaderLabels(
            ["학생 A", "학생 B", "거리 제약 조건", "관리"]
        )
        self.table_forbidden.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_forbidden.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table_forbidden.verticalHeader().setVisible(False)
        header = self.table_forbidden.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table_forbidden.setColumnWidth(3, 90)
        layout.addWidget(self.table_forbidden, stretch=1)

        # 하단 선택 삭제 / 전체 삭제 바
        tbl_bottom = QHBoxLayout()
        self.lbl_forbidden_count = QLabel("등록된 제외 쌍: 0건")
        self.lbl_forbidden_count.setStyleSheet("font-weight: bold; font-size: 12px;")
        tbl_bottom.addWidget(self.lbl_forbidden_count)
        tbl_bottom.addStretch(1)

        btn_remove_selected = QPushButton("선택 항목 삭제")
        btn_remove_selected.clicked.connect(self._on_remove_selected_forbidden)
        tbl_bottom.addWidget(btn_remove_selected)

        btn_clear_forbidden = QPushButton("전체 목록 비우기")
        btn_clear_forbidden.clicked.connect(self._on_clear_all_forbidden)
        tbl_bottom.addWidget(btn_clear_forbidden)

        layout.addLayout(tbl_bottom)

    def _format_student_name(self, student_id: str) -> str:
        st = self.roster_by_id.get(student_id)
        if st is not None:
            return st.display_label()
        return f"{student_id} (현재 명단 없음)"

    def _refresh_forbidden_table(self) -> None:
        self.table_forbidden.setRowCount(0)
        for row_idx, (id_a, id_b) in enumerate(self._working_forbidden_pairs):
            self.table_forbidden.insertRow(row_idx)
            self.table_forbidden.setRowHeight(row_idx, 36)

            item_a = QTableWidgetItem(self._format_student_name(id_a))
            item_a.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_b = QTableWidgetItem(self._format_student_name(id_b))
            item_b.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_rule = QTableWidgetItem("8방향 1칸 이내 인접 금지 (체비쇼프 > 1)")
            item_rule.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_forbidden.setItem(row_idx, 0, item_a)
            self.table_forbidden.setItem(row_idx, 1, item_b)
            self.table_forbidden.setItem(row_idx, 2, item_rule)

            btn_del = QPushButton("삭제")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            btn_del.clicked.connect(lambda _, idx=row_idx: self._on_delete_forbidden_row(idx))

            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(6, 2, 6, 2)
            cell_layout.addWidget(btn_del)
            self.table_forbidden.setCellWidget(row_idx, 3, cell_widget)

        self.lbl_forbidden_count.setText(
            f"등록된 제외 쌍: {len(self._working_forbidden_pairs)}건"
        )

    def _on_add_forbidden_pair(self) -> None:
        id_a = self.combo_student_a.currentData()
        id_b = self.combo_student_b.currentData()
        if not id_a or not id_b:
            QMessageBox.information(self, "학생 선택 안내", "제외할 두 학생을 선택해 주세요.")
            return
        if id_a == id_b:
            QMessageBox.warning(
                self,
                "동일 학생 선택 오류",
                "서로 다른 두 학생을 선택해 주세요.",
            )
            return

        pair_set = frozenset((id_a, id_b))
        for ex_a, ex_b in self._working_forbidden_pairs:
            if frozenset((ex_a, ex_b)) == pair_set:
                QMessageBox.information(
                    self,
                    "중복 등록 안내",
                    "이미 근거리 배치 제외 목록에 등록된 학생 쌍입니다.",
                )
                return

        self._working_forbidden_pairs.append((id_a, id_b))
        self._refresh_forbidden_table()

    def _on_delete_forbidden_row(self, row_idx: int) -> None:
        if 0 <= row_idx < len(self._working_forbidden_pairs):
            self._working_forbidden_pairs.pop(row_idx)
            self._refresh_forbidden_table()

    def _on_remove_selected_forbidden(self) -> None:
        selected_rows = sorted(
            {idx.row() for idx in self.table_forbidden.selectedIndexes()},
            reverse=True,
        )
        if not selected_rows:
            return
        for r in selected_rows:
            if 0 <= r < len(self._working_forbidden_pairs):
                self._working_forbidden_pairs.pop(r)
        self._refresh_forbidden_table()

    def _on_clear_all_forbidden(self) -> None:
        if not self._working_forbidden_pairs:
            return
        self._working_forbidden_pairs.clear()
        self._refresh_forbidden_table()

    # ------------------------------------------------------------------
    # 전체 설정 검증 및 저장
    # ------------------------------------------------------------------
    def _on_save_all(self) -> None:
        """세 탭의 모든 설정을 검증하고 SecretConfigService에 일괄 저장합니다."""
        # 1. PIN 입력란에 작성 중인 값이 있다면 검증 후 함께 반영
        new_pin = self.edit_new_pin.text().strip()
        confirm_pin = self.edit_confirm_pin.text().strip()
        if new_pin or confirm_pin:
            if len(new_pin) != 4 or not new_pin.isdigit():
                QMessageBox.warning(
                    self,
                    "PIN 형식 오류",
                    "마스터 PIN 번호는 반드시 4자리 숫자(예: 0000 ~ 9999)여야 합니다.",
                )
                self.tabs.setCurrentWidget(self.tab_security)
                self.edit_new_pin.setFocus()
                return
            if new_pin != confirm_pin:
                QMessageBox.warning(
                    self,
                    "PIN 불일치",
                    "새 PIN 번호와 확인 입력값이 일치하지 않습니다.",
                )
                self.tabs.setCurrentWidget(self.tab_security)
                self.edit_confirm_pin.setFocus()
                return
            self._working_pin = new_pin

        # 2. 단축키 검증
        menu_seq = (
            self.edit_menu_shortcut.keySequence()
            .toString(QKeySequence.SequenceFormat.NativeText)
            .strip()
        )
        force_seq = (
            self.edit_force_shortcut.keySequence()
            .toString(QKeySequence.SequenceFormat.NativeText)
            .strip()
        )

        if not menu_seq:
            QMessageBox.warning(
                self,
                "단축키 미지정",
                "히든 메뉴 열기 단축키는 비워둘 수 없습니다 (비공개 메뉴 재진입에 필수).",
            )
            self.tabs.setCurrentWidget(self.tab_security)
            self.edit_menu_shortcut.setFocus()
            return

        if menu_seq and force_seq and menu_seq.lower() == force_seq.lower():
            QMessageBox.warning(
                self,
                "단축키 중복 오류",
                "히든 메뉴 열기 단축키와 1회성 강제배치 트리거 단축키는 서로 다르게 지정해야 합니다.",
            )
            self.tabs.setCurrentWidget(self.tab_security)
            self.edit_force_shortcut.setFocus()
            return

        # 3. SecretConfigService에 일괄 저장
        cfg = self.secret_service.load()
        cfg.pin = self._working_pin
        cfg.menu_shortcut = menu_seq
        cfg.force_shortcut = force_seq
        cfg.force_next_assignment = self.chk_force_next.isChecked()
        cfg.preset_map = dict(self._working_preset_map)
        cfg.forbidden_pairs = list(self._working_forbidden_pairs)
        self.secret_service.save(cfg)

        self.accept()
