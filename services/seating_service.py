"""
교실 자리 배치 프로그램 - 자리 배치 알고리즘 서비스 (services/seating_service.py)
5가지 배치 방식(기본 무작위, 남녀 이성 짝꿍, 동성 짝꿍, 번호순 자동 배치, 앞뒤 구역 교차 배치),
고정석(Pin/Lock) 유지/무시 옵션, 수동 자리 맞바꾸기(Swap) 및 유효성 검증을 담당합니다.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

from models import (
    ClassroomGrid,
    Gender,
    OrderDirection,
    PlacementMode,
    Seat,
    Student,
)


class SeatingValidationError(Exception):
    """자리 배치 제약 조건 위반 시 발생하는 사용자 정의 예외"""


class SeatingService:
    """
    교실 자리 배치 비즈니스 로직 및 제약 조건 검증 서비스 클래스.
    """

    @staticmethod
    def validate_arrangement(
        grid: ClassroomGrid,
        roster: List[Student],
        respect_locks: bool = True,
    ) -> None:
        """
        자리 배치 실행 전 제약 조건을 검증합니다.
        - 학생 명단이 비어 있는 경우 예외 발생
        - 학생 명단 내 중복 식별자가 있는 경우 예외 발생
        - 활성 책상 수 < 전체 학생 수인 경우 예외 발생 (기존 배치 보존)
        - 고정석 유지 시 배정 가능한 책상 수가 부족한 경우 예외 발생
        """
        active_desks = grid.active_desks()
        total_active = len(active_desks)
        total_students = len(roster)

        if total_students == 0:
            raise SeatingValidationError(
                "등록된 학생 명단이 없습니다. 먼저 [학생 명단 관리]에서 학생을 추가하거나 엑셀 파일을 불러오세요."
            )

        seen_ids: Set[str] = set()
        for st in roster:
            if st.student_id in seen_ids:
                raise SeatingValidationError(
                    f"학생 명단에 중복된 학생 식별자({st.display_label()})가 존재합니다."
                )
            seen_ids.add(st.student_id)

        if total_active < total_students:
            raise SeatingValidationError(
                f"활성 책상 수({total_active}석)가 전체 학생 수({total_students}명)보다 부족합니다.\n"
                f"최소 {total_students - total_active}개의 활성 책상을 추가로 확보해 주세요."
            )

        if respect_locks:
            locked_desks = [d for d in active_desks if d.is_locked]
            if len(locked_desks) > total_active:
                raise SeatingValidationError(
                    f"고정된 좌석 수({len(locked_desks)}석)가 활성 책상 수({total_active}석)를 초과합니다."
                )

            roster_ids = {s.student_id for s in roster}
            # 빈 좌석으로 잠겨 있는 좌석 수 계산 (명단에서 삭제된 학생이 앉아 있던 잠금 좌석은 해제 대상이므로 제외)
            locked_empty_count = sum(1 for d in locked_desks if d.student is None)
            available_for_students = total_active - locked_empty_count
            if available_for_students < total_students:
                raise SeatingValidationError(
                    f"빈 상태로 고정된 좌석({locked_empty_count}석)을 제외하면 배정 가능한 책상({available_for_students}석)이 "
                    f"전체 학생 수({total_students}명)보다 부족합니다."
                )

            locked_valid_students = {
                d.student.student_id
                for d in locked_desks
                if d.student is not None and d.student.student_id in roster_ids
            }
            unlocked_count = sum(
                1
                for d in active_desks
                if not d.is_locked or (d.student is not None and d.student.student_id not in roster_ids)
            )
            remaining_count = total_students - len(locked_valid_students)
            if unlocked_count < remaining_count:
                raise SeatingValidationError(
                    f"배정 가능한 비고정 좌석({unlocked_count}석)보다 "
                    f"배정해야 할 학생 수({remaining_count}명)가 더 많습니다."
                )

    @classmethod
    def execute_placement(
        cls,
        grid: ClassroomGrid,
        roster: List[Student],
        mode: PlacementMode = PlacementMode.RANDOM,
        respect_locks: bool = True,
        order_direction: OrderDirection = OrderDirection.ROW_FIRST,
        seed: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        선택된 배치 방식(5종)과 고정석 유지 여부에 따라 자리를 배치합니다.
        - respect_locks=True: 고정된 좌석과 해당 학생을 유지하고 나머지 좌석만 배치
        - respect_locks=False: 고정 표시(is_locked) 자체는 삭제하지 않고 유지하되,
                               이번 배치에서 고정 제약을 무시하고 전체 학생을 재배치
        반환값: (상태 표시줄 요약 메시지, 조건 부분 불충족 안내 메시지 또는 None)
        """
        # 1. 사전 유효성 검증 (실패 시 기존 배치 상태 100% 보존)
        cls.validate_arrangement(grid, roster, respect_locks=respect_locks)

        # 앞뒤 구역 교차 배치는 현재 배치된 좌석이 최소 1개 이상 있어야 수행 가능
        prev_coord_by_id: Dict[str, Tuple[int, int]] = {
            desk.student.student_id: desk.coordinate
            for desk in grid.active_desks()
            if desk.student is not None
        }
        if mode == PlacementMode.FRONT_BACK_CROSS and not prev_coord_by_id:
            raise SeatingValidationError(
                "현재 배치된 학생이 없어 앞뒤 구역 교차 배치를 실행할 수 없습니다.\n"
                "먼저 다른 배치 방식으로 자리를 배치한 뒤 실행해 주세요."
            )

        rng = random.Random(seed)
        roster_by_id = {s.student_id: s for s in roster}

        # 2. 고정석 유지/무시 옵션에 따른 대상 좌석 및 미배정 학생 분리
        locked_student_ids: Set[str] = set()
        editable_desks: List[Seat] = []

        if respect_locks:
            for desk in grid.active_desks():
                if desk.is_locked:
                    if desk.student is not None:
                        if desk.student.student_id in roster_by_id and desk.student.student_id not in locked_student_ids:
                            desk.student = roster_by_id[desk.student.student_id]
                            locked_student_ids.add(desk.student.student_id)
                        else:
                            # 명단에서 제거된 학생이거나 중복 고정된 경우 정리
                            desk.student = None
                            desk.is_locked = False
                            editable_desks.append(desk)
                    else:
                        # 빈 좌석으로 고정된 경우 빈 상태 유지
                        pass
                else:
                    desk.student = None
                    editable_desks.append(desk)
        else:
            # 고정 제약 무시: 저장된 is_locked 속성은 삭제하지 않고 학생 배정만 전체 재수행
            for desk in grid.active_desks():
                desk.student = None
                editable_desks.append(desk)

        remaining_students: List[Student] = [
            s for s in roster if s.student_id not in locked_student_ids
        ]

        # 앞줄부터 채울 대상 비고정 좌석 (학생 수와 정확히 동일한 개수)
        target_desks: List[Seat] = editable_desks[: len(remaining_students)]

        notice: Optional[str] = None

        if mode == PlacementMode.RANDOM:
            cls._place_random(target_desks, remaining_students, rng)
        elif mode == PlacementMode.MIXED_GENDER_PAIR:
            notice = cls._place_mixed_gender_pairs(
                grid, target_desks, remaining_students, respect_locks, rng
            )
        elif mode == PlacementMode.SAME_GENDER_PAIR:
            notice = cls._place_same_gender_pairs(
                grid, target_desks, remaining_students, respect_locks, rng
            )
        elif mode == PlacementMode.NUMBER_ORDER:
            notice = cls._place_number_order(
                target_desks, remaining_students, order_direction
            )
        elif mode == PlacementMode.FRONT_BACK_CROSS:
            notice = cls._place_front_back_cross(
                grid,
                target_desks,
                remaining_students,
                prev_coord_by_id,
                respect_locks,
                rng,
            )

        # 3. 사후 무결성 검증 (학생 중복 또는 누락 방지)
        cls._verify_post_assignment(grid, roster)

        lock_desc = "고정석 유지" if respect_locks else "고정 제약 무시"
        status_msg = f"[{mode.display_kr()} · {lock_desc}] 자리 배치가 완료되었습니다."
        if notice:
            status_msg += f" ({notice})"

        return status_msg, notice

    @staticmethod
    def _place_random(
        target_desks: List[Seat],
        students: List[Student],
        rng: random.Random,
    ) -> None:
        shuffled = list(students)
        rng.shuffle(shuffled)
        for desk, student in zip(target_desks, shuffled):
            desk.student = student

    @classmethod
    def _place_mixed_gender_pairs(
        cls,
        grid: ClassroomGrid,
        target_desks: List[Seat],
        students: List[Student],
        respect_locks: bool,
        rng: random.Random,
    ) -> Optional[str]:
        """
        남녀 이성 짝꿍 배치:
        - 레이아웃의 통로(AISLE)/비활성(DISABLED)을 넘지 않는 인접 2인 짝꿍 좌석을 활용
        - 고정석 유지 시 이미 고정된 학생의 성별과 반대 성별을 옆자리에 우선 배정
        - 빈 짝꿍 좌석에 남학생 1명 + 여학생 1명을 우선 배정하고 나머지는 무작위 배정
        """
        target_coords = {d.coordinate for d in target_desks}
        pairs, _ = grid.get_desk_pairs()

        males = [s for s in students if s.gender == Gender.MALE]
        females = [s for s in students if s.gender == Gender.FEMALE]
        unknowns = [s for s in students if s.gender == Gender.NONE]
        rng.shuffle(males)
        rng.shuffle(females)
        rng.shuffle(unknowns)

        open_pairs: List[Tuple[Seat, Seat]] = []
        half_locked_pairs: List[Tuple[Seat, Seat]] = []

        for s1, s2 in pairs:
            c1_in = s1.coordinate in target_coords
            c2_in = s2.coordinate in target_coords
            if c1_in and c2_in:
                open_pairs.append((s1, s2))
            elif respect_locks and (c1_in != c2_in):
                locked_seat = s2 if c1_in else s1
                free_seat = s1 if c1_in else s2
                if locked_seat.student is not None:
                    half_locked_pairs.append((locked_seat, free_seat))

        # 1) 한쪽이 고정된 짝꿍 좌석에 이성 학생 우선 배정
        rng.shuffle(half_locked_pairs)
        for locked_seat, free_seat in half_locked_pairs:
            assert locked_seat.student is not None
            if locked_seat.student.gender == Gender.MALE and females:
                free_seat.student = females.pop()
            elif locked_seat.student.gender == Gender.FEMALE and males:
                free_seat.student = males.pop()

        # 2) 두 자리가 모두 비어 있는 짝꿍 좌석에 남녀 1쌍씩 배정
        rng.shuffle(open_pairs)
        for s1, s2 in open_pairs:
            if males and females:
                m_st = males.pop()
                f_st = females.pop()
                if rng.random() < 0.5:
                    s1.student, s2.student = m_st, f_st
                else:
                    s1.student, s2.student = f_st, m_st

        # 3) 남은 빈 좌석에 나머지 학생 무작위 배정
        unfilled_desks = [d for d in target_desks if d.student is None]
        leftovers = males + females + unknowns
        rng.shuffle(leftovers)
        for desk, st in zip(unfilled_desks, leftovers):
            desk.student = st

        return cls._summarize_pair_result(grid, is_mixed=True)

    @classmethod
    def _place_same_gender_pairs(
        cls,
        grid: ClassroomGrid,
        target_desks: List[Seat],
        students: List[Student],
        respect_locks: bool,
        rng: random.Random,
    ) -> Optional[str]:
        """
        동성 짝꿍 배치:
        - 레이아웃의 통로(AISLE)/비활성(DISABLED)을 넘지 않는 인접 2인 짝꿍 좌석을 활용
        - 고정석 유지 시 이미 고정된 학생과 같은 성별 학생을 옆자리에 우선 배정
        - 빈 짝꿍 좌석에 남-남 또는 여-여 짝을 우선 배정하고 나머지는 무작위 배정
        """
        target_coords = {d.coordinate for d in target_desks}
        pairs, _ = grid.get_desk_pairs()

        males = [s for s in students if s.gender == Gender.MALE]
        females = [s for s in students if s.gender == Gender.FEMALE]
        unknowns = [s for s in students if s.gender == Gender.NONE]
        rng.shuffle(males)
        rng.shuffle(females)
        rng.shuffle(unknowns)

        open_pairs: List[Tuple[Seat, Seat]] = []
        half_locked_pairs: List[Tuple[Seat, Seat]] = []

        for s1, s2 in pairs:
            c1_in = s1.coordinate in target_coords
            c2_in = s2.coordinate in target_coords
            if c1_in and c2_in:
                open_pairs.append((s1, s2))
            elif respect_locks and (c1_in != c2_in):
                locked_seat = s2 if c1_in else s1
                free_seat = s1 if c1_in else s2
                if locked_seat.student is not None:
                    half_locked_pairs.append((locked_seat, free_seat))

        # 1) 한쪽이 고정된 짝꿍 좌석에 동성 학생 우선 배정
        rng.shuffle(half_locked_pairs)
        for locked_seat, free_seat in half_locked_pairs:
            assert locked_seat.student is not None
            if locked_seat.student.gender == Gender.MALE and males:
                free_seat.student = males.pop()
            elif locked_seat.student.gender == Gender.FEMALE and females:
                free_seat.student = females.pop()

        # 2) 남은 남학생/여학생으로 2인 동성 조를 구성해 빈 짝꿍 좌석에 배정
        same_gender_teams: List[Tuple[Student, Student]] = []
        while len(males) >= 2:
            same_gender_teams.append((males.pop(), males.pop()))
        while len(females) >= 2:
            same_gender_teams.append((females.pop(), females.pop()))
        rng.shuffle(same_gender_teams)

        rng.shuffle(open_pairs)
        for (s1, s2), (st_a, st_b) in zip(open_pairs, same_gender_teams):
            s1.student = st_a
            s2.student = st_b

        # 사용되지 않은 동성 팀 학생들을 다시 잔여 풀로 환원
        used_teams = min(len(open_pairs), len(same_gender_teams))
        extra_team_students: List[Student] = []
        for st_a, st_b in same_gender_teams[used_teams:]:
            extra_team_students.extend([st_a, st_b])

        # 3) 남은 빈 좌석에 나머지 학생 무작위 배정
        unfilled_desks = [d for d in target_desks if d.student is None]
        leftovers = males + females + unknowns + extra_team_students
        rng.shuffle(leftovers)
        for desk, st in zip(unfilled_desks, leftovers):
            desk.student = st

        return cls._summarize_pair_result(grid, is_mixed=False)

    @staticmethod
    def _summarize_pair_result(grid: ClassroomGrid, is_mixed: bool) -> Optional[str]:
        """짝꿍 배치 결과에서 조건 성립 여부와 부분 불충족 사유를 간결히 요약합니다."""
        pairs, singles = grid.get_desk_pairs()
        mode_label = "이성 짝꿍" if is_mixed else "동성 짝꿍"

        if not pairs:
            return "현재 레이아웃에 인접한 짝꿍 좌석이 없어 무작위로 배치되었습니다."

        matched_pairs = 0
        unmatched_students = 0

        for s1, s2 in pairs:
            if s1.student is not None and s2.student is not None:
                g1, g2 = s1.student.gender, s2.student.gender
                if is_mixed:
                    is_ok = {g1, g2} == {Gender.MALE, Gender.FEMALE}
                else:
                    is_ok = (g1 == g2) and (g1 in (Gender.MALE, Gender.FEMALE))
                if is_ok:
                    matched_pairs += 1
                else:
                    unmatched_students += 2
            elif s1.student is not None or s2.student is not None:
                unmatched_students += 1

        for single_seat in singles:
            if single_seat.student is not None:
                unmatched_students += 1

        if unmatched_students > 0:
            return (
                f"{mode_label} {matched_pairs}조 성립 · "
                f"인원/성별/고정석/단독석 조건으로 {unmatched_students}명은 잔여 좌석에 배치됨"
            )
        return None

    @staticmethod
    def _place_number_order(
        target_desks: List[Seat],
        students: List[Student],
        order_direction: OrderDirection,
    ) -> Optional[str]:
        """
        번호순 자동 배치:
        - 출석번호 오름차순(숫자 우선, 번호 미입력 시 이름순)으로 정렬하여 배치
        - 가로 우선(ROW_FIRST): 앞줄 왼쪽 -> 오른쪽 순서
        - 세로 우선(COL_FIRST): 왼쪽 열 앞 -> 뒤 순서
        """
        sorted_students = sorted(students, key=lambda s: s.sort_key())

        if order_direction == OrderDirection.COL_FIRST:
            ordered_desks = sorted(target_desks, key=lambda d: (d.col, d.row))
        else:
            ordered_desks = sorted(target_desks, key=lambda d: (d.row, d.col))

        for desk, student in zip(ordered_desks, sorted_students):
            desk.student = student

        no_num_count = sum(1 for s in sorted_students if not s.number.strip())
        if no_num_count > 0:
            return f"번호 미입력 학생 {no_num_count}명은 이름순으로 뒷자리에 배치됨"
        return None

    @staticmethod
    def _place_front_back_cross(
        grid: ClassroomGrid,
        target_desks: List[Seat],
        students: List[Student],
        prev_coord_by_id: Dict[str, Tuple[int, int]],
        respect_locks: bool,
        rng: random.Random,
    ) -> Optional[str]:
        """
        앞뒤 구역 교차 배치:
        - 실제 교탁과 가까운 앞쪽 구역(작은 row 인덱스)과 뒤쪽 구역(큰 row 인덱스)을 구분하여
          앞쪽 구역 학생은 뒤쪽 구역으로, 뒤쪽 구역 학생은 앞쪽 구역으로 교차 재배치합니다.
        - 홀수 행, 앞뒤 구역 수용 인원 차이, 고정석, 미배정 학생을 안전하게 처리합니다.
        """
        locked_occupied = [
            d for d in grid.active_desks() if d.student is not None and d not in target_desks
        ]
        all_relevant_rows = sorted(
            {d.row for d in target_desks}
            | {d.row for d in locked_occupied}
            | {r for (r, _) in prev_coord_by_id.values()}
        )

        if len(all_relevant_rows) <= 1:
            shuffled = list(students)
            rng.shuffle(shuffled)
            for desk, st in zip(target_desks, shuffled):
                desk.student = st
            return "현재 사용 중인 좌석이 1개 행뿐이어서 같은 행 내에서 무작위 재배치됨"

        half_idx = len(all_relevant_rows) // 2
        front_rows: Set[int] = set(all_relevant_rows[:half_idx])
        back_rows: Set[int] = set(all_relevant_rows[half_idx:])

        # 홀수 행일 때 가장 뒤쪽 행들과 정중앙 행을 구분하여 교차 이동 효과를 극대화
        is_odd_rows = (len(all_relevant_rows) % 2 == 1)
        mid_row: Optional[int] = all_relevant_rows[half_idx] if is_odd_rows else None
        strict_back_rows: Set[int] = (
            set(all_relevant_rows[half_idx + 1 :]) if is_odd_rows else back_rows
        )

        front_target_desks = [d for d in target_desks if d.row in front_rows]
        rng.shuffle(front_target_desks)

        if is_odd_rows and mid_row is not None:
            strict_back_desks = [d for d in target_desks if d.row in strict_back_rows]
            mid_target_desks = [d for d in target_desks if d.row == mid_row]
            rng.shuffle(strict_back_desks)
            rng.shuffle(mid_target_desks)
            # 앞구역 학생이 뒤로 갈 때 맨 뒤쪽 행부터 우선 배정
            back_target_desks = strict_back_desks + mid_target_desks
        else:
            back_target_desks = [d for d in target_desks if d.row in back_rows]
            rng.shuffle(back_target_desks)

        from_front: List[Student] = []
        from_strict_back: List[Student] = []
        from_mid: List[Student] = []
        unassigned_prev: List[Student] = []

        for st in students:
            prev_coord = prev_coord_by_id.get(st.student_id)
            if prev_coord is None:
                unassigned_prev.append(st)
            else:
                prev_r, _ = prev_coord
                if prev_r in front_rows:
                    from_front.append(st)
                elif is_odd_rows and mid_row is not None and prev_r == mid_row:
                    from_mid.append(st)
                else:
                    from_strict_back.append(st)

        rng.shuffle(from_front)
        rng.shuffle(from_strict_back)
        rng.shuffle(from_mid)
        rng.shuffle(unassigned_prev)

        # 뒷구역 학생이 앞으로 갈 때 맨 뒷줄 학생을 최우선으로 앞구역에 배정
        from_back = from_strict_back + from_mid

        overflow_students: List[Student] = []

        # 1) 이전 앞구역 학생 -> 뒤쪽 구역 좌석에 배정
        for st in from_front:
            if back_target_desks:
                desk = back_target_desks.pop(0)
                desk.student = st
            else:
                overflow_students.append(st)

        # 2) 이전 뒷구역 학생 -> 앞쪽 구역 좌석에 배정
        for st in from_back:
            if front_target_desks:
                desk = front_target_desks.pop(0)
                desk.student = st
            else:
                overflow_students.append(st)

        # 3) 구역 수용 인원 차이로 인한 잔여 학생 및 미배정 학생을 남은 빈 좌석에 배정
        remaining_desks = back_target_desks + front_target_desks
        rng.shuffle(remaining_desks)
        leftover_students = overflow_students + unassigned_prev
        rng.shuffle(leftover_students)

        for desk, st in zip(remaining_desks, leftover_students):
            desk.student = st

        # 결과 요약 안내 생성
        notes: List[str] = []
        if overflow_students:
            notes.append(f"앞뒤 구역 좌석 수 차이로 {len(overflow_students)}명은 동일 구역 내 재배치")
        if unassigned_prev:
            notes.append(f"기존 미배정 {len(unassigned_prev)}명 신규 배치")
        if respect_locks and locked_occupied:
            notes.append(f"고정석 {len(locked_occupied)}명 유지")

        return " · ".join(notes) if notes else None

    @staticmethod
    def _verify_post_assignment(grid: ClassroomGrid, roster: List[Student]) -> None:
        """모든 학생이 중복이나 누락 없이 정확히 1좌석씩 배정되었는지 검증합니다."""
        roster_ids = {s.student_id for s in roster}
        assigned_ids: List[str] = [
            d.student.student_id
            for d in grid.active_desks()
            if d.student is not None
        ]
        if len(assigned_ids) != len(set(assigned_ids)):
            raise SeatingValidationError("내부 오류: 동일 학생이 중복 배치되었습니다.")
        if set(assigned_ids) != roster_ids:
            missing = len(roster_ids - set(assigned_ids))
            raise SeatingValidationError(f"내부 오류: 배정에서 누락된 학생({missing}명)이 발생했습니다.")

    @classmethod
    def assign_full_random(
        cls,
        grid: ClassroomGrid,
        roster: List[Student],
        seed: Optional[int] = None,
    ) -> None:
        """기존 호환용: 고정 제약을 무시하고 전체 학생을 무작위 배치합니다."""
        cls.execute_placement(
            grid,
            roster,
            mode=PlacementMode.RANDOM,
            respect_locks=False,
            seed=seed,
        )

    @classmethod
    def assign_respecting_locks(
        cls,
        grid: ClassroomGrid,
        roster: List[Student],
        seed: Optional[int] = None,
    ) -> None:
        """기존 호환용: 고정석을 유지하고 나머지 학생을 무작위 배치합니다."""
        cls.execute_placement(
            grid,
            roster,
            mode=PlacementMode.RANDOM,
            respect_locks=True,
            seed=seed,
        )

    @staticmethod
    def swap_seats(
        grid: ClassroomGrid,
        coord_a: Tuple[int, int],
        coord_b: Tuple[int, int],
    ) -> None:
        """
        두 활성 책상(coord_a, coord_b)에 배정된 학생을 서로 맞바꿉니다.
        """
        if coord_a == coord_b:
            return

        seat_a = grid.get_seat(*coord_a)
        seat_b = grid.get_seat(*coord_b)

        if not seat_a.is_active_desk or not seat_b.is_active_desk:
            raise SeatingValidationError("활성 책상끼리만 자리를 맞바꿀 수 있습니다.")

        seat_a.student, seat_b.student = seat_b.student, seat_a.student

    @staticmethod
    def assign_student_to_seat(
        grid: ClassroomGrid,
        target_coord: Tuple[int, int],
        student: Optional[Student],
        auto_lock: bool = True,
    ) -> None:
        """
        특정 좌석에 학생을 직접 지정(Pre-set)합니다.
        이미 다른 좌석에 해당 학생이 배치되어 있다면 기존 좌석에서 자동으로 이동시킵니다.
        """
        target_seat = grid.get_seat(*target_coord)
        if not target_seat.is_active_desk:
            raise SeatingValidationError("비활성 공간이나 통로에는 학생을 배치할 수 없습니다.")

        if student is None:
            target_seat.student = None
            target_seat.is_locked = False
            return

        # 이미 다른 좌석에 배정되어 있는지 확인 후 기존 좌석 비우기
        for desk in grid.active_desks():
            if (
                desk.coordinate != target_coord
                and desk.student is not None
                and desk.student.student_id == student.student_id
            ):
                desk.student = None
                desk.is_locked = False

        target_seat.student = student
        if auto_lock:
            target_seat.is_locked = True
