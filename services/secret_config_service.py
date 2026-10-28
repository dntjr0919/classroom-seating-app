"""
교실 자리 배치 프로그램 - 히든 관리자 비밀 설정 서비스 (services/secret_config_service.py)
교사용 비공개 기능(마스터 PIN, 히든 메뉴/강제배치 단축키, 1회성 강제 배치 플래그 및 사전 좌석 매핑,
1칸 이내 근거리 배치 제외 학생 쌍 목록)을 은닉 로컬 파일(.seat_secret.json) 및 QSettings에 저장·관리합니다.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import QSettings

DEFAULT_PIN = "0000"
DEFAULT_MENU_SHORTCUT = "Ctrl+Shift+H"
DEFAULT_FORCE_SHORTCUT = "Ctrl+Shift+F"
SECRET_FILE_NAME = ".seat_secret.json"

SETTINGS_ORG = "ClassroomSeatingApp"
SETTINGS_APP = "SecretAdminConfig"


def format_coord_key(row: int, col: int) -> str:
    """0-기반 (row, col) 좌표를 표준 문자열 키 '(r, c)' 형식으로 변환합니다."""
    return f"({int(row)}, {int(col)})"


def parse_coord_key(key: Union[str, Tuple[int, int], List[int]]) -> Optional[Tuple[int, int]]:
    """
    '(r, c)', 'r,c', (r, c) 등의 키를 (row, col) 정수 튜플로 파싱합니다.
    유효하지 않은 형식이면 None을 반환합니다.
    """
    if isinstance(key, (tuple, list)) and len(key) == 2:
        try:
            return (int(key[0]), int(key[1]))
        except (ValueError, TypeError):
            return None

    if not isinstance(key, str):
        return None

    cleaned = key.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()
    parts = [p.strip() for p in cleaned.split(",")]
    if len(parts) != 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def normalize_pair(id_a: str, id_b: str) -> Tuple[str, str]:
    """두 학생 ID 쌍을 순서와 무관하게 비교할 수 있도록 정규화합니다 (입력 순서는 유지하되 공백 제거)."""
    return (str(id_a).strip(), str(id_b).strip())


@dataclass
class SecretConfig:
    """히든 관리자 설정 데이터 모델"""

    pin: str = DEFAULT_PIN
    menu_shortcut: str = DEFAULT_MENU_SHORTCUT
    force_shortcut: str = DEFAULT_FORCE_SHORTCUT
    force_next_assignment: bool = False
    preset_map: Dict[str, str] = field(default_factory=dict)
    forbidden_pairs: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def open_menu_shortcut(self) -> str:
        return self.menu_shortcut

    @open_menu_shortcut.setter
    def open_menu_shortcut(self, value: str) -> None:
        self.menu_shortcut = value

    @property
    def force_trigger_shortcut(self) -> str:
        return self.force_shortcut

    @force_trigger_shortcut.setter
    def force_trigger_shortcut(self, value: str) -> None:
        self.force_shortcut = value

    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화용 딕셔너리를 반환합니다."""
        normalized_presets: Dict[str, str] = {}
        for k, v in self.preset_map.items():
            coord = parse_coord_key(k)
            student_id = str(v).strip()
            if coord is not None and student_id:
                normalized_presets[format_coord_key(coord[0], coord[1])] = student_id

        normalized_pairs: List[List[str]] = []
        seen_sets = set()
        for pair in self.forbidden_pairs:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                a, b = str(pair[0]).strip(), str(pair[1]).strip()
                if a and b and a != b:
                    pair_key = frozenset((a, b))
                    if pair_key not in seen_sets:
                        seen_sets.add(pair_key)
                        normalized_pairs.append([a, b])

        return {
            "pin": str(self.pin).strip() or DEFAULT_PIN,
            "menu_shortcut": str(self.menu_shortcut).strip(),
            "force_shortcut": str(self.force_shortcut).strip(),
            "force_next_assignment": bool(self.force_next_assignment),
            "preset_map": normalized_presets,
            "forbidden_pairs": normalized_pairs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecretConfig":
        """딕셔너리에서 안전하게 SecretConfig 인스턴스를 복원합니다."""
        if not isinstance(data, dict):
            return cls()

        raw_pin = str(data.get("pin", DEFAULT_PIN)).strip()
        if not raw_pin:
            raw_pin = DEFAULT_PIN

        menu_sc = data.get("menu_shortcut", data.get("open_menu_shortcut", DEFAULT_MENU_SHORTCUT))
        force_sc = data.get("force_shortcut", data.get("force_trigger_shortcut", DEFAULT_FORCE_SHORTCUT))

        menu_shortcut = str(menu_sc).strip() if menu_sc is not None else DEFAULT_MENU_SHORTCUT
        force_shortcut = str(force_sc).strip() if force_sc is not None else DEFAULT_FORCE_SHORTCUT
        force_next = bool(data.get("force_next_assignment", False))

        raw_presets = data.get("preset_map", {})
        preset_map: Dict[str, str] = {}
        if isinstance(raw_presets, dict):
            for k, v in raw_presets.items():
                coord = parse_coord_key(k)
                st_id = str(v).strip() if v is not None else ""
                if coord is not None and st_id:
                    preset_map[format_coord_key(coord[0], coord[1])] = st_id

        raw_pairs = data.get("forbidden_pairs", [])
        forbidden_pairs: List[Tuple[str, str]] = []
        seen_sets = set()
        if isinstance(raw_pairs, list):
            for item in raw_pairs:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    a, b = str(item[0]).strip(), str(item[1]).strip()
                    if a and b and a != b:
                        pair_key = frozenset((a, b))
                        if pair_key not in seen_sets:
                            seen_sets.add(pair_key)
                            forbidden_pairs.append((a, b))

        return cls(
            pin=raw_pin,
            menu_shortcut=menu_shortcut,
            force_shortcut=force_shortcut,
            force_next_assignment=force_next,
            preset_map=preset_map,
            forbidden_pairs=forbidden_pairs,
        )


class SecretConfigService:
    """
    히든 관리자 설정을 로컬 은닉 파일(.seat_secret.json)과 QSettings에
    이중 안전 저장·조회하는 서비스 클래스.
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        self._file_path = file_path or self._default_secret_file_path()
        self._config: SecretConfig = self.load()

    @staticmethod
    def _default_secret_file_path() -> str:
        """프로젝트 실행 경로 기준 .seat_secret.json 파일 경로를 반환합니다."""
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_dir, SECRET_FILE_NAME)

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def config(self) -> SecretConfig:
        return self._config

    def load(self) -> SecretConfig:
        """
        .seat_secret.json 파일에서 설정을 우선 로드하고,
        파일이 없거나 손상된 경우 QSettings 백업 또는 기본값으로 복원합니다.
        """
        # 1. 로컬 은닉 파일(.seat_secret.json) 확인
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as fp:
                    raw = json.load(fp)
                self._config = SecretConfig.from_dict(raw)
                return self._config
            except Exception:
                pass

        # 2. QSettings 백업 확인 (커스텀 파일 경로가 아닌 기본 경로일 때만)
        if self._file_path == self._default_secret_file_path():
            try:
                settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
                raw_json = settings.value("secret_config_json", "", type=str)
                if raw_json:
                    data = json.loads(raw_json)
                    self._config = SecretConfig.from_dict(data)
                    self._write_file_safely(self._config)
                    return self._config
            except Exception:
                pass

        # 3. 최초 실행 시 기본값 초기화 및 저장
        self._config = SecretConfig()
        self.save(self._config)
        return self._config

    def _write_file_safely(self, cfg: SecretConfig) -> None:
        """은닉 설정 파일(.seat_secret.json)에 JSON을 기록합니다."""
        try:
            # Windows에서 숨김 속성 파일 덮어쓰기 권한 오류 방지를 위해 기존 숨김 속성 임시 해제
            if sys.platform == "win32" and os.path.exists(self._file_path):
                try:
                    import ctypes
                    FILE_ATTRIBUTE_NORMAL = 0x80
                    ctypes.windll.kernel32.SetFileAttributesW(self._file_path, FILE_ATTRIBUTE_NORMAL)
                except Exception:
                    pass

            with open(self._file_path, "w", encoding="utf-8") as fp:
                json.dump(cfg.to_dict(), fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save(self, config: Optional[SecretConfig] = None) -> None:
        """현재 설정을 .seat_secret.json 및 QSettings에 동기화 저장합니다."""
        if config is not None:
            self._config = SecretConfig.from_dict(config.to_dict())
        else:
            self._config = SecretConfig.from_dict(self._config.to_dict())

        self._write_file_safely(self._config)

        if self._file_path == self._default_secret_file_path():
            try:
                settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
                settings.setValue(
                    "secret_config_json",
                    json.dumps(self._config.to_dict(), ensure_ascii=False),
                )
                settings.sync()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 개별 항목 조회 / 수정 편의 메서드
    # ------------------------------------------------------------------
    def verify_pin(self, input_pin: str) -> bool:
        """입력된 PIN 번호가 저장된 마스터 PIN과 일치하는지 검증합니다."""
        self.load()
        return str(input_pin).strip() == self._config.pin

    def get_pin(self) -> str:
        self.load()
        return self._config.pin

    def set_pin(self, new_pin: str) -> None:
        cleaned = str(new_pin).strip()
        if not cleaned:
            raise ValueError("PIN 번호는 비어 있을 수 없습니다.")
        self._config.pin = cleaned
        self.save()

    def get_menu_shortcut(self) -> str:
        self.load()
        return self._config.menu_shortcut

    def set_menu_shortcut(self, shortcut: str) -> None:
        self._config.menu_shortcut = str(shortcut).strip()
        self.save()

    def get_force_shortcut(self) -> str:
        self.load()
        return self._config.force_shortcut

    def set_force_shortcut(self, shortcut: str) -> None:
        self._config.force_shortcut = str(shortcut).strip()
        self.save()

    def is_force_next_assignment(self) -> bool:
        self.load()
        return bool(self._config.force_next_assignment)

    def set_force_next_assignment(self, enabled: bool) -> None:
        self.load()
        self._config.force_next_assignment = bool(enabled)
        self.save()

    def toggle_force_next_assignment(self) -> bool:
        """1회성 강제 배치 플래그를 토글(On/Off)하고 변경된 상태를 반환합니다."""
        self.load()
        self._config.force_next_assignment = not self._config.force_next_assignment
        self.save()
        return self._config.force_next_assignment

    def consume_force_next_assignment(self) -> None:
        """1회성 강제 배치가 실행된 직후 플래그를 즉시 False로 리셋합니다."""
        self.load()
        if self._config.force_next_assignment:
            self._config.force_next_assignment = False
            self.save()

    def get_preset_map(self) -> Dict[str, str]:
        """강제 배치 사전 좌석 매핑 딕셔너리 사본(key: '(r, c)', value: student_id)을 반환합니다."""
        self.load()
        return dict(self._config.preset_map)

    def set_preset_map(self, preset_map: Dict[str, str]) -> None:
        cleaned: Dict[str, str] = {}
        for k, v in preset_map.items():
            coord = parse_coord_key(k)
            st_id = str(v).strip() if v is not None else ""
            if coord is not None and st_id:
                cleaned[format_coord_key(coord[0], coord[1])] = st_id
        self._config.preset_map = cleaned
        self.save()

    def set_preset_seat(self, row: int, col: int, student_id: Optional[str]) -> None:
        """
        특정 (row, col) 좌석에 학생을 사전 매핑합니다.
        동일 학생이 이미 다른 좌석에 매핑되어 있으면 기존 좌석 매핑을 제거합니다.
        student_id가 None 또는 빈 문자열이면 해당 좌석의 매핑을 해제합니다.
        """
        self.load()
        target_key = format_coord_key(row, col)
        if not student_id or not str(student_id).strip():
            self._config.preset_map.pop(target_key, None)
        else:
            st_id = str(student_id).strip()
            # 중복 방지: 이미 다른 좌석에 동일 학생이 지정되어 있다면 제거
            keys_to_remove = [
                k for k, v in self._config.preset_map.items() if v == st_id and k != target_key
            ]
            for k in keys_to_remove:
                self._config.preset_map.pop(k, None)
            self._config.preset_map[target_key] = st_id
        self.save()

    def clear_preset_map(self) -> None:
        self.load()
        self._config.preset_map.clear()
        self.save()

    def get_forbidden_pairs(self) -> List[Tuple[str, str]]:
        """1칸 이내 근거리 배치 제외 학생 ID 쌍 리스트를 반환합니다."""
        self.load()
        return list(self._config.forbidden_pairs)

    def set_forbidden_pairs(self, pairs: List[Tuple[str, str]]) -> None:
        cleaned: List[Tuple[str, str]] = []
        seen = set()
        for pair in pairs:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                a, b = str(pair[0]).strip(), str(pair[1]).strip()
                if a and b and a != b:
                    key = frozenset((a, b))
                    if key not in seen:
                        seen.add(key)
                        cleaned.append((a, b))
        self._config.forbidden_pairs = cleaned
        self.save()

    def add_forbidden_pair(self, student_id_a: str, student_id_b: str) -> bool:
        """
        근거리 배치 제외 학생 쌍을 추가합니다.
        동일 학생이거나 이미 등록된 쌍(순서 무관)이면 False를 반환합니다.
        """
        self.load()
        a, b = str(student_id_a).strip(), str(student_id_b).strip()
        if not a or not b or a == b:
            return False
        target_set = frozenset((a, b))
        for existing_a, existing_b in self._config.forbidden_pairs:
            if frozenset((existing_a, existing_b)) == target_set:
                return False
        self._config.forbidden_pairs.append((a, b))
        self.save()
        return True

    def remove_forbidden_pair(self, student_id_a: str, student_id_b: str) -> bool:
        """등록된 근거리 배치 제외 학생 쌍을 삭제합니다 (순서 무관)."""
        self.load()
        target_set = frozenset((str(student_id_a).strip(), str(student_id_b).strip()))
        before_len = len(self._config.forbidden_pairs)
        self._config.forbidden_pairs = [
            (a, b)
            for (a, b) in self._config.forbidden_pairs
            if frozenset((a, b)) != target_set
        ]
        if len(self._config.forbidden_pairs) != before_len:
            self.save()
            return True
        return False
