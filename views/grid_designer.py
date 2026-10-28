"""
교실 자리 배치 프로그램 - 대화형 좌석 레이아웃 편집기 (views/grid_designer.py)
N x M 마스터 격자 크기 설정, 셀 클릭 토글(활성 책상 / 복도 / 비활성), 프리셋 배치를 제공합니다.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from models import CellState, ClassroomGrid, PresetType
from .theme_manager import ThemeManager


class GridCellButton(QPushButton):
    """
    격자 편집기에서 각 셀(row, col)의 상태를 클릭으로 순환 토글하는 버튼 위젯.
    """

    def __init__(
        self,
        row: int,
        col: int,
        state: CellState = CellState.ACTIVE,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.row = row
        self.col = col
        self.state = state
        self.setMinimumSize(78, 54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._on_clicked)
        self.refresh_appearance()

    def _on_clicked(self) -> None:
        self.state = self.state.next_state()
        self.refresh_appearance()

    def set_cell_state(self, state: CellState) -> None:
        self.state = state
        self.refresh_appearance()

    def refresh_appearance(self) -> None:
        coord_text = f"({self.row + 1}, {self.col + 1})"
        is_dark = ThemeManager.is_dark()

        if self.state == CellState.ACTIVE:
            self.setText(f"{coord_text}\n[활성 책상]")
            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #1E3A8A;
                        border: 2px solid #3B82F6;
                        border-radius: 6px;
                        color: #F8FAFC;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #1D4ED8;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #EFF6FF;
                        border: 2px solid #2563EB;
                        border-radius: 6px;
                        color: #1E3A8A;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #DBEAFE;
                    }
                    """
                )
        elif self.state == CellState.AISLE:
            self.setText(f"{coord_text}\n[복도/통로]")
            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #0F172A;
                        border: 1px dashed #475569;
                        border-radius: 6px;
                        color: #94A3B8;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #1E293B;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #F8FAFC;
                        border: 1px dashed #94A3B8;
                        border-radius: 6px;
                        color: #64748B;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #F1F5F9;
                    }
                    """
                )
        else:
            self.setText(f"{coord_text}\n[비활성]")
            if is_dark:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #1E293B;
                        border: 1px solid #334155;
                        border-radius: 6px;
                        color: #64748B;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #334155;
                    }
                    """
                )
            else:
                self.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #E2E8F0;
                        border: 1px solid #CBD5E1;
                        border-radius: 6px;
                        color: #94A3B8;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #CBD5E1;
                    }
                    """
                )


class GridDesignerDialog(QDialog):
    """
    교실 N x M 마스터 격자 크기 및 개별 셀 상태(활성 책상 / 통로 / 비활성)를 설정하는 대화상자.
    """

    def __init__(
        self,
        current_grid: ClassroomGrid,
        student_count: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("교실 책상 레이아웃 설정")
        self.resize(860, 640)

        self._student_count = student_count
        self._working_grid = ClassroomGrid(rows=current_grid.rows, cols=current_grid.cols)
        self._working_grid.apply_layout_states(current_grid.clone_layout_states())
        self._cell_buttons: Dict[Tuple[int, int], GridCellButton] = {}

        self._init_ui()
        self._rebuild_grid_buttons()

    def _init_ui(self) -> None:
        is_dark = ThemeManager.is_dark()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. 상단 컨트롤 박스 (N x M 크기 & 프리셋 템플릿)
        top_group = QGroupBox("1. 격자 크기(N × M) 및 프리셋 템플릿 선택")
        top_layout = QHBoxLayout(top_group)

        top_layout.addWidget(QLabel("행(가로 줄, N):"))
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 15)
        self.spin_rows.setValue(self._working_grid.rows)
        self.spin_rows.setFixedWidth(84)
        self.spin_rows.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_rows.setToolTip("교실 행(가로 줄) 수를 변경합니다 (1~15).")
        self.spin_rows.valueChanged.connect(self._on_dimensions_changed)
        top_layout.addWidget(self.spin_rows)

        top_layout.addSpacing(8)
        top_layout.addWidget(QLabel("열(세로 칸, M):"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 15)
        self.spin_cols.setValue(self._working_grid.cols)
        self.spin_cols.setFixedWidth(84)
        self.spin_cols.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_cols.setToolTip("교실 열(세로 칸) 수를 변경합니다 (1~15).")
        self.spin_cols.valueChanged.connect(self._on_dimensions_changed)
        top_layout.addWidget(self.spin_cols)

        top_layout.addSpacing(20)
        top_layout.addWidget(QLabel("빠른 프리셋:"))

        btn_pairs = QPushButton("👥 짝꿍형 (2열 1조)")
        btn_pairs.clicked.connect(lambda: self._apply_preset(PresetType.PAIRS))
        top_layout.addWidget(btn_pairs)

        btn_exam = QPushButton("📝 시험 대형 (1열 단독)")
        btn_exam.clicked.connect(lambda: self._apply_preset(PresetType.EXAM))
        top_layout.addWidget(btn_exam)

        btn_cluster = QPushButton("🧩 모둠형 (4인 클러스터)")
        btn_cluster.clicked.connect(lambda: self._apply_preset(PresetType.CLUSTER))
        top_layout.addWidget(btn_cluster)

        btn_all = QPushButton("🔄 전체 활성 책상")
        btn_all.clicked.connect(lambda: self._apply_preset(PresetType.ALL_ACTIVE))
        top_layout.addWidget(btn_all)

        top_layout.addStretch(1)
        main_layout.addWidget(top_group)

        # 2. 상태 안내 및 범례 표시줄
        info_bar = QHBoxLayout()
        guide_lbl = QLabel(
            "💡 각 셀을 클릭할 때마다 <b>[활성 책상] → [복도/통로] → [비활성]</b> 순서로 전환됩니다."
        )
        guide_color = "#CBD5E1" if is_dark else "#334155"
        guide_lbl.setStyleSheet(f"color: {guide_color};")
        info_bar.addWidget(guide_lbl)
        info_bar.addStretch(1)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("font-weight: bold; font-size: 13px;")
        info_bar.addWidget(self.lbl_summary)
        main_layout.addLayout(info_bar)

        # 3. 교탁 배너
        podium_frame = QFrame()
        podium_frame.setStyleSheet(
            "background-color: #334155; color: #FFFFFF; border-radius: 6px; padding: 6px;"
        )
        podium_layout = QHBoxLayout(podium_frame)
        podium_lbl = QLabel("칠 판 / 교 탁 (교실 앞쪽)")
        podium_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        podium_lbl.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 13px;")
        podium_layout.addWidget(podium_lbl)
        main_layout.addWidget(podium_frame)

        # 4. 대화형 격자 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        board_bg = "#0B1120" if is_dark else "#F1F5F9"
        board_bd = "#334155" if is_dark else "#CBD5E1"
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {board_bg}; border: 1px solid {board_bd}; border-radius: 8px; }}"
        )
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet(f"background-color: {board_bg};")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(8)
        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 5. 하단 저장/취소 버튼
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch(1)

        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)

        btn_apply = QPushButton("레이아웃 적용")
        btn_apply.setObjectName("PrimaryButton")
        btn_apply.setDefault(True)
        btn_apply.clicked.connect(self._on_apply)

        bottom_bar.addWidget(btn_cancel)
        bottom_bar.addWidget(btn_apply)
        main_layout.addLayout(bottom_bar)

    def _sync_button_states_to_working_grid(self) -> None:
        for (r, c), btn in self._cell_buttons.items():
            if 0 <= r < self._working_grid.rows and 0 <= c < self._working_grid.cols:
                self._working_grid.get_seat(r, c).set_state(btn.state)

    def _on_dimensions_changed(self) -> None:
        self._sync_button_states_to_working_grid()
        new_rows = self.spin_rows.value()
        new_cols = self.spin_cols.value()
        self._working_grid.resize(new_rows, new_cols)
        self._rebuild_grid_buttons()

    def _apply_preset(self, preset: PresetType) -> None:
        self._working_grid.apply_preset(preset)
        for (r, c), btn in self._cell_buttons.items():
            btn.set_cell_state(self._working_grid.get_seat(r, c).state)
        self._update_summary_label()

    def _rebuild_grid_buttons(self) -> None:
        # 기존 위젯 제거
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

        self._cell_buttons.clear()

        for r in range(self._working_grid.rows):
            for c in range(self._working_grid.cols):
                seat = self._working_grid.get_seat(r, c)
                btn = GridCellButton(r, c, seat.state, parent=self.grid_container)
                btn.clicked.connect(self._update_summary_label)
                self.grid_layout.addWidget(btn, r, c)
                self._cell_buttons[(r, c)] = btn

        self._update_summary_label()

    def _update_summary_label(self) -> None:
        is_dark = ThemeManager.is_dark()
        active_count = sum(
            1 for btn in self._cell_buttons.values() if btn.state == CellState.ACTIVE
        )
        aisle_count = sum(
            1 for btn in self._cell_buttons.values() if btn.state == CellState.AISLE
        )
        if active_count < self._student_count:
            color = "#F87171" if is_dark else "#DC2626"
            warn = f" (⚠ 학생 수 {self._student_count}명보다 {self._student_count - active_count}석 부족)"
        else:
            color = "#34D399" if is_dark else "#15803D"
            warn = f" (학생 {self._student_count}명 수용 가능)"

        self.lbl_summary.setText(
            f"<span style='color:{color};'>활성 책상: {active_count}석{warn}</span> | 통로: {aisle_count}칸"
        )

    def _on_apply(self) -> None:
        self._sync_button_states_to_working_grid()
        self.accept()

    def get_layout_result(self) -> Tuple[int, int, Dict[Tuple[int, int], CellState]]:
        """설정된 (rows, cols, 좌표별 CellState 매핑) 튜플을 반환합니다."""
        return (
            self._working_grid.rows,
            self._working_grid.cols,
            self._working_grid.clone_layout_states(),
        )
