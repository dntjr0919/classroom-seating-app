"""
교실 자리 배치 프로그램 - 학생 명단 관리 다이얼로그 (views/student_dialog.py)
테이블 직접 편집(행 추가/수정/삭제) 및 엑셀(.xlsx, .xls) 파일 업로드를 지원합니다.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models import Gender, Student
from services import FileService, FileServiceError
from .theme_manager import ThemeManager, show_saved_file_message


class StudentRosterDialog(QDialog):
    """
    학생 명단을 수동으로 입력/편집하거나 엑셀 파일에서 불러오는 모달 다이얼로그.
    """

    COL_NUMBER = 0
    COL_NAME = 1
    COL_GENDER = 2

    def __init__(
        self,
        current_roster: List[Student],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("학생 명단 관리")
        self.resize(620, 520)
        self._roster: List[Student] = list(current_roster)
        self._init_ui()
        self._populate_table(self._roster)

    def _init_ui(self) -> None:
        is_dark = ThemeManager.is_dark()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 상단 안내 및 엑셀 업로드 버튼 영역
        top_bar = QHBoxLayout()
        info_label = QLabel(
            "학생의 <b>번호</b> 또는 <b>이름</b> 중 최소 하나를 입력해야 합니다.<br>"
            "엑셀(.xlsx, .xls) 업로드 시 <code>번호</code>, <code>이름</code>, <code>성별</code> 열을 자동 인식합니다."
        )
        info_color = "#CBD5E1" if is_dark else "#334155"
        info_label.setStyleSheet(f"color: {info_color}; font-size: 12px;")
        top_bar.addWidget(info_label, stretch=1)

        self.btn_upload_excel = QPushButton("📂 엑셀 파일 불러오기")
        self.btn_upload_excel.setObjectName("PrimaryButton")
        self.btn_upload_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_upload_excel.clicked.connect(self._on_upload_excel)
        top_bar.addWidget(self.btn_upload_excel)
        layout.addLayout(top_bar)

        # 중앙 편집 테이블
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["번호 (Number)", "이름 (Name)", "성별 (Gender)"])
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(self.COL_NUMBER, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(self.COL_GENDER, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        # 테이블 조작 버튼 바
        ctrl_bar = QHBoxLayout()
        self.btn_add_row = QPushButton("+ 학생 추가")
        self.btn_add_row.clicked.connect(lambda: self._insert_row())

        self.btn_del_row = QPushButton("- 선택 행 삭제")
        self.btn_del_row.clicked.connect(self._on_delete_selected_rows)

        self.btn_sample = QPushButton("✨ 샘플 명단(24명) 생성")
        self.btn_sample.clicked.connect(self._on_load_sample)

        self.btn_clear = QPushButton("전체 비우기")
        self.btn_clear.clicked.connect(self._on_clear_all)

        self.lbl_count = QLabel("총 0명")
        cnt_color = "#F8FAFC" if is_dark else "#1E293B"
        self.lbl_count.setStyleSheet(f"font-weight: bold; color: {cnt_color};")

        ctrl_bar.addWidget(self.btn_add_row)
        ctrl_bar.addWidget(self.btn_del_row)
        ctrl_bar.addWidget(self.btn_sample)
        ctrl_bar.addWidget(self.btn_clear)
        ctrl_bar.addStretch(1)
        ctrl_bar.addWidget(self.lbl_count)
        layout.addLayout(ctrl_bar)

        # 하단 확인 / 취소 및 엑셀 양식 저장 버튼 바
        bottom_bar = QHBoxLayout()

        self.btn_export_template = QPushButton("📥 엑셀 양식 저장")
        self.btn_export_template.setToolTip("현재 표에 입력된 학생 명단(번호, 이름, 성별)을 포함한 엑셀 양식(.xlsx)으로 저장합니다.")
        self.btn_export_template.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_template.clicked.connect(self._on_export_template)
        bottom_bar.addWidget(self.btn_export_template)

        bottom_bar.addStretch(1)

        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("명단 적용 및 닫기")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save_and_accept)

        bottom_bar.addWidget(self.btn_cancel)
        bottom_bar.addWidget(self.btn_save)
        layout.addLayout(bottom_bar)

    def _create_gender_combo(self, selected: Gender = Gender.NONE) -> QComboBox:
        combo = QComboBox()
        combo.addItem("선택 안 함 (-)", Gender.NONE.value)
        combo.addItem("남 (M)", Gender.MALE.value)
        combo.addItem("여 (F)", Gender.FEMALE.value)

        idx = combo.findData(selected.value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

    def _populate_table(self, students: List[Student]) -> None:
        self.table.setRowCount(0)
        for student in students:
            self._insert_row(student.number, student.name, student.gender)
        self._update_count_label()

    def _insert_row(
        self,
        number: str = "",
        name: str = "",
        gender: Gender = Gender.NONE,
    ) -> None:
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        if not number and not name:
            # 새 빈 행 추가 시 기본 번호 자동 제안
            number = str(row_idx + 1)

        num_item = QTableWidgetItem(str(number))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        name_item = QTableWidgetItem(str(name))
        name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.setItem(row_idx, self.COL_NUMBER, num_item)
        self.table.setItem(row_idx, self.COL_NAME, name_item)
        self.table.setCellWidget(row_idx, self.COL_GENDER, self._create_gender_combo(gender))
        self._update_count_label()

    def _on_delete_selected_rows(self) -> None:
        selected_rows = sorted(
            {index.row() for index in self.table.selectedIndexes()},
            reverse=True,
        )
        if not selected_rows:
            QMessageBox.information(self, "행 선택 안내", "삭제할 학생 행을 먼저 선택해 주세요.")
            return
        for row_idx in selected_rows:
            self.table.removeRow(row_idx)
        self._update_count_label()

    def _on_clear_all(self) -> None:
        if self.table.rowCount() == 0:
            return
        reply = QMessageBox.question(
            self,
            "전체 비우기 확인",
            "현재 입력된 모든 학생 명단을 비우시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)
            self._update_count_label()

    def _on_load_sample(self) -> None:
        sample_names = [
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
            ("21", "이도현", Gender.MALE), ("22", "이세영", Gender.FEMALE),
            ("23", "정해인", Gender.MALE), ("24", "한소희", Gender.FEMALE),
        ]
        sample_students = [Student(num, name, gen) for num, name, gen in sample_names]
        self._populate_table(sample_students)

    def _on_upload_excel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "학생 명단 엑셀 파일 선택",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)",
        )
        if not file_path:
            return

        try:
            imported_students = FileService.import_students_from_excel(file_path)
            self._populate_table(imported_students)
            QMessageBox.information(
                self,
                "엑셀 불러오기 완료",
                f"총 {len(imported_students)}명의 학생 명단을 성공적으로 불러왔습니다.",
            )
        except FileServiceError as exc:
            QMessageBox.critical(self, "엑셀 불러오기 오류", str(exc))

    def _update_count_label(self) -> None:
        self.lbl_count.setText(f"총 {self.table.rowCount()}행")

    def _on_save_and_accept(self) -> None:
        parsed_students: List[Student] = []
        seen_ids = set()

        for r in range(self.table.rowCount()):
            num_item = self.table.item(r, self.COL_NUMBER)
            name_item = self.table.item(r, self.COL_NAME)
            combo = self.table.cellWidget(r, self.COL_GENDER)

            raw_num = num_item.text().strip() if num_item else ""
            raw_name = name_item.text().strip() if name_item else ""
            raw_gender = Gender.NONE
            if isinstance(combo, QComboBox):
                raw_gender = Gender.from_str(combo.currentData())

            # 완전히 비어 있는 행은 무시
            if not raw_num and not raw_name:
                continue

            try:
                student = Student(number=raw_num, name=raw_name, gender=raw_gender)
            except ValueError as exc:
                QMessageBox.warning(
                    self,
                    "입력 값 오류",
                    f"{r + 1}번째 행에 오류가 있습니다:\n{exc}",
                )
                return

            # 동일 번호+이름 중복 방지
            if student.student_id in seen_ids:
                QMessageBox.warning(
                    self,
                    "중복 학생 감지",
                    f"{r + 1}번째 행의 '{student.display_label()}' 학생이 중복되어 있습니다.\n"
                    "번호 또는 이름을 구분해 주세요.",
                )
                return

            seen_ids.add(student.student_id)
            parsed_students.append(student)

        self._roster = parsed_students
        self.accept()

    def _get_current_table_students(self) -> List[Student]:
        """현재 테이블에 입력되어 있는 학생 목록을 Student 객체 리스트로 추출합니다."""
        parsed: List[Student] = []
        for r in range(self.table.rowCount()):
            num_item = self.table.item(r, self.COL_NUMBER)
            name_item = self.table.item(r, self.COL_NAME)
            combo = self.table.cellWidget(r, self.COL_GENDER)

            raw_num = num_item.text().strip() if num_item else ""
            raw_name = name_item.text().strip() if name_item else ""
            raw_gender = Gender.NONE
            if isinstance(combo, QComboBox):
                raw_gender = Gender.from_str(combo.currentData())

            if not raw_num and not raw_name:
                continue

            try:
                parsed.append(Student(number=raw_num, name=raw_name, gender=raw_gender))
            except ValueError:
                continue
        return parsed

    def _on_export_template(self) -> None:
        """현재 학생 명단이 포함된 엑셀 양식(.xlsx)을 저장하고 열기/확인 대화상자를 표시합니다."""
        students = self._get_current_table_students()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "학생 명단 엑셀 양식 저장",
            "학생명단_양식.xlsx",
            "Excel Workbook (*.xlsx);;All Files (*)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"

        try:
            saved_path = FileService.export_students_template(file_path, students)
            show_saved_file_message(
                self,
                "엑셀 양식 저장 완료",
                f"총 {len(students)}명의 학생 명단이 포함된 엑셀 양식이 저장되었습니다:\n{saved_path}",
                saved_path,
            )
        except Exception as exc:
            QMessageBox.critical(self, "양식 저장 오류", f"엑셀 파일 저장 중 오류가 발생했습니다:\n{exc}")

    def get_roster(self) -> List[Student]:
        """최종 검증된 학생 명단 리스트를 반환합니다."""
        return self._roster
