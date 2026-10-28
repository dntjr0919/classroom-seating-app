"""
교실 자리 배치 프로그램 - 메인 좌석 배치 보드 뷰 (views/seating_view.py)
시각적 책상 카드, 잠금(Pin/Lock) 토글 버튼, 드래그 앤 드롭 및 클릭 맞바꾸기(Swap),
우클릭 사전 학생 지정 메뉴, 슬롯머신 룰렛 연출 및 라이트/다크 테마를 제공합니다.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QMimeData, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QDrag, QFont, QMouseEvent, QPixmap, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models import AnimationSpeed, CellState, ClassroomGrid, Gender, Seat, Student
from .theme_manager import ThemeManager


MIME_SEAT_COORD = "application/x-classroom-seat-coord"


class DeskCardWidget(QFrame):
    """
    교실 격자의 개별 셀(활성 책상 / 통로 / 비활성)을 표현하는 카드 위젯.
    - 활성 책상일 때: 좌표 표시, 잠금(Pin) 토글 버튼, 배정 학생 '[번호] 이름' 표시
    - 클릭 선택 또는 드래그 앤 드롭으로 두 좌석 간 학생 맞바꾸기(Swap) 지원
    - 우클릭 컨텍스트 메뉴를 통한 특정 학생 직접 배정(Pre-set) 지원
    """

    lock_toggled = pyqtSignal(int, int)                  # (row, col)
    desk_clicked = pyqtSignal(int, int)                  # (row, col)
    swap_requested = pyqtSignal(int, int, int, int)      # (from_r, from_c, to_r, to_c)
    preset_student_requested = pyqtSignal(int, int)      # (row, col)
    clear_seat_requested = pyqtSignal(int, int)          # (row, col)

    def __init__(
        self,
        seat: Seat,
        is_selected: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.seat = seat
        self.is_selected = is_selected
        self._is_shuffling: bool = False
        self._interaction_locked: bool = False
        self._drag_start_pos: Optional[QPoint] = None
        self._last_rendered_size: Optional[Tuple[int, int]] = None

        self.setMinimumSize(116, 78)
        self.resize(116, 78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(self.seat.is_active_desk)
        self._init_ui()
        self.refresh_card()

    def set_interaction_locked(self, locked: bool) -> None:
        """애니메이션 진행 중 핀 버튼/우클릭/드래그 조작을 잠급니다."""
        self._interaction_locked = locked
        if hasattr(self, "btn_pin"):
            self.btn_pin.setEnabled(not locked)

    def _on_pin_clicked(self) -> None:
        if self._interaction_locked or self._is_shuffling:
            return
        self.lock_toggled.emit(self.seat.row, self.seat.col)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 5)
        layout.setSpacing(2)

        if self.seat.state == CellState.ACTIVE:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            # 상단 바: 좌석 좌표 + 고정(Pin) 정사각형 아이콘 토글 버튼
            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(4)

            self.lbl_coord = QLabel(self.seat.coordinate_label())
            top_row.addWidget(self.lbl_coord)
            top_row.addStretch(1)

            self.btn_pin = QPushButton()
            self.btn_pin.setFixedSize(26, 26)
            self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_pin.clicked.connect(self._on_pin_clicked)
            top_row.addWidget(self.btn_pin)
            layout.addLayout(top_row)

            # 중앙: 학생 이름 표시 (교실 TV/프로젝터 가독성 강화)
            self.lbl_student = QLabel()
            self.lbl_student.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_student.setWordWrap(False)
            layout.addWidget(self.lbl_student, stretch=1)

            # 하단: 번호 · 성별 간결 표시 (또는 빈 좌석 안내)
            self.lbl_sub = QLabel()
            self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.lbl_sub)

        elif self.seat.state == CellState.AISLE:
            # 복도(통로)는 학생 책상과 동일한 비율로 확장되어 자연스러운 교실 열 간격을 유지
            self.setMinimumSize(116, 78)
            lbl = QLabel("")
            layout.addWidget(lbl)

        else:
            # 비활성 영역 (책상과 동일한 크기로 스케일링)
            self.setMinimumSize(116, 78)
            self.lbl_disabled = QLabel("비활성")
            self.lbl_disabled.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.lbl_disabled)

    def refresh_card(self) -> None:
        """좌석 상태(Empty, Assigned, Locked, Selected) 및 현재 테마에 따라 스타일을 업데이트합니다."""
        self._is_shuffling = False
        self._last_rendered_size = None  # 상태 변경 시 무조건 재적용
        is_dark = ThemeManager.is_dark()

        if self.seat.state == CellState.AISLE:
            self.setStyleSheet(
                "QFrame { background-color: transparent; border: none; }"
            )
            return

        if self.seat.state == CellState.DISABLED:
            bg_dis = "#1E293B" if is_dark else "#F1F5F9"
            bd_dis = "#334155" if is_dark else "#E2E8F0"
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {bg_dis};
                    border: 1px solid {bd_dis};
                    border-radius: 8px;
                }}
                """
            )
            self._update_fonts_and_sizes()
            return

        self.lbl_coord.setText(self.seat.coordinate_label())

        # 활성 책상인 경우 텍스트 및 초기 스타일 구성 후 반응형 폰트/크기 동적 계산
        if self.seat.student is not None:
            st = self.seat.student
            main_text = st.name if st.name else f"{st.number}번"
            self.lbl_student.setText(main_text)

            # 번호·성별 간결 표시 (이름 가독성을 방해하지 않도록 보조 줄에 배치)
            sub_parts: List[str] = []
            if st.number and st.name:
                sub_parts.append(f"{st.number}번")
            if st.gender == Gender.MALE:
                sub_parts.append("남")
            elif st.gender == Gender.FEMALE:
                sub_parts.append("여")

            self.lbl_sub.setText(" · ".join(sub_parts) if sub_parts else "")
        else:
            self.lbl_student.setText("(빈 좌석)")
            self.lbl_sub.setText("우클릭 학생 지정")

        # 카드 배경 및 테두리 결정 (레이아웃 흔들림 방지를 위해 모든 활성 카드 테두리 두께를 2px로 통일)
        if is_dark:
            if self.is_selected:
                bg = "#1E3A8A"
                border = "2px solid #60A5FA"
            elif self.seat.is_locked:
                bg = "#451A03"
                border = "2px solid #F59E0B"
            elif self.seat.student is not None:
                bg = "#1E293B"
                border = "2px solid #64748B"
            else:
                bg = "#0F172A"
                border = "2px dashed #334155"
            hover_border = "#60A5FA"
        else:
            if self.is_selected:
                bg = "#DBEAFE"
                border = "2px solid #2563EB"
            elif self.seat.is_locked:
                bg = "#FEF3C7"
                border = "2px solid #D97706"
            elif self.seat.student is not None:
                bg = "#FFFFFF"
                border = "2px solid #334155"
            else:
                bg = "#F8FAFC"
                border = "2px dashed #94A3B8"
            hover_border = "#2563EB"

        self.setStyleSheet(
            f"""
            DeskCardWidget {{
                background-color: {bg};
                border: {border};
                border-radius: 8px;
            }}
            DeskCardWidget:hover {{
                border: 2px solid {hover_border};
            }}
            """
        )

        # 현재 카드 크기에 맞춘 폰트 및 핀 크기 동적 계산 적용
        self._update_fonts_and_sizes()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """창 또는 카드의 크기가 변경될 때 폰트 크기를 반응형으로 재계산합니다."""
        super().resizeEvent(event)
        self._update_fonts_and_sizes()

    def _update_fonts_and_sizes(self) -> None:
        """카드의 현재 너비·높이에 비례하여 학생 이름, 보조 텍스트, 좌표, 핀 버튼 크기를 동적으로 조정합니다."""
        w = self.width() if (self.parent() is not None and self.width() > 10) else 116
        h = self.height() if (self.parent() is not None and self.height() > 10) else 78

        # 동일한 크기일 때 불필요한 재계산 방지
        if self._last_rendered_size == (w, h):
            return
        self._last_rendered_size = (w, h)

        is_dark = ThemeManager.is_dark()

        # 카드의 폭과 높이를 고려한 기준 폰트 크기 (기본 약 18px, 최대 36px)
        scale_by_h = h * 0.23
        scale_by_w = w * 0.15
        base_px = max(15, min(36, int(min(scale_by_h, scale_by_w))))

        if self.seat.state == CellState.DISABLED:
            if hasattr(self, "lbl_disabled"):
                dis_px = max(11, min(24, int(base_px * 0.65)))
                dis_font = QFont("맑은 고딕")
                dis_font.setPixelSize(dis_px)
                dis_font.setWeight(QFont.Weight.Medium)
                self.lbl_disabled.setFont(dis_font)
                dis_color = "#64748B" if is_dark else "#94A3B8"
                self.lbl_disabled.setStyleSheet(
                    f"color: {dis_color}; border: none; background: transparent;"
                )
            return

        if not self.seat.is_active_desk:
            return

        coord_px = max(9, min(14, int(base_px * 0.52)))
        pin_size = max(26, min(36, int(h * 0.33)))
        pin_font_px = max(12, min(17, int(pin_size * 0.48)))

        coord_font = QFont("맑은 고딕")
        coord_font.setPixelSize(coord_px)
        coord_font.setWeight(QFont.Weight.DemiBold)
        self.lbl_coord.setFont(coord_font)
        coord_color = "#94A3B8" if is_dark else "#64748B"
        self.lbl_coord.setStyleSheet(
            f"color: {coord_color}; border: none; background: transparent;"
        )

        if self.btn_pin.width() != pin_size or self.btn_pin.height() != pin_size:
            self.btn_pin.setFixedSize(pin_size, pin_size)
        pin_font = QFont("맑은 고딕")
        pin_font.setPixelSize(pin_font_px)
        self.btn_pin.setFont(pin_font)

        # 핀 버튼 스타일
        if self.seat.is_locked:
            self.btn_pin.setText("📌")
            self.btn_pin.setToolTip("현재: 고정됨 (클릭하여 고정 해제)")
            self.btn_pin.setStyleSheet(
                """
                QPushButton {
                    background-color: #F59E0B;
                    color: #FFFFFF;
                    border: 1px solid #D97706;
                    border-radius: 5px;
                    padding: 0px;
                }
                QPushButton:hover { background-color: #D97706; }
                """
            )
        else:
            self.btn_pin.setText("🔓")
            self.btn_pin.setToolTip("현재: 고정 해제됨 (클릭하여 이 좌석 고정)")
            if is_dark:
                self.btn_pin.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #334155;
                        color: #94A3B8;
                        border: 1px solid #475569;
                        border-radius: 5px;
                        padding: 0px;
                    }
                    QPushButton:hover { background-color: #475569; color: #F8FAFC; }
                    """
                )
            else:
                self.btn_pin.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #E2E8F0;
                        color: #64748B;
                        border: 1px solid #CBD5E1;
                        border-radius: 5px;
                        padding: 0px;
                    }
                    QPushButton:hover { background-color: #CBD5E1; color: #1E293B; }
                    """
                )

        if self._is_shuffling:
            # 슬롯머신 롤링 중인 좌석:
            # 학생이 배정될 좌석(seat.student is not None)은 이전 상태가 빈 좌석이었더라도
            # 무조건 처음부터 크고 굵은 글씨(base_px)로 롤링 애니메이션을 표시합니다.
            sub_px = max(10, min(15, int(base_px * 0.56)))
            sub_font = QFont("맑은 고딕")
            sub_font.setPixelSize(sub_px)
            sub_font.setWeight(QFont.Weight.DemiBold)
            self.lbl_sub.setFont(sub_font)
            shuffle_sub_color = "#C4B5FD" if is_dark else "#7C3AED"
            self.lbl_sub.setStyleSheet(
                f"color: {shuffle_sub_color}; border: none; background: transparent;"
            )

            if self.seat.student is not None:
                st_font = QFont("맑은 고딕")
                st_font.setPixelSize(base_px)
                st_font.setWeight(QFont.Weight.ExtraBold)
                st_font.setItalic(False)
                self.lbl_student.setFont(st_font)
                st_color = "#F8FAFC" if is_dark else "#0F172A"
                self.lbl_student.setStyleSheet(
                    f"color: {st_color}; border: none; background: transparent;"
                )
            else:
                empty_px = max(12, min(20, int(base_px * 0.70)))
                empty_font = QFont("맑은 고딕")
                empty_font.setPixelSize(empty_px)
                empty_font.setWeight(QFont.Weight.Normal)
                empty_font.setItalic(True)
                self.lbl_student.setFont(empty_font)
                empty_color = "#64748B" if is_dark else "#94A3B8"
                self.lbl_student.setStyleSheet(
                    f"color: {empty_color}; border: none; background: transparent;"
                )
            return

        if self.seat.student is not None:
            st = self.seat.student
            actual_text = st.name if st.name else f"{st.number}번"
            name_len = len(actual_text)
            if name_len <= 3:
                student_px = base_px
            elif name_len <= 4:
                student_px = max(14, int(base_px * 0.88))
            elif name_len <= 6:
                student_px = max(13, int(base_px * 0.74))
            else:
                student_px = max(12, int(base_px * 0.62))

            sub_px = max(10, min(16, int(base_px * 0.58)))

            st_font = QFont("맑은 고딕")
            st_font.setPixelSize(student_px)
            st_font.setWeight(QFont.Weight.ExtraBold)
            st_font.setItalic(False)
            self.lbl_student.setFont(st_font)

            st_color = "#F8FAFC" if is_dark else "#0F172A"
            self.lbl_student.setStyleSheet(
                f"color: {st_color}; border: none; background: transparent;"
            )

            sub_font = QFont("맑은 고딕")
            sub_font.setPixelSize(sub_px)
            sub_font.setWeight(QFont.Weight.DemiBold)
            self.lbl_sub.setFont(sub_font)

            if is_dark:
                sub_color = "#CBD5E1"
                if st.gender == Gender.MALE:
                    sub_color = "#60A5FA"
                elif st.gender == Gender.FEMALE:
                    sub_color = "#F472B6"
            else:
                sub_color = "#475569"
                if st.gender == Gender.MALE:
                    sub_color = "#2563EB"
                elif st.gender == Gender.FEMALE:
                    sub_color = "#DB2777"

            self.lbl_sub.setStyleSheet(
                f"color: {sub_color}; border: none; background: transparent;"
            )
        else:
            empty_px = max(12, min(20, int(base_px * 0.70)))
            empty_sub_px = max(9, min(13, int(base_px * 0.50)))

            empty_font = QFont("맑은 고딕")
            empty_font.setPixelSize(empty_px)
            empty_font.setWeight(QFont.Weight.Normal)
            empty_font.setItalic(True)
            self.lbl_student.setFont(empty_font)

            empty_sub_font = QFont("맑은 고딕")
            empty_sub_font.setPixelSize(empty_sub_px)
            empty_sub_font.setWeight(QFont.Weight.Normal)
            self.lbl_sub.setFont(empty_sub_font)

            empty_color = "#64748B" if is_dark else "#94A3B8"
            empty_sub_color = "#475569" if is_dark else "#CBD5E1"
            self.lbl_student.setStyleSheet(
                f"color: {empty_color}; border: none; background: transparent;"
            )
            self.lbl_sub.setStyleSheet(
                f"color: {empty_sub_color}; border: none; background: transparent;"
            )

    def enter_shuffle_mode(self) -> None:
        """
        슬롯머신 셔플 시작 시 카드 스타일을 보라색 점선 테두리로 전환하고,
        학생이 배정된 모든 좌석의 글씨 크기를 즉시 크고 굵은 글씨로 동기화합니다.
        """
        if not self.seat.is_active_desk:
            return
        self._is_shuffling = True
        self._last_rendered_size = None
        is_dark = ThemeManager.is_dark()

        self.lbl_sub.setText("🎲 롤링 중...")
        bg_shuf = "#2E1065" if is_dark else "#EDE9FE"
        bd_shuf = "#A78BFA" if is_dark else "#8B5CF6"
        self.setStyleSheet(
            f"""
            DeskCardWidget {{
                background-color: {bg_shuf};
                border: 2px dashed {bd_shuf};
                border-radius: 8px;
            }}
            """
        )
        # 이전 상태가 (빈 좌석)이었더라도 즉시 현재 배치의 큰 폰트로 갱신
        self._update_fonts_and_sizes()

    def show_shuffle_tick(self, temp_name: str) -> None:
        """초고속 롤링 틱: 렌더링 부하/크래시 방지를 위해 CSS 재파싱 없이 순수 텍스트만 초경량 교체"""
        if not self.seat.is_active_desk or not self._is_shuffling:
            return
        self.lbl_student.setText(temp_name)

    def show_lock_in_effect(self, student: Optional[Student]) -> None:
        """슬롯머신이 해당 좌석에서 멈추며 최종 학생으로 확정될 때 골드 하이라이트를 적용합니다."""
        self._is_shuffling = False
        self.seat.student = student
        self.refresh_card()
        is_dark = ThemeManager.is_dark()
        bg_lock = "#451A03" if is_dark else "#FEF3C7"
        bd_lock = "#F59E0B" if is_dark else "#D97706"
        # 행 높이 흔들림(resizeEvent 연쇄 발생)을 막기 위해 동일한 2px 테두리 두께 유지
        self.setStyleSheet(
            f"""
            DeskCardWidget {{
                background-color: {bg_lock};
                border: 2px solid {bd_lock};
                border-radius: 8px;
            }}
            """
        )

    # ------------------------------------------------------------------
    # 마우스 클릭, 우클릭 메뉴, 드래그 앤 드롭 이벤트 처리
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        if event is None or not self.seat.is_active_desk:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        if (
            event is None
            or not self.seat.is_active_desk
            or self._interaction_locked
            or self._is_shuffling
            or self._drag_start_pos is None
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            return

        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        # 드래그 시작
        self._drag_start_pos = None
        drag = QDrag(self)
        mime_data = QMimeData()
        coord_bytes = f"{self.seat.row},{self.seat.col}".encode("utf-8")
        mime_data.setData(MIME_SEAT_COORD, coord_bytes)
        drag.setMimeData(mime_data)

        pixmap: QPixmap = self.grab()
        drag.setPixmap(pixmap.scaled(120, 76, Qt.AspectRatioMode.KeepAspectRatio))
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        if event is not None and self.seat.is_active_desk:
            if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos is not None:
                self._drag_start_pos = None
                self.desk_clicked.emit(self.seat.row, self.seat.col)
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        if (
            event is None
            or not self.seat.is_active_desk
            or self._interaction_locked
            or self._is_shuffling
        ):
            return
        menu = QMenu(self)
        act_assign = QAction("👤 이 좌석에 학생 직접 지정(고정)...", self)
        act_assign.triggered.connect(
            lambda: self.preset_student_requested.emit(self.seat.row, self.seat.col)
        )
        menu.addAction(act_assign)

        lock_label = "🔓 좌석 고정(Pin) 해제" if self.seat.is_locked else "📌 좌석 고정(Pin) 설정"
        act_lock = QAction(lock_label, self)
        act_lock.triggered.connect(
            lambda: self.lock_toggled.emit(self.seat.row, self.seat.col)
        )
        menu.addAction(act_lock)

        if self.seat.student is not None:
            menu.addSeparator()
            act_clear = QAction("🗑 이 좌석 비우기", self)
            act_clear.triggered.connect(
                lambda: self.clear_seat_requested.emit(self.seat.row, self.seat.col)
            )
            menu.addAction(act_clear)

        menu.exec(event.globalPos())

    def dragEnterEvent(self, event) -> None:
        if (
            event is not None
            and self.seat.is_active_desk
            and not self._interaction_locked
            and not self._is_shuffling
            and event.mimeData() is not None
            and event.mimeData().hasFormat(MIME_SEAT_COORD)
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if (
            event is None
            or not self.seat.is_active_desk
            or self._interaction_locked
            or self._is_shuffling
            or event.mimeData() is None
            or not event.mimeData().hasFormat(MIME_SEAT_COORD)
        ):
            return
        raw = bytes(event.mimeData().data(MIME_SEAT_COORD)).decode("utf-8")
        try:
            from_r, from_c = [int(x) for x in raw.split(",")]
            to_r, to_c = self.seat.row, self.seat.col
            event.acceptProposedAction()
            if (from_r, from_c) != (to_r, to_c):
                # Windows OLE 드래그 루프가 완전히 종료된 직후 안전하게 스왑 실행
                QTimer.singleShot(
                    0, lambda: self.swap_requested.emit(from_r, from_c, to_r, to_c)
                )
        except ValueError:
            return


class SeatingBoardView(QWidget):
    """
    교탁/칠판 헤더와 전체 N x M 책상 카드 그리드를 표시하고 상호작용을 중계하는 메인 보드 뷰.
    """

    seat_lock_toggled = pyqtSignal(int, int)
    seats_swapped = pyqtSignal(int, int, int, int)
    seat_preset_requested = pyqtSignal(int, int)
    seat_clear_requested = pyqtSignal(int, int)
    animation_finished = pyqtSignal()
    manual_reveal_ready = pyqtSignal(int, int)  # (남은 좌석 수, 전체 공개 좌석 수)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._selected_coord: Optional[Tuple[int, int]] = None
        self._cards: Dict[Tuple[int, int], DeskCardWidget] = {}
        self._grid_signature: Optional[Tuple[int, int, Tuple[Tuple[int, int, CellState], ...]]] = None

        # 슬롯머신 셔플 룰렛 애니메이션 상태 변수 및 단일 타이머 인스턴스
        self._ticker_timer = QTimer(self)
        self._ticker_timer.timeout.connect(self._on_shuffle_ticker_tick)

        self._reveal_timer = QTimer(self)
        self._reveal_timer.timeout.connect(self._reveal_next_automatic)

        self._initial_shuffle_timer = QTimer(self)
        self._initial_shuffle_timer.setSingleShot(True)
        self._initial_shuffle_timer.timeout.connect(self._on_initial_shuffle_done)

        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self.skip_animation)

        self._is_animating: bool = False
        self._is_in_manual_phase: bool = False
        self._pending_grid: Optional[ClassroomGrid] = None
        self._unlocked_coords: List[Tuple[int, int]] = []
        self._unrevealed_queue: List[Tuple[int, int]] = []
        self._revealed_set: set[Tuple[int, int]] = set()
        self._speed: AnimationSpeed = AnimationSpeed.NORMAL
        self._roster_pool: List[str] = []

        self._init_ui()
        self.apply_theme_styles()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 12)
        main_layout.setSpacing(10)

        # 상단 안내 및 교탁 영역
        podium_container = QHBoxLayout()
        podium_container.addStretch(1)

        self.podium_banner = QFrame()
        self.podium_banner.setMinimumWidth(360)
        self.podium_banner.setMaximumWidth(520)
        podium_layout = QVBoxLayout(self.podium_banner)
        podium_layout.setContentsMargins(12, 6, 12, 6)
        self.lbl_podium = QLabel("칠 판 / 교 탁 (앞)")
        self.lbl_podium.setAlignment(Qt.AlignmentFlag.AlignCenter)
        podium_layout.addWidget(self.lbl_podium)

        podium_container.addWidget(self.podium_banner, stretch=2)
        podium_container.addStretch(1)
        main_layout.addLayout(podium_container)

        # 조작 팁 배너
        self.lbl_hint = QLabel(
            "💡 <b>수동 자리 이동:</b> 두 책상을 차례대로 클릭하거나 드래그 앤 드롭하면 자리를 맞바꿉니다. | "
            "<b>고정석 지정:</b> 책상 우클릭으로 특정 학생을 사전 배정하거나 우측 상단 <b>[📌]</b> 아이콘 버튼을 누르세요."
        )
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_hint)

        # 중앙 스크롤 가능한 책상 격자 보드
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.board_container = QWidget()
        self.grid_layout = QGridLayout(self.board_container)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setSpacing(8)

        self.scroll_area.setWidget(self.board_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

    def apply_theme_styles(self) -> None:
        """현재 테마(라이트/다크)에 맞게 보드 배경과 배너, 모든 좌석 카드를 갱신합니다."""
        is_dark = ThemeManager.is_dark()
        podium_bg = "#334155" if is_dark else "#1E293B"
        podium_border = "1px solid #475569" if is_dark else "none"
        self.podium_banner.setStyleSheet(
            f"""
            QFrame {{
                background-color: {podium_bg};
                border: {podium_border};
                border-radius: 8px;
                padding: 8px 24px;
            }}
            """
        )
        self.lbl_podium.setStyleSheet(
            "color: #FFFFFF; font-size: 15px; font-weight: bold; letter-spacing: 3px; border: none; background: transparent;"
        )

        hint_color = "#94A3B8" if is_dark else "#475569"
        self.lbl_hint.setStyleSheet(f"color: {hint_color}; font-size: 12px;")

        board_bg = "#0B1120" if is_dark else "#F1F5F9"
        board_border = "#334155" if is_dark else "#CBD5E1"
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {board_bg}; border: 1px solid {board_border}; border-radius: 10px; }}"
        )
        self.board_container.setStyleSheet(f"background-color: {board_bg};")

        for card in self._cards.values():
            if card._is_shuffling:
                card.enter_shuffle_mode()
            else:
                card.refresh_card()

    def _compute_grid_signature(
        self, grid: ClassroomGrid
    ) -> Tuple[int, int, Tuple[Tuple[int, int, CellState], ...]]:
        return (
            grid.rows,
            grid.cols,
            tuple(
                (r, c, grid.get_seat(r, c).state)
                for r in range(grid.rows)
                for c in range(grid.cols)
            ),
        )

    def render_grid(self, grid: ClassroomGrid) -> None:
        """
        ClassroomGrid 모델 상태를 기반으로 전체 책상 위젯을 렌더링합니다.
        격자 크기와 셀 상태(ACTIVE/AISLE/DISABLED)가 동일하면 기존 위젯을 파괴하지 않고
        제자리(In-place)에서 데이터와 스타일만 갱신하여 메모리 누수 및 크래시를 원천 방지합니다.
        """
        self._stop_all_anim_timers()
        self._is_animating = False
        self._is_in_manual_phase = False

        # 선택된 좌표가 유효 범위를 벗어났으면 초기화
        if self._selected_coord is not None:
            sr, sc = self._selected_coord
            if not (0 <= sr < grid.rows and 0 <= sc < grid.cols) or not grid.get_seat(sr, sc).is_active_desk:
                self._selected_coord = None

        new_sig = self._compute_grid_signature(grid)
        if self._grid_signature == new_sig and len(self._cards) == grid.rows * grid.cols:
            # 기존 카드 위젯 재사용 (위젯 재생성/파괴 0회)
            for (r, c), card in self._cards.items():
                card.seat = grid.get_seat(r, c)
                card.is_selected = (self._selected_coord == (r, c))
                card.set_interaction_locked(False)
                card.refresh_card()
            return

        # 격자 크기나 셀 타입이 변경된 경우에만 위젯 재구성
        self._grid_signature = new_sig
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

        # 기존 행/열의 확장 가중치 초기화
        for r in range(self.grid_layout.rowCount()):
            self.grid_layout.setRowStretch(r, 0)
        for c in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(c, 0)

        self._cards.clear()

        for r in range(grid.rows):
            self.grid_layout.setRowStretch(r, 1)
            for c in range(grid.cols):
                seat = grid.get_seat(r, c)
                is_sel = self._selected_coord == (r, c)
                card = DeskCardWidget(seat=seat, is_selected=is_sel, parent=self.board_container)
                card.lock_toggled.connect(self.seat_lock_toggled.emit)
                card.desk_clicked.connect(self._on_desk_clicked)
                card.swap_requested.connect(self._on_swap_requested)
                card.preset_student_requested.connect(self.seat_preset_requested.emit)
                card.clear_seat_requested.connect(self.seat_clear_requested.emit)

                self.grid_layout.addWidget(card, r, c)
                self._cards[(r, c)] = card

        for c in range(grid.cols):
            self.grid_layout.setColumnStretch(c, 1)

    def clear_selection(self) -> None:
        self._selected_coord = None

    def _on_desk_clicked(self, row: int, col: int) -> None:
        if self._is_in_manual_phase:
            # 수동 오픈 단계에서는 클릭한 특정 좌석을 즉시 공개
            self.reveal_specific_seat(row, col)
            return

        if self._is_animating:
            # 자동 애니메이션 진행 중에는 자리 선택/스왑 방지
            return

        clicked_coord = (row, col)
        if self._selected_coord is None:
            self._selected_coord = clicked_coord
            if clicked_coord in self._cards:
                self._cards[clicked_coord].is_selected = True
                self._cards[clicked_coord].refresh_card()
        elif self._selected_coord == clicked_coord:
            # 같은 좌석 재클릭 시 선택 해제
            self._selected_coord = None
            if clicked_coord in self._cards:
                self._cards[clicked_coord].is_selected = False
                self._cards[clicked_coord].refresh_card()
        else:
            # 두 번째 좌석 클릭 -> 두 좌석 맞바꾸기 요청
            from_r, from_c = self._selected_coord
            self._selected_coord = None
            self.seats_swapped.emit(from_r, from_c, row, col)

    def _on_swap_requested(self, from_r: int, from_c: int, to_r: int, to_c: int) -> None:
        if self._is_animating:
            return
        self._selected_coord = None
        self.seats_swapped.emit(from_r, from_c, to_r, to_c)

    # ------------------------------------------------------------------
    # 슬롯머신 셔플 룰렛 애니메이션 공개 제어 (1초 전체 셔플 + 자리당 간격/수동 오픈)
    # ------------------------------------------------------------------
    def is_animating(self) -> bool:
        """현재 슬롯머신 애니메이션이 재생 중인지 여부를 반환합니다."""
        return self._is_animating

    def is_in_manual_phase(self) -> bool:
        """현재 수동 오픈 대기 단계인지 여부를 반환합니다."""
        return self._is_in_manual_phase

    def _stop_all_anim_timers(self) -> None:
        """모든 애니메이션 타이머를 안전하게 정지합니다."""
        if self._ticker_timer.isActive():
            self._ticker_timer.stop()
        if self._reveal_timer.isActive():
            self._reveal_timer.stop()
        if self._initial_shuffle_timer.isActive():
            self._initial_shuffle_timer.stop()
        if self._finish_timer.isActive():
            self._finish_timer.stop()

    def start_slot_machine_animation(
        self,
        grid: ClassroomGrid,
        roster: List[Student],
        speed: AnimationSpeed = AnimationSpeed.NORMAL,
        respect_locks: bool = True,
    ) -> None:
        """
        슬롯머신 셔플 룰렛 애니메이션을 구동합니다:
        1. 처음 1초(1000ms): 모든 대상 좌석이 가볍고 안전하게 고속 롤링
        2. 이후:
           - 빠르게/보통/느리게: 각 자리당 간격(0.3s/0.5s/1.0s)마다 순차 확정
           - 수동 오픈: 스페이스바를 누르거나 좌석을 클릭할 때마다 1자리씩 확정
        """
        self._stop_all_anim_timers()

        # 만약 격자 구조가 아직 생성되지 않았거나 변경되었다면 먼저 동기화
        if self._grid_signature != self._compute_grid_signature(grid) or len(self._cards) != grid.rows * grid.cols:
            self.render_grid(grid)

        self._is_animating = True
        self._is_in_manual_phase = False
        self._pending_grid = grid
        self._speed = speed
        self._selected_coord = None

        # 모든 카드에 최신 Seat 참조 반영 및 애니메이션 중 핀/드래그/우클릭 잠금
        for (r, c), card in self._cards.items():
            card.seat = grid.get_seat(r, c)
            card.is_selected = False
            card.set_interaction_locked(True)

        # 셔플 대상 좌표 목록 (활성 책상이면서 고정 유지 대상이 아닌 좌석)
        self._unlocked_coords = [
            (seat.row, seat.col)
            for seat in grid.active_desks()
            if not (respect_locks and seat.is_locked)
        ]

        if not self._unlocked_coords:
            # 고정석 외에 배치할 좌석이 없으면 즉시 완료
            self._is_animating = False
            for card in self._cards.values():
                card.set_interaction_locked(False)
            self.render_grid(grid)
            self.animation_finished.emit()
            return

        # 학생 이름 풀 준비
        self._roster_pool = [s.name if s.name else s.number for s in roster if s.name or s.number]
        if not self._roster_pool:
            self._roster_pool = ["학생"]

        # 모든 대상 카드에 셔플 스타일 및 큰 폰트 즉시 적용 (초기화 직후에도 모든 배정 좌석이 큰 글씨로 시작)
        for coord in self._unlocked_coords:
            card = self._cards.get(coord)
            if card:
                card.enter_shuffle_mode()
                card.show_shuffle_tick(random.choice(self._roster_pool))

        # 앞자리부터 차례대로 멈추도록 행/열 기준 정렬
        sorted_coords = sorted(self._unlocked_coords, key=lambda rc: (rc[0], rc[1]))
        self._unrevealed_queue = list(sorted_coords)
        self._revealed_set = set()

        # 1. 고속 글자 롤링 타이머 (안정적인 50ms 간격)
        self._ticker_timer.start(50)

        # 2. 처음 1초(1000ms) 초기 셔플 완료 타이머
        self._initial_shuffle_timer.start(speed.initial_shuffle_ms)

    def _on_shuffle_ticker_tick(self) -> None:
        """아직 확정되지 않은 모든 좌석에 무작위 학생 이름을 초경량 교체합니다."""
        if not self._is_animating:
            return
        for coord in self._unlocked_coords:
            if coord not in self._revealed_set:
                card = self._cards.get(coord)
                if card:
                    rand_name = random.choice(self._roster_pool)
                    card.show_shuffle_tick(rand_name)

    def _on_initial_shuffle_done(self) -> None:
        """처음 1초간의 전체 슬롯머신 셔플이 끝나고 순차/수동 확정 단계로 진입합니다."""
        if not self._is_animating:
            return

        if self._speed == AnimationSpeed.MANUAL:
            # 수동 모드: 스페이스바 또는 클릭 대기
            self._is_in_manual_phase = True
            self.manual_reveal_ready.emit(len(self._unrevealed_queue), len(self._unlocked_coords))
        else:
            # 자동 모드: 설정된 간격(0.3s/0.5s/1.0s)으로 1자리씩 확정 시작
            self._reveal_next_automatic()
            if self._is_animating and self._unrevealed_queue:
                self._reveal_timer.start(self._speed.per_seat_ms)

    def _reveal_next_automatic(self) -> None:
        """자동 모드: 큐에서 다음 좌석을 꺼내 확정합니다."""
        if not self._is_animating or not self._unrevealed_queue:
            return
        next_coord = self._unrevealed_queue.pop(0)
        self._reveal_coord(next_coord)

    def reveal_next_manual(self) -> bool:
        """수동 모드: 스페이스바/엔터 키 입력 시 다음 좌석을 1개 확정합니다."""
        if not self._is_animating or not self._is_in_manual_phase or not self._unrevealed_queue:
            return False
        next_coord = self._unrevealed_queue.pop(0)
        self._reveal_coord(next_coord)
        return True

    def reveal_specific_seat(self, row: int, col: int) -> bool:
        """수동 모드: 마우스로 특정 좌석 카드를 클릭했을 때 해당 좌석을 즉시 확정합니다."""
        coord = (row, col)
        if not self._is_animating or not self._is_in_manual_phase or coord not in self._unrevealed_queue:
            return False
        self._unrevealed_queue.remove(coord)
        self._reveal_coord(coord)
        return True

    def _reveal_coord(self, coord: Tuple[int, int]) -> None:
        """지정된 좌석을 최종 확정 상태로 전환합니다."""
        self._revealed_set.add(coord)
        card = self._cards.get(coord)
        if card and self._pending_grid:
            target_seat = self._pending_grid.get_seat(coord[0], coord[1])
            card.show_lock_in_effect(target_seat.student)

        # 모든 좌석이 공개되었는지 확인
        if len(self._unrevealed_queue) == 0:
            self._stop_all_anim_timers()
            self._is_in_manual_phase = False
            # 마지막 좌석의 플래시 효과를 보여준 뒤 350ms 후 완료
            self._finish_timer.start(350)
        elif self._is_in_manual_phase:
            self.manual_reveal_ready.emit(len(self._unrevealed_queue), len(self._unlocked_coords))

    def skip_animation(self) -> None:
        """애니메이션을 즉시 중단하고 최종 완성 상태로 즉시 전환합니다."""
        self._stop_all_anim_timers()

        self._is_animating = False
        self._is_in_manual_phase = False
        self._pending_grid = None

        for card in self._cards.values():
            card.set_interaction_locked(False)

        # animation_finished 시그널이 MainWindow._on_placement_animation_finished -> _refresh_all을 호출하여
        # 중복 렌더링 없이 정확히 1회 제자리(In-place) 갱신을 수행합니다.
        self.animation_finished.emit()
