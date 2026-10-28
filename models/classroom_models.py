"""
교실 자리 배치 프로그램 - 데이터 모델 모듈 (models/classroom_models.py)
Student(학생), Seat(좌석), ClassroomGrid(교실 격자 레이아웃) 클래스를 정의합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Gender(str, Enum):
    """학생 성별 열거형"""
    MALE = "M"
    FEMALE = "F"
    NONE = ""

    @classmethod
    def from_str(cls, value: Optional[str]) -> "Gender":
        """다양한 한/영 성별 표기 문자열을 표준 Gender 값으로 변환합니다."""
        if not value:
            return cls.NONE
        cleaned = str(value).strip().upper()
        if cleaned in ("M", "남", "남자", "남학생", "MALE", "BOY"):
            return cls.MALE
        if cleaned in ("F", "여", "여자", "여학생", "FEMALE", "GIRL"):
            return cls.FEMALE
        return cls.NONE

    def display_kr(self) -> str:
        """화면 표시용 한글 성별 문자열을 반환합니다."""
        if self == Gender.MALE:
            return "남"
        if self == Gender.FEMALE:
            return "여"
        return "-"


class CellState(str, Enum):
    """교실 격자 셀의 상태 열거형"""
    ACTIVE = "ACTIVE"       # 활성 책상 (학생 배치 가능)
    AISLE = "AISLE"         # 복도 / 빈 통로 공간
    DISABLED = "DISABLED"   # 비활성 공간 (기둥, 사물함 등 배치 불가 영역)

    def next_state(self) -> "CellState":
        """클릭 시 순환할 다음 셀 상태를 반환합니다 (ACTIVE -> AISLE -> DISABLED -> ACTIVE)."""
        order = [CellState.ACTIVE, CellState.AISLE, CellState.DISABLED]
        idx = order.index(self)
        return order[(idx + 1) % len(order)]

    def display_kr(self) -> str:
        """화면 표시용 한글 상태명을 반환합니다."""
        mapping = {
            CellState.ACTIVE: "활성 책상",
            CellState.AISLE: "통로(복도)",
            CellState.DISABLED: "비활성",
        }
        return mapping.get(self, "활성 책상")


class PresetType(str, Enum):
    """책상 배치 프리셋 유형"""
    PAIRS = "PAIRS"         # 짝꿍형 (2열 1조 + 통로)
    EXAM = "EXAM"           # 시험 대형 (1열 단독 배치 + 통로)
    CLUSTER = "CLUSTER"     # 모둠형 (4인 2x2 클러스터 + 가로/세로 통로)
    ALL_ACTIVE = "ALL_ACTIVE"  # 전체 활성 책상


class PlacementMode(str, Enum):
    """자리 배치 방식 열거형 (5가지 배치 모드)"""
    RANDOM = "RANDOM"                         # 1. 기본 무작위 배치
    MIXED_GENDER_PAIR = "MIXED_GENDER_PAIR"   # 2. 남녀 이성 짝꿍 배치
    SAME_GENDER_PAIR = "SAME_GENDER_PAIR"     # 3. 동성 짝꿍 배치
    NUMBER_ORDER = "NUMBER_ORDER"             # 4. 번호순 자동 배치
    FRONT_BACK_CROSS = "FRONT_BACK_CROSS"     # 5. 앞뒤 구역 교차 배치

    def display_kr(self) -> str:
        mapping = {
            PlacementMode.RANDOM: "기본 무작위 배치",
            PlacementMode.MIXED_GENDER_PAIR: "남녀 이성 짝꿍 배치",
            PlacementMode.SAME_GENDER_PAIR: "동성 짝꿍 배치",
            PlacementMode.NUMBER_ORDER: "번호순 자동 배치",
            PlacementMode.FRONT_BACK_CROSS: "앞뒤 구역 교차 배치",
        }
        return mapping.get(self, "기본 무작위 배치")


class OrderDirection(str, Enum):
    """번호순 자동 배치 시 진행 방향 열거형"""
    ROW_FIRST = "ROW_FIRST"   # 가로 우선 (앞줄 왼쪽 -> 오른쪽)
    COL_FIRST = "COL_FIRST"   # 세로 우선 (왼쪽 열 앞 -> 뒤)

    def display_kr(self) -> str:
        mapping = {
            OrderDirection.ROW_FIRST: "가로 우선 (행 순서)",
            OrderDirection.COL_FIRST: "세로 우선 (열 순서)",
        }
        return mapping.get(self, "가로 우선 (행 순서)")


class ViewPerspective(str, Enum):
    """인쇄 및 내보내기 시점 방향 열거형"""
    STUDENT_VIEW = "STUDENT_VIEW"  # 게시용 (학생 시점: 교탁이 위쪽/앞쪽)
    TEACHER_VIEW = "TEACHER_VIEW"  # 교사용 (교사 시점: 교탁이 아래쪽/앞쪽, 좌석 180도 회전)

    def display_kr(self) -> str:
        if self == ViewPerspective.TEACHER_VIEW:
            return "교사용 (교탁 아래)"
        return "게시용 (교탁 위)"


class AnimationSpeed(str, Enum):
    """슬롯머신 셔플 연출 공개 간격 및 모드 열거형"""
    FAST = "FAST"        # 자리당 0.3초 간격
    NORMAL = "NORMAL"    # 자리당 0.5초 간격 (기본값)
    SLOW = "SLOW"        # 자리당 1.0초 간격
    MANUAL = "MANUAL"    # 수동 오픈 (스페이스바 / 클릭)

    def display_kr(self) -> str:
        if self == AnimationSpeed.FAST:
            return "⚡ 빠르게 (자리당 0.3초)"
        elif self == AnimationSpeed.SLOW:
            return "🐢 느리게 (자리당 1.0초)"
        elif self == AnimationSpeed.MANUAL:
            return "🖐 수동 오픈 (Space / 클릭)"
        return "⏱ 보통 (자리당 0.5초)"

    @property
    def per_seat_ms(self) -> int:
        """각 좌석 확정 사이의 대기 간격(밀리초)"""
        if self == AnimationSpeed.FAST:
            return 300
        elif self == AnimationSpeed.SLOW:
            return 1000
        elif self == AnimationSpeed.MANUAL:
            return 0
        return 500

    @property
    def initial_shuffle_ms(self) -> int:
        """처음 전체 슬롯머신 셔플 지속 시간(1.0초 = 1000ms)"""
        return 1000

    @property
    def ticker_interval_ms(self) -> int:
        """글자 롤링 틱 간격 (밀리초)"""
        return 40


class ThemeMode(str, Enum):
    """화면 테마 모드 열거형 (라이트 / 다크 / 시스템 설정 연동)"""
    LIGHT = "LIGHT"
    DARK = "DARK"
    SYSTEM = "SYSTEM"

    def display_kr(self) -> str:
        if self == ThemeMode.DARK:
            return "🌙 다크 모드"
        elif self == ThemeMode.SYSTEM:
            return "💻 시스템 설정 연동"
        return "☀️ 라이트 모드"


@dataclass
class Student:
    """
    학생 정보를 담는 데이터 모델.
    번호(number)와 이름(name) 중 최소 하나는 반드시 존재해야 합니다.
    """
    number: str = ""
    name: str = ""
    gender: Gender = Gender.NONE
    student_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.number = str(self.number).strip() if self.number is not None else ""
        self.name = str(self.name).strip() if self.name is not None else ""
        if not isinstance(self.gender, Gender):
            self.gender = Gender.from_str(str(self.gender))

        if not self.is_valid():
            raise ValueError("학생 데이터에는 '번호' 또는 '이름' 중 최소 한 가지가 입력되어야 합니다.")

        # 고유 식별자 생성 (번호와 이름 조합)
        self.student_id = f"{self.number}:{self.name}"

    def is_valid(self) -> bool:
        """번호 또는 이름 중 최소 하나가 존재하는지 검증합니다."""
        return bool(self.number or self.name)

    def display_label(self) -> str:
        """책상 카드 및 엑셀 셀에 표시할 '[번호] 이름' 형식 문자열을 반환합니다."""
        if self.number and self.name:
            return f"[{self.number}] {self.name}"
        if self.number:
            return f"[{self.number}]"
        return self.name

    def sort_key(self) -> Tuple[int, str, str]:
        """번호순(숫자 우선) 및 가나다순 정렬을 위한 키를 반환합니다."""
        try:
            num_val = int(self.number)
            return (0, f"{num_val:06d}", self.name)
        except ValueError:
            return (1, self.number, self.name)


@dataclass
class Seat:
    """
    교실 격자 내 개별 셀(좌석/통로/비활성)의 상태를 나타내는 모델.
    """
    row: int
    col: int
    state: CellState = CellState.ACTIVE
    student: Optional[Student] = None
    is_locked: bool = False

    @property
    def coordinate(self) -> Tuple[int, int]:
        """0-기반 (행, 열) 좌표를 반환합니다."""
        return (self.row, self.col)

    def coordinate_label(self) -> str:
        """사용자 친화적인 1-기반 'R행 C열' 문자열을 반환합니다."""
        return f"{self.row + 1}행 {self.col + 1}열"

    @property
    def is_active_desk(self) -> bool:
        """현재 셀이 학생 배치가 가능한 활성 책상인지 여부를 반환합니다."""
        return self.state == CellState.ACTIVE

    @property
    def is_empty(self) -> bool:
        """활성 책상이면서 학생이 아직 배정되지 않았는지 여부를 반환합니다."""
        return self.is_active_desk and (self.student is None)

    def set_state(self, new_state: CellState) -> None:
        """
        셀의 상태를 변경합니다.
        비활성 또는 통로로 변경될 경우 배정된 학생과 잠금 상태를 해제합니다.
        """
        self.state = new_state
        if new_state != CellState.ACTIVE:
            self.student = None
            self.is_locked = False

    def clear_assignment(self, force: bool = False) -> None:
        """
        배정된 학생을 비웁니다.
        force=False이면 잠금(Pin) 상태인 좌석은 유지합니다.
        """
        if force or not self.is_locked:
            self.student = None
            if force:
                self.is_locked = False


class ClassroomGrid:
    """
    교실 전체 N x M 좌석 격자를 관리하는 모델 클래스.
    """

    def __init__(self, rows: int = 6, cols: int = 8) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("행과 열의 크기는 최소 1 이상이어야 합니다.")
        self.rows: int = rows
        self.cols: int = cols
        self._seats: Dict[Tuple[int, int], Seat] = {}
        self._init_grid()

    def _init_grid(self) -> None:
        """기본 격자를 생성합니다."""
        self._seats.clear()
        for r in range(self.rows):
            for c in range(self.cols):
                self._seats[(r, c)] = Seat(row=r, col=c, state=CellState.ACTIVE)

    def resize(self, new_rows: int, new_cols: int) -> None:
        """
        격자 크기를 변경하되, 기존 좌표 범위 내의 좌석 상태와 배정 정보를 보존합니다.
        """
        if new_rows < 1 or new_cols < 1:
            raise ValueError("행과 열의 크기는 최소 1 이상이어야 합니다.")

        updated_seats: Dict[Tuple[int, int], Seat] = {}
        for r in range(new_rows):
            for c in range(new_cols):
                if (r, c) in self._seats:
                    updated_seats[(r, c)] = self._seats[(r, c)]
                else:
                    updated_seats[(r, c)] = Seat(row=r, col=c, state=CellState.ACTIVE)

        self.rows = new_rows
        self.cols = new_cols
        self._seats = updated_seats

    def get_seat(self, row: int, col: int) -> Seat:
        """특정 (row, col) 위치의 Seat 객체를 반환합니다."""
        if (row, col) not in self._seats:
            raise IndexError(f"유효하지 않은 좌석 좌표입니다: ({row}, {col})")
        return self._seats[(row, col)]

    def all_seats(self) -> List[Seat]:
        """행 우선 순서로 모든 Seat 리스트를 반환합니다."""
        return [
            self._seats[(r, c)]
            for r in range(self.rows)
            for c in range(self.cols)
        ]

    def active_desks(self) -> List[Seat]:
        """현재 활성화된 책상(CellState.ACTIVE) 목록만 반환합니다."""
        return [s for s in self.all_seats() if s.is_active_desk]

    def locked_desks(self) -> List[Seat]:
        """활성 책상 중 고정(Pin/Lock)된 좌석 목록을 반환합니다."""
        return [s for s in self.active_desks() if s.is_locked]

    def unlocked_active_desks(self) -> List[Seat]:
        """활성 책상 중 고정되지 않은 좌석 목록을 반환합니다."""
        return [s for s in self.active_desks() if not s.is_locked]

    def assigned_students_map(self) -> Dict[str, Seat]:
        """현재 좌석에 배치된 학생의 student_id -> Seat 매핑을 반환합니다."""
        result: Dict[str, Seat] = {}
        for seat in self.active_desks():
            if seat.student is not None:
                result[seat.student.student_id] = seat
        return result

    def clear_all_assignments(self, keep_locked: bool = True) -> None:
        """
        좌석에 배치된 학생을 초기화합니다.
        keep_locked=True이면 잠금(Pin) 설정된 좌석의 학생은 그대로 유지합니다.
        """
        for seat in self.active_desks():
            seat.clear_assignment(force=not keep_locked)

    def apply_preset(self, preset: PresetType) -> None:
        """
        지정된 프리셋 레이아웃(짝꿍형, 시험 대형, 모둠형, 전체 활성)을 격자에 적용합니다.
        """
        for r in range(self.rows):
            for c in range(self.cols):
                seat = self.get_seat(r, c)
                if preset == PresetType.ALL_ACTIVE:
                    seat.set_state(CellState.ACTIVE)
                elif preset == PresetType.PAIRS:
                    # 2열 책상 + 1열 통로 패턴 (예: O O _ O O _ O O)
                    if c % 3 == 2:
                        seat.set_state(CellState.AISLE)
                    else:
                        seat.set_state(CellState.ACTIVE)
                elif preset == PresetType.EXAM:
                    # 시험 대형: 홀수 열을 통로로 비워 1인 1열 간격 유지 (예: O _ O _ O _)
                    if c % 2 == 1:
                        seat.set_state(CellState.AISLE)
                    else:
                        seat.set_state(CellState.ACTIVE)
                elif preset == PresetType.CLUSTER:
                    # 모둠형(4인 클러스터): 2행x2열 책상 묶음 후 가로/세로 통로 배치
                    if (r % 3 == 2) or (c % 3 == 2):
                        seat.set_state(CellState.AISLE)
                    else:
                        seat.set_state(CellState.ACTIVE)

    def clone_layout_states(self) -> Dict[Tuple[int, int], CellState]:
        """현재 격자의 셀 상태만 복사하여 딕셔너리로 반환합니다."""
        return {(r, c): self.get_seat(r, c).state for r in range(self.rows) for c in range(self.cols)}

    def apply_layout_states(self, states: Dict[Tuple[int, int], CellState]) -> None:
        """딕셔너리로 전달된 셀 상태를 현재 격자에 일괄 반영합니다."""
        for (r, c), state in states.items():
            if 0 <= r < self.rows and 0 <= c < self.cols:
                self.get_seat(r, c).set_state(state)

    def get_desk_pairs(self) -> Tuple[List[Tuple[Seat, Seat]], List[Seat]]:
        """
        현재 레이아웃의 통로(AISLE) 및 비활성(DISABLED) 셀을 기준으로 분단을 구분하고,
        같은 행 내 인접한 활성 책상(ACTIVE)을 왼쪽부터 2개씩 묶어 짝꿍 쌍과 단독 좌석을 반환합니다.
        통로나 비활성 공간을 넘어 임의로 짝을 맺지 않습니다.
        """
        pairs: List[Tuple[Seat, Seat]] = []
        singles: List[Seat] = []

        for r in range(self.rows):
            segment: List[Seat] = []
            for c in range(self.cols):
                seat = self.get_seat(r, c)
                if seat.is_active_desk:
                    segment.append(seat)
                else:
                    if segment:
                        for i in range(0, len(segment) - 1, 2):
                            pairs.append((segment[i], segment[i + 1]))
                        if len(segment) % 2 == 1:
                            singles.append(segment[-1])
                        segment = []
            if segment:
                for i in range(0, len(segment) - 1, 2):
                    pairs.append((segment[i], segment[i + 1]))
                if len(segment) % 2 == 1:
                    singles.append(segment[-1])

        return pairs, singles

