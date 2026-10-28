"""
교실 자리 배치 프로그램 (Classroom Seating Arrangement Program)
진입점(Entry Point) 및 메인 윈도우 컨트롤러 (main.py)
PyInstaller --onedir 패키징 호환을 위한 동적 리소스 경로(sys._MEIPASS) 헬퍼를 포함합니다.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from models import (
    AnimationSpeed,
    ClassroomGrid,
    Gender,
    OrderDirection,
    PlacementMode,
    PresetType,
    Student,
    ThemeMode,
    ViewPerspective,
)
from services import (
    FileService,
    FileServiceError,
    SeatingService,
    SeatingValidationError,
)
from views import (
    ACTION_CLEAR_ASSIGNMENT,
    ACTION_EXPORT_PRINT_PDF,
    ACTION_LAYOUT_MGMT,
    ACTION_LOAD_EXCEL,
    ACTION_OPEN_EXPORT_MENU,
    ACTION_ROSTER_MGMT,
    ACTION_RUN_PLACEMENT,
    ACTION_SAVE_EXCEL,
    ACTION_SHORTCUT_SETTINGS,
    GridDesignerDialog,
    SeatingBoardView,
    ShortcutManager,
    ShortcutSettingsDialog,
    StudentRosterDialog,
    ThemeManager,
    show_saved_file_message,
)


def resource_path(relative_path: str) -> str:
    """
    PyInstaller (--onedir / --onefile) 환경과 일반 개발 환경 모두에서
    정적 에셋 경로를 안전하게 참조하기 위한 동적 경로 반환 헬퍼 함수입니다.
    하드코딩된 절대 경로를 사용하지 않습니다.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


APP_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #F8FAFC;
    color: #0F172A;
}
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 14px;
    color: #1E293B;
    font-weight: 600;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #F1F5F9;
    border-color: #94A3B8;
}
QPushButton#PrimaryButton {
    background-color: #2563EB;
    border: 1px solid #1D4ED8;
    color: #FFFFFF;
}
QPushButton#PrimaryButton:hover {
    background-color: #1D4ED8;
}
QPushButton#AccentButton {
    background-color: #059669;
    border: 1px solid #047857;
    color: #FFFFFF;
}
QPushButton#AccentButton:hover {
    background-color: #047857;
}
QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1E293B;
    font-weight: 600;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #94A3B8;
}
QCheckBox {
    color: #1E293B;
    font-weight: 600;
    font-size: 12px;
    spacing: 6px;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    margin-top: 8px;
    padding-top: 10px;
    background-color: #FFFFFF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    gridline-color: #E2E8F0;
}
QHeaderView::section {
    background-color: #1E293B;
    color: #FFFFFF;
    padding: 6px;
    font-weight: bold;
    border: none;
}
"""


class MainWindow(QMainWindow):
    """
    교실 자리 배치 프로그램의 메인 애플리케이션 윈도우.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("교실 자리 배치 프로그램 (Classroom Seating Arrangement)")
        self.resize(1180, 780)

        # 초기 모델 상태 (기본 5행 x 8열 짝꿍형, 샘플 학생 20명)
        self.grid = ClassroomGrid(rows=5, cols=8)
        self.grid.apply_preset(PresetType.PAIRS)
        self.roster: List[Student] = self._create_initial_sample_roster()

        self.shortcut_actions: dict[str, QAction] = {}

        self._init_ui()
        self._init_shortcuts()
        self._refresh_all()

    @staticmethod
    def _create_initial_sample_roster() -> List[Student]:
        """프로그램 첫 실행 시 바로 테스트할 수 있는 기본 샘플 학생 명단(20명)을 생성합니다."""
        sample_data = [
            ("1", "강하늘", Gender.MALE), ("2", "고윤정", Gender.FEMALE),
            ("3", "김도현", Gender.MALE), ("4", "김민지", Gender.FEMALE),
            ("5", "김서연", Gender.FEMALE), ("6", "김지훈", Gender.MALE),
            ("7", "남주혁", Gender.MALE), ("8", "노윤서", Gender.FEMALE),
            ("9", "박보검", Gender.MALE), ("10", "박은빈", Gender.FEMALE),
            ("11", "배수지", Gender.FEMALE), ("12", "백현우", Gender.MALE),
            ("13", "서강준", Gender.MALE), ("14", "손예진", Gender.FEMALE),
            ("15", "송강", Gender.MALE), ("16", "신세경", Gender.FEMALE),
            ("17", "안효섭", Gender.MALE), ("18", "아이유", Gender.FEMALE),
            ("19", "유재석", Gender.MALE), ("20", "윤아", Gender.FEMALE),
        ]
        return [Student(num, name, gen) for num, name, gen in sample_data]

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 14, 16, 10)
        root_layout.setSpacing(10)

        # 1. 상단 툴바 프레임
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar_frame)
        tb_layout.setContentsMargins(10, 6, 10, 6)
        tb_layout.setSpacing(8)

        # 1-1. '파일' 드롭다운 메뉴 (맨 왼쪽)
        self.btn_file_menu = QPushButton("📁 파일 ▼")
        self.btn_file_menu.setToolTip("자리 배치 엑셀 저장 및 불러오기 메뉴를 엽니다.")
        file_menu = QMenu(self)

        self.act_save_seating = file_menu.addAction("💾 배치 엑셀 저장", self._save_seating_excel)
        self.act_load_seating = file_menu.addAction("📂 배치 엑셀 불러오기", self._load_seating_excel)
        self.btn_file_menu.setMenu(file_menu)
        tb_layout.addWidget(self.btn_file_menu)

        # 1-2. '설정' 드롭다운 메뉴 (파일 메뉴 옆)
        self.btn_settings_menu = QPushButton("⚙ 설정 ▼")
        self.btn_settings_menu.setToolTip("학생 명단, 책상 레이아웃, 단축키 및 테마 설정 메뉴를 엽니다.")
        settings_menu = QMenu(self)

        self.act_roster = settings_menu.addAction("👥 학생 명단 관리 (엑셀/수동)", self._open_student_dialog)
        self.act_layout = settings_menu.addAction("📐 책상 레이아웃 설정 (N×M)", self._open_grid_designer)
        self.act_shortcuts = settings_menu.addAction("⌨ 단축키 설정", self._open_shortcut_dialog)

        settings_menu.addSeparator()

        # 연출 속도 서브메뉴 추가
        menu_speed = settings_menu.addMenu("🎬 슬롯머신 연출 속도")
        menu_speed.addAction("⚡ 빠르게 (자리당 0.3초)", lambda: self._set_animation_speed(AnimationSpeed.FAST))
        menu_speed.addAction("⏱ 보통 (자리당 0.5초)", lambda: self._set_animation_speed(AnimationSpeed.NORMAL))
        menu_speed.addAction("🐢 느리게 (자리당 1.0초)", lambda: self._set_animation_speed(AnimationSpeed.SLOW))
        menu_speed.addAction("🖐 수동 오픈 (Space / 클릭)", lambda: self._set_animation_speed(AnimationSpeed.MANUAL))

        # 화면 테마(라이트/다크/시스템) 서브메뉴 추가
        menu_theme = settings_menu.addMenu("🎨 화면 테마 설정")
        self.act_theme_light = menu_theme.addAction(
            "☀️ 라이트 모드 (밝은 화면)", lambda: self._set_theme_mode(ThemeMode.LIGHT)
        )
        self.act_theme_dark = menu_theme.addAction(
            "🌙 다크 모드 (어두운 화면)", lambda: self._set_theme_mode(ThemeMode.DARK)
        )
        self.act_theme_system = menu_theme.addAction(
            "💻 시스템 설정 연동", lambda: self._set_theme_mode(ThemeMode.SYSTEM)
        )
        for act in (self.act_theme_light, self.act_theme_dark, self.act_theme_system):
            act.setCheckable(True)

        self.btn_settings_menu.setMenu(settings_menu)
        tb_layout.addWidget(self.btn_settings_menu)

        # 1-3. 빠른 테마 전환 버튼 (라이트 <-> 다크 원클릭 전환)
        self.btn_theme_toggle = QPushButton()
        self.btn_theme_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_toggle.setToolTip("클릭하여 라이트 모드와 다크 모드를 즉시 전환합니다.")
        self.btn_theme_toggle.clicked.connect(self._toggle_theme_quick)
        tb_layout.addWidget(self.btn_theme_toggle)

        # 하위 호환성을 위한 참조 유지
        self.btn_roster = self.act_roster
        self.btn_layout = self.act_layout
        self.btn_save_seating = self.act_save_seating
        self.btn_load_seating = self.act_load_seating
        self.btn_shortcuts = self.act_shortcuts

        tb_layout.addSpacing(10)

        # 배치 방식 드롭다운 (5종)
        self.combo_mode = QComboBox()
        self.combo_mode.setToolTip("자리 배치 방식을 선택하세요.")
        self.combo_mode.addItem("🎲 기본 무작위 배치", PlacementMode.RANDOM)
        self.combo_mode.addItem("👫 남녀 이성 짝꿍 배치", PlacementMode.MIXED_GENDER_PAIR)
        self.combo_mode.addItem("👬 동성 짝꿍 배치", PlacementMode.SAME_GENDER_PAIR)
        self.combo_mode.addItem("🔢 번호순 자동 배치", PlacementMode.NUMBER_ORDER)
        self.combo_mode.addItem("↕ 앞뒤 구역 교차 배치", PlacementMode.FRONT_BACK_CROSS)
        self.combo_mode.currentIndexChanged.connect(self._on_placement_mode_changed)
        tb_layout.addWidget(self.combo_mode)

        # 번호순 배치 전용 방향 선택 (가로 우선 / 세로 우선)
        self.combo_order_dir = QComboBox()
        self.combo_order_dir.setToolTip("번호순 배치 시 좌석을 채우는 방향을 선택하세요.")
        self.combo_order_dir.addItem("가로 우선 (행 순서)", OrderDirection.ROW_FIRST)
        self.combo_order_dir.addItem("세로 우선 (열 순서)", OrderDirection.COL_FIRST)
        self.combo_order_dir.setVisible(False)
        tb_layout.addWidget(self.combo_order_dir)

        # 고정석 유지 체크박스 (기본 체크)
        self.chk_respect_locks = QCheckBox("고정석 유지")
        self.chk_respect_locks.setChecked(True)
        self.chk_respect_locks.setToolTip(
            "체크 시: 고정(📌)된 좌석과 학생을 유지하고 나머지 좌석만 배치합니다.\n"
            "체크 해제 시: 저장된 고정 표시는 유지하되, 이번 배치에서 고정 제약을 무시하고 전체 재배치합니다."
        )
        tb_layout.addWidget(self.chk_respect_locks)

        # 긴장감 연출 (슬롯머신 셔플) on/off 체크박스 (기본 체크, QSettings 영구 저장)
        ui_settings = QSettings("ClassroomSeatingApp", "UISettings")
        saved_effect = ui_settings.value("enable_shuffle_effect", True, type=bool)

        self.chk_shuffle_effect = QCheckBox("🎬 슬롯머신 연출")
        self.chk_shuffle_effect.setChecked(saved_effect)
        self.chk_shuffle_effect.setToolTip(
            "체크 시: 자리 배치 실행 시 슬롯머신 룰렛 셔플 애니메이션으로 긴장감 있게 공개합니다.\n"
            "체크 해제 시: 애니메이션 없이 즉시 결과를 배치합니다."
        )
        self.chk_shuffle_effect.toggled.connect(self._on_toggle_shuffle_effect)
        tb_layout.addWidget(self.chk_shuffle_effect)

        # 연출 속도 선택 콤보박스 (빠르게/보통/느리게/수동)
        self.combo_anim_speed = QComboBox()
        self.combo_anim_speed.setToolTip("슬롯머신 룰렛 연출의 진행 속도 또는 수동 오픈 방식을 선택합니다.")
        self.combo_anim_speed.addItem(AnimationSpeed.FAST.display_kr(), AnimationSpeed.FAST)
        self.combo_anim_speed.addItem(AnimationSpeed.NORMAL.display_kr(), AnimationSpeed.NORMAL)
        self.combo_anim_speed.addItem(AnimationSpeed.SLOW.display_kr(), AnimationSpeed.SLOW)
        self.combo_anim_speed.addItem(AnimationSpeed.MANUAL.display_kr(), AnimationSpeed.MANUAL)

        saved_speed_str = ui_settings.value("animation_speed", AnimationSpeed.NORMAL.value, type=str)
        try:
            saved_speed = AnimationSpeed(saved_speed_str)
        except ValueError:
            saved_speed = AnimationSpeed.NORMAL
        speed_idx = self.combo_anim_speed.findData(saved_speed)
        self.combo_anim_speed.setCurrentIndex(speed_idx if speed_idx >= 0 else 1)
        self.combo_anim_speed.currentIndexChanged.connect(self._on_anim_speed_changed)
        self.combo_anim_speed.setEnabled(saved_effect)
        tb_layout.addWidget(self.combo_anim_speed)

        # 단일 배치 실행 버튼
        self.btn_execute_placement = QPushButton("🎲 배치 실행")
        self.btn_execute_placement.setObjectName("PrimaryButton")
        self.btn_execute_placement.setToolTip("선택한 배치 방식과 고정석 옵션으로 자리를 배치합니다.")
        self.btn_execute_placement.clicked.connect(self._run_placement)
        tb_layout.addWidget(self.btn_execute_placement)

        self.btn_clear = QPushButton("🧹 배정 초기화")
        self.btn_clear.clicked.connect(self._clear_assignments)
        tb_layout.addWidget(self.btn_clear)

        tb_layout.addStretch(1)

        # 단일 내보내기 드롭다운 메뉴 (게시용 vs 교사용 180도 회전 지원)
        self.btn_export_menu = QPushButton("📤 인쇄·게시용 내보내기 ▼")
        self.btn_export_menu.setObjectName("AccentButton")
        self.btn_export_menu.setToolTip("게시용(학생 시점) 또는 교사용(180도 회전 시점)으로 엑셀, PDF, HTML, 한글 문서를 내보냅니다.")

        export_menu = QMenu(self)

        # 1. 게시용 서브메뉴
        menu_student = export_menu.addMenu("📋 게시용 (학생용 - 교탁 위)")
        menu_student.addAction("📊 엑셀 파일 (.xlsx)", lambda: self._export_seating_doc("xlsx", ViewPerspective.STUDENT_VIEW))
        menu_student.addAction("📄 PDF 문서 (.pdf)", lambda: self._export_seating_doc("pdf", ViewPerspective.STUDENT_VIEW))
        menu_student.addAction("🌐 인쇄용 웹 문서 (.html)", lambda: self._export_seating_doc("html", ViewPerspective.STUDENT_VIEW))
        menu_student.addAction("📝 한글 문서 (.hwp - 한컴오피스 필요)", lambda: self._export_seating_doc("hwp", ViewPerspective.STUDENT_VIEW))

        # 2. 교사용 서브메뉴
        menu_teacher = export_menu.addMenu("👩‍🏫 교사용 (교탁 아래 - 180° 회전)")
        menu_teacher.addAction("📊 엑셀 파일 (.xlsx)", lambda: self._export_seating_doc("xlsx", ViewPerspective.TEACHER_VIEW))
        menu_teacher.addAction("📄 PDF 문서 (.pdf)", lambda: self._export_seating_doc("pdf", ViewPerspective.TEACHER_VIEW))
        menu_teacher.addAction("🌐 인쇄용 웹 문서 (.html)", lambda: self._export_seating_doc("html", ViewPerspective.TEACHER_VIEW))
        menu_teacher.addAction("📝 한글 문서 (.hwp - 한컴오피스 필요)", lambda: self._export_seating_doc("hwp", ViewPerspective.TEACHER_VIEW))

        self.btn_export_menu.setMenu(export_menu)
        tb_layout.addWidget(self.btn_export_menu)

        root_layout.addWidget(toolbar_frame)

        # 2. 요약 지표 및 조건 안내 표시줄
        stats_bar = QHBoxLayout()
        self.lbl_stats = QLabel()
        stats_bar.addWidget(self.lbl_stats)
        stats_bar.addStretch(1)

        self.lbl_notice = QLabel("")
        self.lbl_notice.setVisible(False)
        stats_bar.addWidget(self.lbl_notice)
        root_layout.addLayout(stats_bar)

        # 3. 메인 좌석 배치 보드 뷰
        self.seating_view = SeatingBoardView(self)
        self.seating_view.seat_lock_toggled.connect(self._on_toggle_seat_lock)
        self.seating_view.seats_swapped.connect(self._on_swap_seats)
        self.seating_view.seat_preset_requested.connect(self._on_preset_student_to_seat)
        self.seating_view.seat_clear_requested.connect(self._on_clear_single_seat)
        self.seating_view.animation_finished.connect(self._on_placement_animation_finished)
        self.seating_view.manual_reveal_ready.connect(self._on_manual_reveal_ready)
        root_layout.addWidget(self.seating_view, stretch=1)

        # 4. 하단 상태 표시줄
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        status_bar.showMessage("준비 완료 — 상단 버튼으로 학생 명단과 책상 레이아웃을 설정한 뒤 자리를 배치하세요.")

        self._sync_theme_ui()

    def _set_theme_mode(self, mode: ThemeMode) -> None:
        """사용자가 선택한 화면 테마(라이트/다크/시스템)를 즉시 적용하고 영구 저장합니다."""
        ThemeManager.apply_theme(None, mode)
        self._sync_theme_ui()
        self.seating_view.apply_theme_styles()
        self._refresh_all()
        mode_desc = mode.display_kr()
        actual_desc = "다크 모드" if ThemeManager.is_dark() else "라이트 모드"
        self.statusBar().showMessage(f"화면 테마가 [{mode_desc}] (현재: {actual_desc})로 적용되었습니다.")

    def _toggle_theme_quick(self) -> None:
        """툴바 버튼 클릭 시 라이트 모드 <-> 다크 모드를 즉시 전환합니다."""
        next_mode = ThemeMode.LIGHT if ThemeManager.is_dark() else ThemeMode.DARK
        self._set_theme_mode(next_mode)

    def _sync_theme_ui(self) -> None:
        """테마 메뉴 체크 표시와 툴바 테마 전환 버튼, 라벨 스타일을 현재 테마에 맞게 동기화합니다."""
        cur_mode = ThemeManager.current_mode()
        is_dark = ThemeManager.is_dark()

        if hasattr(self, "act_theme_light"):
            self.act_theme_light.setChecked(cur_mode == ThemeMode.LIGHT)
            self.act_theme_dark.setChecked(cur_mode == ThemeMode.DARK)
            self.act_theme_system.setChecked(cur_mode == ThemeMode.SYSTEM)

        if hasattr(self, "btn_theme_toggle"):
            if is_dark:
                self.btn_theme_toggle.setText("☀️ 라이트")
                self.btn_theme_toggle.setToolTip("현재: 다크 모드 (클릭하면 ☀️ 라이트 모드로 전환합니다)")
            else:
                self.btn_theme_toggle.setText("🌙 다크")
                self.btn_theme_toggle.setToolTip("현재: 라이트 모드 (클릭하면 🌙 다크 모드로 전환합니다)")

        stats_color = "#F8FAFC" if is_dark else "#1E293B"
        self.lbl_stats.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {stats_color};")

        if is_dark:
            self.lbl_notice.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: #FDE68A; background-color: #451A03; "
                "border: 1px solid #F59E0B; border-radius: 5px; padding: 2px 8px;"
            )
        else:
            self.lbl_notice.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: #B45309; background-color: #FEF3C7; "
                "border: 1px solid #F59E0B; border-radius: 5px; padding: 2px 8px;"
            )

    def _on_placement_mode_changed(self) -> None:
        """번호순 자동 배치 선택 시에만 가로/세로 방향 드롭다운을 표시합니다."""
        mode = self.combo_mode.currentData()
        self.combo_order_dir.setVisible(mode == PlacementMode.NUMBER_ORDER)

    def _set_notice(self, notice: Optional[str]) -> None:
        if notice:
            self.lbl_notice.setText(f"ℹ {notice}")
            self.lbl_notice.setVisible(True)
        else:
            self.lbl_notice.clear()
            self.lbl_notice.setVisible(False)

    def _refresh_all(self) -> None:
        """보드 뷰와 상단 통계 요약 라벨을 최신 모델 상태로 갱신합니다."""
        self.seating_view.render_grid(self.grid)

        total_students = len(self.roster)
        active_desks = len(self.grid.active_desks())
        assigned_count = len(self.grid.assigned_students_map())
        locked_count = len(self.grid.locked_desks())

        is_dark = ThemeManager.is_dark()
        if active_desks < total_students:
            status_color = "#F87171" if is_dark else "#DC2626"
        else:
            status_color = "#34D399" if is_dark else "#059669"

        self.lbl_stats.setText(
            f"격자 크기: {self.grid.rows}행 × {self.grid.cols}열  |  "
            f"등록 학생: <b>{total_students}명</b>  |  "
            f"<span style='color:{status_color};'>활성 책상: <b>{active_desks}석</b></span>  |  "
            f"배정 완료: <b>{assigned_count}명</b>  |  "
            f"고정 좌석(Pin): <b>{locked_count}석</b>"
        )

    # ------------------------------------------------------------------
    # 다이얼로그 및 배치 액션 핸들러
    # ------------------------------------------------------------------
    def _open_student_dialog(self) -> None:
        if self.seating_view.is_animating():
            return
        dlg = StudentRosterDialog(self.roster, self)
        if dlg.exec() == StudentRosterDialog.DialogCode.Accepted:
            self.roster = dlg.get_roster()
            # 명단에서 제거된 학생이 좌석에 남아 있다면 정리
            valid_ids = {s.student_id for s in self.roster}
            for seat in self.grid.active_desks():
                if seat.student and seat.student.student_id not in valid_ids:
                    seat.student = None
                    seat.is_locked = False
            self._set_notice(None)
            self._refresh_all()
            self.statusBar().showMessage(f"학생 명단이 업데이트되었습니다 (총 {len(self.roster)}명).")

    def _open_grid_designer(self) -> None:
        if self.seating_view.is_animating():
            return
        dlg = GridDesignerDialog(self.grid, len(self.roster), self)
        if dlg.exec() == GridDesignerDialog.DialogCode.Accepted:
            new_r, new_c, states = dlg.get_layout_result()
            self.grid.resize(new_r, new_c)
            self.grid.apply_layout_states(states)
            self.seating_view.clear_selection()
            self._set_notice(None)
            self._refresh_all()
            self.statusBar().showMessage(
                f"책상 레이아웃이 {new_r}행 × {new_c}열 (활성 {len(self.grid.active_desks())}석)로 변경되었습니다."
            )

    def _on_toggle_shuffle_effect(self, checked: bool) -> None:
        """슬롯머신 연출 on/off 설정을 영구 저장하고 콤보박스 활성화 상태를 갱신합니다."""
        ui_settings = QSettings("ClassroomSeatingApp", "UISettings")
        ui_settings.setValue("enable_shuffle_effect", checked)
        if hasattr(self, "combo_anim_speed") and not self.seating_view.is_animating():
            self.combo_anim_speed.setEnabled(checked)

    def _set_animation_speed(self, speed: AnimationSpeed) -> None:
        """설정 메뉴에서 선택 시 툴바 콤보박스와 설정을 동기화합니다."""
        idx = self.combo_anim_speed.findData(speed)
        if idx >= 0:
            self.combo_anim_speed.setCurrentIndex(idx)

    def _on_anim_speed_changed(self) -> None:
        """연출 속도 콤보박스 변경 시 QSettings에 영구 저장합니다."""
        speed = self.combo_anim_speed.currentData()
        if isinstance(speed, AnimationSpeed):
            ui_settings = QSettings("ClassroomSeatingApp", "UISettings")
            ui_settings.setValue("animation_speed", speed.value)

    def _set_controls_enabled_for_anim(self, enabled: bool) -> None:
        """애니메이션 재생 중 상태 충돌을 방지하기 위해 비배치 UI 컨트롤을 일괄 활성/비활성화합니다."""
        self.btn_clear.setEnabled(enabled)
        self.btn_file_menu.setEnabled(enabled)
        self.btn_settings_menu.setEnabled(enabled)
        self.btn_theme_toggle.setEnabled(enabled)
        self.btn_export_menu.setEnabled(enabled)
        self.combo_mode.setEnabled(enabled)
        self.combo_order_dir.setEnabled(enabled)
        self.chk_shuffle_effect.setEnabled(enabled)
        self.combo_anim_speed.setEnabled(enabled and self.chk_shuffle_effect.isChecked())
        self.chk_respect_locks.setEnabled(enabled)

    def _run_placement(self) -> None:
        """툴바에서 선택된 배치 방식과 고정석 유지 여부에 따라 배치를 실행합니다."""
        # 연출 중 다시 클릭한 경우:
        # - 수동 모드 진행 중이면 다음 좌석 확정 오픈
        # - 자동 모드 진행 중이면 즉시 전체 스킵
        if self.seating_view.is_animating():
            if self.seating_view.is_in_manual_phase():
                self.seating_view.reveal_next_manual()
            else:
                self.seating_view.skip_animation()
            return

        mode = self.combo_mode.currentData()
        if not isinstance(mode, PlacementMode):
            mode = PlacementMode.RANDOM
        respect_locks = self.chk_respect_locks.isChecked()
        order_dir = self.combo_order_dir.currentData()
        if not isinstance(order_dir, OrderDirection):
            order_dir = OrderDirection.ROW_FIRST

        try:
            status_msg, notice = SeatingService.execute_placement(
                self.grid,
                self.roster,
                mode=mode,
                respect_locks=respect_locks,
                order_direction=order_dir,
            )
            self._last_status_msg = status_msg
            self._last_notice = notice

            if self.chk_shuffle_effect.isChecked():
                # 긴장감 연출 (슬롯머신 셔플) 시작 (선택된 속도/모드 적용)
                speed = self.combo_anim_speed.currentData()
                if not isinstance(speed, AnimationSpeed):
                    speed = AnimationSpeed.NORMAL

                # 연출 진행 중에는 초기화 및 기타 제어 UI 비활성화 (상태 충돌/프리징 방지)
                self._set_controls_enabled_for_anim(False)

                if speed == AnimationSpeed.MANUAL:
                    self.btn_execute_placement.setText("🎲 슬롯머신 셔플 중...")
                    self.statusBar().showMessage("🎲 슬롯머신 전체 셔플 중... (1초 후 [Space/클릭]으로 1자리씩 오픈 대기)")
                else:
                    self.btn_execute_placement.setText("⏭ 스킵 (ESC)")
                    self.statusBar().showMessage(f"🎲 슬롯머신 자리 공개 진행 중 [{speed.display_kr()}]... (ESC: 즉시 스킵)")

                self.btn_execute_placement.setStyleSheet(
                    "background-color: #7C3AED; color: #FFFFFF; font-weight: bold; border-radius: 6px; padding: 7px 14px;"
                )
                self.seating_view.start_slot_machine_animation(
                    self.grid, self.roster, speed=speed, respect_locks=respect_locks
                )
            else:
                # 연출 OFF: 즉시 결과 반영
                self._set_controls_enabled_for_anim(True)
                self.seating_view.clear_selection()
                self._set_notice(notice)
                self._refresh_all()
                self.statusBar().showMessage(status_msg)
        except SeatingValidationError as exc:
            QMessageBox.warning(self, "자리 배치 불가", str(exc))

    def _on_manual_reveal_ready(self, remaining: int, total: int) -> None:
        """수동 오픈 모드에서 대기 상태일 때 UI 상태표시줄과 버튼 문구를 갱신합니다."""
        revealed = total - remaining
        self.btn_execute_placement.setText(f"🖐 다음 좌석 오픈 ({revealed}/{total})")
        self.btn_execute_placement.setStyleSheet(
            "background-color: #059669; color: #FFFFFF; font-weight: bold; border-radius: 6px; padding: 7px 14px;"
        )
        self.statusBar().showMessage(
            f"🖐 수동 오픈 대기: [Space / Enter / 버튼 클릭] 또는 [좌석 직접 클릭]으로 다음 자리를 공개하세요. "
            f"(남은 좌석: {remaining}석 / 전체 {total}석) | ESC: 즉시 전체 공개"
        )

    def _on_placement_animation_finished(self) -> None:
        """슬롯머신 애니메이션 완료 시 버튼 원복 및 UI 컨트롤 재활성화"""
        self.btn_execute_placement.setText("🎲 배치 실행")
        self.btn_execute_placement.setStyleSheet("")

        # 애니메이션 중 비활성화했던 UI 컨트롤 복원
        self._set_controls_enabled_for_anim(True)

        self.seating_view.clear_selection()
        if hasattr(self, "_last_notice"):
            self._set_notice(self._last_notice)
        self._refresh_all()
        if hasattr(self, "_last_status_msg"):
            self.statusBar().showMessage(self._last_status_msg)

    def keyPressEvent(self, event) -> None:
        """연출 중 키보드 조작 처리 (ESC: 즉시 전체 스킵, Space/Enter: 수동 1자리 오픈 또는 스킵)"""
        if self.seating_view.is_animating():
            if event.key() == Qt.Key.Key_Escape:
                self.seating_view.skip_animation()
                event.accept()
                return

            if self.seating_view.is_in_manual_phase() and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
                self.seating_view.reveal_next_manual()
                event.accept()
                return

            if not self.seating_view.is_in_manual_phase() and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
                self.seating_view.skip_animation()
                event.accept()
                return

        super().keyPressEvent(event)

    def _run_locked_random_assignment(self) -> None:
        """호환용 헬퍼: 기본 무작위 + 고정석 유지 배치 실행"""
        self.combo_mode.setCurrentIndex(self.combo_mode.findData(PlacementMode.RANDOM))
        self.chk_respect_locks.setChecked(True)
        self._run_placement()

    def _run_full_random_assignment(self) -> None:
        """호환용 헬퍼: 기본 무작위 + 고정 제약 무시 배치 실행"""
        self.combo_mode.setCurrentIndex(self.combo_mode.findData(PlacementMode.RANDOM))
        self.chk_respect_locks.setChecked(False)
        self._run_placement()

    def _clear_assignments(self) -> None:
        if self.seating_view.is_animating():
            self.seating_view.skip_animation()

        keep_locks = False
        if self.grid.locked_desks():
            reply = QMessageBox.question(
                self,
                "배정 초기화 옵션",
                "고정(Pin)된 좌석의 학생은 그대로 유지하시겠습니까?\n"
                "• [Yes]: 고정석 유지 후 일반 좌석만 비우기\n"
                "• [No]: 고정석을 포함한 모든 좌석 비우기",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            keep_locks = reply == QMessageBox.StandardButton.Yes

        self.grid.clear_all_assignments(keep_locked=keep_locks)
        self.seating_view.clear_selection()
        self._set_notice(None)
        self._refresh_all()
        self.statusBar().showMessage("좌석 배정이 초기화되었습니다.")

    def _on_toggle_seat_lock(self, row: int, col: int) -> None:
        if self.seating_view.is_animating():
            return
        seat = self.grid.get_seat(row, col)
        if seat.is_active_desk:
            seat.is_locked = not seat.is_locked
            self._refresh_all()
            state_txt = "고정(Pin) 설정" if seat.is_locked else "고정 해제"
            self.statusBar().showMessage(f"{seat.coordinate_label()} 좌석이 {state_txt}되었습니다.")

    def _on_swap_seats(self, from_r: int, from_c: int, to_r: int, to_c: int) -> None:
        if self.seating_view.is_animating():
            return
        try:
            SeatingService.swap_seats(self.grid, (from_r, from_c), (to_r, to_c))
            self._refresh_all()
            self.statusBar().showMessage(
                f"{from_r + 1}행 {from_c + 1}열 ↔ {to_r + 1}행 {to_c + 1}열 자리를 맞바꾸었습니다."
            )
        except SeatingValidationError as exc:
            QMessageBox.warning(self, "자리 맞바꾸기 오류", str(exc))

    def _on_preset_student_to_seat(self, row: int, col: int) -> None:
        if self.seating_view.is_animating():
            return
        if not self.roster:
            QMessageBox.information(
                self, "학생 명단 없음", "먼저 [학생 명단 관리]에서 학생을 등록해 주세요."
            )
            return

        seat = self.grid.get_seat(row, col)
        sorted_roster = sorted(self.roster, key=lambda s: s.sort_key())
        items = ["(선택 해제 / 좌석 비우기)"] + [s.display_label() for s in sorted_roster]

        current_idx = 0
        if seat.student is not None:
            for idx, st in enumerate(sorted_roster, start=1):
                if st.student_id == seat.student.student_id:
                    current_idx = idx
                    break

        choice, ok = QInputDialog.getItem(
            self,
            f"{seat.coordinate_label()} 학생 직접 배정",
            f"{seat.coordinate_label()} 좌석에 고정 배정할 학생을 선택하세요:",
            items,
            current_idx,
            False,
        )
        if not ok:
            return

        if choice == items[0]:
            SeatingService.assign_student_to_seat(self.grid, (row, col), None)
        else:
            chosen_idx = items.index(choice) - 1
            chosen_student = sorted_roster[chosen_idx]
            SeatingService.assign_student_to_seat(
                self.grid, (row, col), chosen_student, auto_lock=True
            )

        self._refresh_all()

    def _on_clear_single_seat(self, row: int, col: int) -> None:
        if self.seating_view.is_animating():
            return
        SeatingService.assign_student_to_seat(self.grid, (row, col), None)
        self._refresh_all()

    # ------------------------------------------------------------------
    # 자리 배치 복원용 엑셀 저장 / 불러오기 핸들러
    # ------------------------------------------------------------------
    def _save_seating_excel(self) -> None:
        """현재 교실 자리 배치와 명단, 설정을 복원 가능한 엑셀 파일(.xlsx)로 저장합니다."""
        if self.seating_view.is_animating():
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "자리 배치 엑셀 저장 (복원용 데이터 포함)",
            "교실_자리배치_저장데이터.xlsx",
            "Excel Workbook (*.xlsx)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"

        mode = self.combo_mode.currentData()
        if not isinstance(mode, PlacementMode):
            mode = PlacementMode.RANDOM
        respect_locks = self.chk_respect_locks.isChecked()
        order_dir = self.combo_order_dir.currentData()
        if not isinstance(order_dir, OrderDirection):
            order_dir = OrderDirection.ROW_FIRST

        try:
            saved = FileService.save_seating_to_excel(
                file_path,
                self.grid,
                self.roster,
                mode=mode,
                respect_locks=respect_locks,
                order_direction=order_dir,
            )
            show_saved_file_message(
                self,
                "자리 배치 엑셀 저장 완료",
                f"자리 배치와 학생 명단, 레이아웃 및 설정이 안전하게 저장되었습니다:\n{saved}\n\n"
                "나중에 [배치 엑셀 불러오기]를 통해 언제든지 그대로 복원할 수 있습니다.",
                saved,
            )
            self.statusBar().showMessage(f"자리 배치 저장 완료: {saved}")
        except FileServiceError as exc:
            QMessageBox.critical(self, "자리 배치 저장 오류", str(exc))

    def _load_seating_excel(self) -> None:
        """이전에 저장한 자리 배치 엑셀 파일(.xlsx)을 불러와 레이아웃과 배치를 복원합니다."""
        if self.seating_view.is_animating():
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "자리 배치 엑셀 파일 불러오기",
            "",
            "Excel Files (*.xlsx);;All Files (*)",
        )
        if not file_path:
            return

        reply = QMessageBox.question(
            self,
            "자리 배치 복원 확인",
            "현재 교실 자리 배치와 학생 명단을 선택한 엑셀 파일의 데이터로 교체하시겠습니까?\n\n"
            "※ 주의: 현재 화면의 저장되지 않은 변경사항은 대체됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            restored = FileService.load_seating_from_excel(file_path)

            # 한 번에 원자적(Atomic) 적용
            self.grid = restored.grid
            self.roster = restored.roster

            mode_idx = self.combo_mode.findData(restored.mode)
            if mode_idx >= 0:
                self.combo_mode.setCurrentIndex(mode_idx)

            self.chk_respect_locks.setChecked(restored.respect_locks)

            dir_idx = self.combo_order_dir.findData(restored.order_direction)
            if dir_idx >= 0:
                self.combo_order_dir.setCurrentIndex(dir_idx)

            self.seating_view.clear_selection()
            self._set_notice(None)
            self._refresh_all()

            assigned_count = len(self.grid.assigned_students_map())
            locked_count = len(self.grid.locked_desks())
            self.statusBar().showMessage(
                f"자리 배치가 성공적으로 복원되었습니다 (학생 {len(self.roster)}명, {self.grid.rows}행×{self.grid.cols}열)."
            )
            QMessageBox.information(
                self,
                "자리 배치 복원 완료",
                f"엑셀 파일에서 자리 배치를 성공적으로 복원했습니다:\n\n"
                f"• 파일 경로: {file_path}\n"
                f"• 등록 학생: {len(self.roster)}명\n"
                f"• 교실 격자: {self.grid.rows}행 × {self.grid.cols}열 (활성 {len(self.grid.active_desks())}석)\n"
                f"• 배정 완료: {assigned_count}명\n"
                f"• 고정 좌석: {locked_count}석",
            )
        except FileServiceError as exc:
            QMessageBox.critical(self, "자리 배치 불러오기 실패", str(exc))

    # ------------------------------------------------------------------
    # 파일 내보내기 핸들러 (Excel / HWP / PDF / HTML, 게시용/교사용)
    # ------------------------------------------------------------------
    def _export_seating_doc(self, fmt: str, perspective: ViewPerspective) -> None:
        """
        선택된 포맷(xlsx, pdf, html, hwp)과 시점(게시용/교사용)에 맞추어 자리배치 문서를 내보냅니다.
        교사용 선택 시 180도 회전(행/열 반전, 글자는 정방향) 및 교탁 아래 배치가 적용됩니다.
        """
        if self.seating_view.is_animating():
            return
        is_teacher = (perspective == ViewPerspective.TEACHER_VIEW)
        suffix = "교사용" if is_teacher else "게시용"
        filter_map = {
            "xlsx": "Excel Workbook (*.xlsx)",
            "pdf": "PDF 문서 (*.pdf)",
            "html": "인쇄용 웹 문서 (*.html)",
            "hwp": "한컴오피스 한글 문서 (*.hwp);;PDF 문서 (*.pdf);;인쇄용 웹 문서 (*.html)",
        }
        default_filename = f"교실_자리배치표_{suffix}.{fmt}"
        dialog_title = f"{perspective.display_kr()} 자리 배치표 내보내기 ({fmt.upper()})"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            default_filename,
            filter_map.get(fmt, "모든 파일 (*.*)"),
        )
        if not file_path:
            return

        # 확장자 보정
        ext = os.path.splitext(file_path)[1].lower()
        if not ext:
            file_path = f"{file_path}.{fmt}"

        try:
            if fmt == "xlsx":
                saved = FileService.export_to_excel(
                    file_path, self.grid, self.roster, perspective=perspective
                )
                msg = f"엑셀 자리 배치표({perspective.display_kr()})와 학생별 배정 요약 시트가 저장되었습니다:\n{saved}"
            elif fmt in ("hwp", "pdf", "html"):
                saved, msg = FileService.export_document_with_fallback(
                    file_path, self.grid, self.roster, perspective=perspective
                )
            else:
                raise ValueError(f"지원하지 않는 포맷입니다: {fmt}")

            show_saved_file_message(
                self, f"내보내기 완료 ({perspective.display_kr()})", msg, saved
            )
            self.statusBar().showMessage(f"저장 완료 ({perspective.display_kr()}): {saved}")
        except Exception as exc:
            QMessageBox.critical(self, "내보내기 오류", f"파일 저장 중 오류가 발생했습니다:\n{exc}")

    def _export_excel(self) -> None:
        """기존 단축키 및 호환성을 위한 게시용 기본 엑셀 내보내기"""
        self._export_seating_doc("xlsx", ViewPerspective.STUDENT_VIEW)

    def _export_hwp_or_doc(self) -> None:
        """기존 단축키 및 호환성을 위한 게시용 기본 한글/PDF/HTML 내보내기"""
        self._export_seating_doc("hwp", ViewPerspective.STUDENT_VIEW)

    # ------------------------------------------------------------------
    # 단축키(Shortcuts) 관리 및 핸들러
    # ------------------------------------------------------------------
    def _init_shortcuts(self) -> None:
        """기능별 QAction 객체를 생성하고 MainWindow에 바인딩합니다."""
        # 드롭다운 메뉴 항목 액션 연결 (메뉴를 열었을 때 우측에 단축키 자동 표시)
        menu_actions = {
            ACTION_SAVE_EXCEL: self.act_save_seating,
            ACTION_LOAD_EXCEL: self.act_load_seating,
            ACTION_ROSTER_MGMT: self.act_roster,
            ACTION_LAYOUT_MGMT: self.act_layout,
            ACTION_SHORTCUT_SETTINGS: self.act_shortcuts,
        }
        for action_id, action in menu_actions.items():
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.addAction(action)
            self.shortcut_actions[action_id] = action

        # 전역 실행 액션 연결
        global_handlers = {
            ACTION_RUN_PLACEMENT: self._run_placement_guarded,
            ACTION_CLEAR_ASSIGNMENT: self._clear_assignments_guarded,
            ACTION_OPEN_EXPORT_MENU: self._open_export_menu,
            ACTION_EXPORT_PRINT_PDF: lambda: self._export_seating_doc("pdf", ViewPerspective.STUDENT_VIEW),
        }
        for action_id, handler in global_handlers.items():
            action = QAction(self)
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(handler)
            self.addAction(action)
            self.shortcut_actions[action_id] = action

        self._apply_shortcuts()

    def _apply_shortcuts(self) -> None:
        """
        저장소(QSettings)에서 단축키 설정을 읽어 QAction에 반영하고,
        버튼 툴팁에도 현재 단축키를 표시합니다.
        """
        shortcuts = ShortcutManager.load_shortcuts()

        for action_id, action in self.shortcut_actions.items():
            seq_str = shortcuts.get(action_id, "")
            if seq_str:
                action.setShortcut(QKeySequence(seq_str))
                action.setEnabled(True)
            else:
                action.setShortcut(QKeySequence())
                action.setEnabled(False)

        # 버튼 툴팁 동적 갱신
        def tip(base: str, action_id: str) -> str:
            seq = shortcuts.get(action_id, "")
            return f"{base} [{seq}]" if seq else base

        save_seq = shortcuts.get(ACTION_SAVE_EXCEL, "")
        load_seq = shortcuts.get(ACTION_LOAD_EXCEL, "")
        self.btn_file_menu.setToolTip(f"자리 배치 엑셀 저장 및 불러오기 (저장: {save_seq or '미지정'}, 불러오기: {load_seq or '미지정'})")

        roster_seq = shortcuts.get(ACTION_ROSTER_MGMT, "")
        layout_seq = shortcuts.get(ACTION_LAYOUT_MGMT, "")
        shortcut_seq = shortcuts.get(ACTION_SHORTCUT_SETTINGS, "")
        self.btn_settings_menu.setToolTip(f"학생 명단({roster_seq}), 책상 레이아웃({layout_seq}), 단축키 설정({shortcut_seq})")

        self.btn_execute_placement.setToolTip(tip("선택한 배치 방식과 고정석 옵션으로 자리를 배치합니다.", ACTION_RUN_PLACEMENT))
        self.btn_clear.setToolTip(tip("현재 배정된 학생들을 좌석에서 비웁니다 (고정석 제외).", ACTION_CLEAR_ASSIGNMENT))
        self.btn_export_menu.setToolTip(tip("게시용(학생 시점) 또는 교사용(180도 회전)으로 문서를 내보냅니다.", ACTION_OPEN_EXPORT_MENU))

    def _is_input_widget_focused(self) -> bool:
        """
        현재 텍스트 입력 위젯(QLineEdit, QTextEdit 등)에 포커스가 있는지 확인합니다.
        글자 입력이나 단어 삭제(Ctrl+Backspace) 중 의도치 않은 전역 동작을 방지합니다.
        """
        focus_w = QApplication.focusWidget()
        if focus_w is not None:
            from PyQt6.QtWidgets import QAbstractSpinBox, QLineEdit, QPlainTextEdit, QTextEdit
            if isinstance(focus_w, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
                return True
        return False

    def _run_placement_guarded(self) -> None:
        """텍스트 입력 중 오작동 방지 가드가 적용된 자리 배치 실행"""
        if self._is_input_widget_focused():
            return
        self._run_placement()

    def _clear_assignments_guarded(self) -> None:
        """텍스트 입력 중(특히 단어 삭제 Ctrl+Backspace) 오작동 방지 가드가 적용된 배정 초기화"""
        if self._is_input_widget_focused():
            return
        self._clear_assignments()

    def _open_export_menu(self) -> None:
        """내보내기 메뉴를 엽니다 (Ctrl+E 등 단축키 연동)"""
        if self._is_input_widget_focused() or self.seating_view.is_animating():
            return
        self.btn_export_menu.showMenu()

    def _open_shortcut_dialog(self) -> None:
        """단축키 설정 대화상자를 열고, 변경 사항 저장 시 즉시 재적용합니다."""
        if self.seating_view.is_animating():
            return
        dlg = ShortcutSettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_shortcuts()
            self.statusBar().showMessage("단축키 설정이 성공적으로 저장 및 적용되었습니다.")


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 10))
    ThemeManager.apply_theme(app, ThemeManager.load_saved_mode())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
