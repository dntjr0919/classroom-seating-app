# 교실 자리 배치 프로그램 (Classroom Seating Arrangement Program - PyQt6)

PyQt6 기반의 모듈형 단독 실행 데스크톱 애플리케이션으로, 학생 명단 관리(수동 편집 및 엑셀 업로드), 대화형 교실 책상 레이아웃 설정(짝꿍형·시험 대형·모둠형), 고정석(Pin) 유지 랜덤 배치, 드래그 앤 드롭 수동 자리 바꿈, 그리고 엑셀(`.xlsx`) 및 한글(`.hwp`)/PDF/HTML 내보내기를 지원합니다.

## 1. 프로젝트 디렉터리 구조

```
classroom_seating_app/
├── main.py                     # 애플리케이션 진입점, 메인 윈도우 컨트롤러, PyInstaller 리소스 경로 헬퍼
├── requirements.txt            # 필수 패키지 의존성 목록
├── README.md                   # 프로젝트 구조 및 PyInstaller 빌드 가이드
├── models/
│   ├── __init__.py             # 모델 패키지 초기화 및 클래스 익스포트
│   └── classroom_models.py     # Student(학생), Seat(좌석), ClassroomGrid(교실 격자), CellState, PresetType
├── services/
│   ├── __init__.py             # 서비스 패키지 초기화
│   ├── seating_service.py      # 전체 랜덤 배치, 고정석(Pin) 유지 랜덤 배치, 수동 스왑 및 제약 조건 검증
│   └── file_service.py         # 엑셀(.xlsx/.xls) 입출력, HWP(win32com) 자동화 및 PDF/HTML 폴백 내보내기
└── views/
    ├── __init__.py             # 뷰 패키지 초기화
    ├── student_dialog.py       # 학생 명단 관리 대화상자 (테이블 행 추가/수정/삭제 + 엑셀 업로드)
    ├── grid_designer.py        # 대화형 N x M 좌석 레이아웃 편집기 및 프리셋(짝꿍형/시험대형/모둠형)
    └── seating_view.py         # 메인 좌석 보드 뷰 (시각적 책상 카드, 잠금 토글, 드래그/클릭 스왑, 우클릭 고정 배정)

```

## 2. 패키지 설치 (`requirements.txt`)

```
pip install -r requirements.txt

```

```
PyQt6>=6.5.0
pandas>=2.0.0
openpyxl>=3.1.0
xlrd>=2.0.1
reportlab>=4.0.0
pywin32>=306; sys_platform == "win32"
pyinstaller>=6.0.0

```

## 3. 실행 및 PyInstaller (`--onedir`) 패키징 명령어

### 개발 환경에서 바로 실행

```
python main.py

```

### PyInstaller `--onedir` 빌드 명령어 (Windows 기준)

프로젝트 루트 폴더(`main.py`가 위치한 경로)에서 아래 명령어를 실행하면 `dist/ClassroomSeating/` 폴더 안에 단독 실행 파일(`ClassroomSeating.exe`)과 의존성 라이브러리가 함께 패키징됩니다.

```
pyinstaller --noconfirm --onedir --windowed ^
    --name "ClassroomSeating" ^
    --hidden-import=openpyxl ^
    --hidden-import=pandas ^
    --hidden-import=reportlab ^
    --hidden-import=win32com.client ^
    main.py

```

### macOS / Linux 터미널 한 줄 빌드 명령어

```
pyinstaller --noconfirm --onedir --windowed --name "ClassroomSeating" --hidden-import=openpyxl --hidden-import=pandas --hidden-import=reportlab main.py

```

## 4. 핵심 기능 요약

1. **학생 명단 관리 (`views/student_dialog.py`, `services/file_service.py`)**

   * `번호`, `이름`, `성별(남/여/선택안함)` 필드를 테이블에서 직접 추가·편집·삭제할 수 있습니다.

   * `번호`와 `이름` 중 최소 하나가 입력되었는지 검증하며 중복 학생을 방지합니다.

   * 엑셀(`.xlsx`, `.xls`) 업로드 시 `번호`, `이름`, `성별` 헤더를 자동 매핑하며, 헤더가 없는 파일은 열 순서(0번=번호, 1번=이름, 2번=성별)로 자동 폴백합니다.

2. **유연한 책상 레이아웃 설정 (`views/grid_designer.py`, `models/classroom_models.py`)**

   * 사용자가 `N행 × M열` 마스터 격자 크기를 자유롭게 지정할 수 있습니다.

   * 각 셀을 클릭하여 `활성 책상` → `복도/통로` → `비활성 공간`으로 상태를 순환 토글할 수 있습니다.

   * `짝꿍형(2열 1조 + 통로)`, `시험 대형(1열 단독 + 통로)`, `모둠형(2×2 4인 클러스터)` 프리셋 버튼을 제공합니다.

3. **자리 배치 알고리즘 및 수동 조작 (`services/seating_service.py`, `views/seating_view.py`)**

   * **고정석 유지 랜덤 배치**: `📌 고정` 토글이 켜진 좌석(또는 우클릭으로 사전 배정된 학생)을 그대로 유지한 채 나머지 학생만 빈 활성 좌석에 무작위로 배치합니다.

   * **전체 완전 랜덤 배치**: 모든 잠금을 해제하고 전체 학생을 무작위로 다시 섞어 배치합니다.

   * **수동 맞바꾸기 (Swap & Drag)**: 두 책상을 차례대로 클릭하거나 마우스로 드래그 앤 드롭하여 즉시 자리를 맞바꿀 수 있습니다.

   * **사전 제약 검증**: 활성 책상 수가 전체 학생 수보다 적거나 고정 좌석 수가 활성 책상 수를 초과하면 경고 창을 띄웁니다.

4. **파일 내보내기 (`services/file_service.py`)**

   * **엑셀(`.xlsx`)**: 교실 실제 배치를 반영한 시각적 레이아웃 시트(`자리배치표`, 복도는 좁은 빈 열로 처리, 책상은 두꺼운 테두리와 `[번호] 이름` 중앙 정렬)와 번호/이름순 학생 좌표 목록 시트(`학생별 배정명단`) 2개를 생성합니다.

   * **한글(`.hwp`) 및 인쇄 문서 폴백**: Windows에 한컴오피스 한글과 `pywin32`가 설치된 경우 COM 자동화로 `.hwp` 표 문서를 생성하며, 미설치 환경이나 타 OS에서는 프로그램 오류 없이 즉시 인쇄 가능한 `.pdf` 또는 `.html` 문서로 자동 폴백 저장합니다.