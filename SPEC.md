# Scavenger 상세 기능 명세 및 개발 계획

## 개요
사용자 비활성 시간대에 Claude Code CLI를 활용하여 우선순위 기반 태스크를 자동 처리하는 Python CLI 도구

## 기술 결정사항
- **태스크 실행**: Claude Code CLI subprocess 호출
- **사용량 추적**: `claude /usage` 명령어로 % 기반 조회
- **태스크 형식**: 단순 텍스트 프롬프트 + 우선순위 + 작업 디렉토리
- **스케줄러**: 데몬 프로세스
- **자율 실행**: 시스템 규칙 주입으로 Claude가 직접 판단하도록 유도

---

## 1. 핵심 기능 목록

### 1.1 태스크 관리
| 기능 | 설명 | CLI 명령어 |
|------|------|-----------|
| 태스크 추가 | 프롬프트, 우선순위, 작업 디렉토리 지정 | `scavenger add --priority N --dir PATH "prompt"` |
| 태스크 목록 | 등록된 태스크 조회 | `scavenger list` |
| 태스크 삭제 | ID로 태스크 제거 | `scavenger remove ID` |
| 태스크 수정 | 우선순위/상태 변경 | `scavenger edit ID --priority N` |
| 태스크 상태 | pending/running/completed/failed | 자동 관리 |

### 1.2 스케줄 및 설정
| 기능 | 설명 | CLI 명령어 |
|------|------|-----------|
| 활성 시간대 설정 | 시작/종료 시간 | `scavenger config --active-start 01:00 --active-end 06:00` |
| 사용량 제한 | 요일별 최대 사용량 % 설정 | `scavenger config --usage-limit "mon:10,tue:20,wed:30,thu:50,fri:70,sat:10,sun:10"` |
| 기본 사용량 제한 | 미지정 요일의 기본값 | `scavenger config --usage-limit-default 20` |
| 사용량 리셋 시간 | 요일별 제한 초기화 시간 | `scavenger config --usage-reset-hour 6` |
| 태스크별 타임아웃 | 단일 태스크 최대 실행 시간 | `scavenger config --task-timeout 30m` |
| 설정 조회 | 현재 설정 확인 | `scavenger config --show` |

### 1.3 데몬 관리
| 기능 | 설명 | CLI 명령어 |
|------|------|-----------|
| 데몬 시작 | 백그라운드 프로세스 시작 | `scavenger start` |
| 데몬 중지 | 현재 작업 완료 후 종료 | `scavenger stop` |
| 긴급 정지 | 즉시 모든 작업 중단 | `scavenger stop --force` |
| 상태 확인 | 데몬 및 현재 작업 상태 | `scavenger status` |

### 1.4 결과 리포팅
| 기능 | 설명 | CLI 명령어 |
|------|------|-----------|
| 이메일 설정 | SMTP 설정 | `scavenger config --email user@example.com --smtp-host ...` |
| 리포트 시간 | 일일 리포트 전송 시간 | `scavenger config --report-time 07:00` |
| 수동 리포트 | 즉시 리포트 생성/전송 | `scavenger report [--send]` |
| 실행 로그 | 과거 실행 이력 조회 | `scavenger history [--date YYYY-MM-DD]` |

### 1.5 자율 처리 전략
사용자 입력 없이 자율적으로 태스크를 처리하기 위한 전략:

**Claude Code 호출 시 시스템 규칙 주입**:
태스크 프롬프트 앞에 다음 규칙을 자동으로 추가하여 Claude Code가 스스로 판단하도록 유도:
```
[Scavenger 자율 실행 모드]
- 이 태스크는 사용자 입력 없이 자동으로 실행됩니다.
- 판단이 필요한 상황에서는 가장 합리적인 선택을 직접 결정하세요.
- 확신이 없는 경우 보수적인 선택을 하세요.
- 작업 불가능한 상황이면 이유를 명시하고 종료하세요.
- 절대로 사용자 입력을 기다리지 마세요.
```

**실행 옵션**:
- `--dangerously-skip-permissions` 옵션으로 권한 프롬프트 우회
- `--print` 옵션으로 non-interactive 모드 실행

**폴백 처리**:
- **타임아웃**: 설정된 시간 초과시 태스크 중단 및 상태 기록
- **무한 대기 감지**: 일정 시간 출력이 없으면 태스크 중단

---

## 2. 데이터 구조

### 2.1 저장소 구조
```
~/.scavenger/
├── config.json          # 전역 설정
├── tasks.json           # 태스크 목록
├── history/             # 실행 이력
│   └── 2024-01-15.json
├── logs/                # 실행 로그
│   └── task_001.log
└── scavenger.pid        # 데몬 PID 파일
```

### 2.2 태스크 스키마
```json
{
  "id": "uuid",
  "prompt": "태스크 프롬프트 텍스트",
  "priority": 1,
  "working_dir": "/path/to/project",
  "status": "pending|running|completed|failed|paused",
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": null,
  "completed_at": null,
  "token_used": 0,
  "error": null,
  "output_summary": null
}
```

### 2.3 설정 스키마
```json
{
  "active_hours": {
    "start": "01:00",
    "end": "06:00",
    "timezone": "Asia/Seoul"
  },
  "limits": {
    "usage_limit_by_day": {
      "mon": 10,
      "tue": 20,
      "wed": 30,
      "thu": 50,
      "fri": 70,
      "sat": 10,
      "sun": 10
    },
    "usage_limit_default": 20,
    "usage_reset_hour": 6,
    "task_timeout_minutes": 30
  },
  "notification": {
    "email": "user@example.com",
    "smtp": {
      "host": "smtp.gmail.com",
      "port": 587,
      "username": "...",
      "password_env": "SCAVENGER_SMTP_PASSWORD"
    },
    "report_time": "07:00"
  },
  "claude_code": {
    "path": "claude",
    "extra_args": []
  }
}
```

---

## 3. 개발 단계 (Development Steps)

### Phase 1: 기본 구조 (MVP)
**목표**: 태스크 추가/실행이 가능한 최소 기능

| Step | 작업 | 상세 |
|------|------|------|
| 1.1 | 프로젝트 초기화 | Python 패키지 구조, pyproject.toml, CLI 진입점 |
| 1.2 | 저장소 모듈 | ~/.scavenger 디렉토리, JSON 파일 읽기/쓰기 |
| 1.3 | 태스크 모델 | 태스크 데이터 클래스, 상태 관리 |
| 1.4 | 태스크 CRUD | add, list, remove 명령어 구현 |
| 1.5 | Claude Code 연동 | subprocess로 CLI 호출, 출력 캡처 |
| 1.6 | 수동 실행 | `scavenger run` - 즉시 1개 태스크 실행 |

**검증**: `scavenger add`, `scavenger list`, `scavenger run` 테스트

### Phase 2: 스케줄링
**목표**: 지정 시간에 자동 실행

| Step | 작업 | 상세 |
|------|------|------|
| 2.1 | 설정 모듈 | config.json 관리, CLI 명령어 |
| 2.2 | 데몬 프로세스 | 백그라운드 실행, PID 관리, 시그널 처리 |
| 2.3 | 스케줄러 | 활성 시간대 체크, 주기적 태스크 실행 |
| 2.4 | 사용량 추적 | `claude /usage` 명령어로 현재 사용량 % 조회 |
| 2.5 | 제한 적용 | 사용량 % 제한, 태스크 타임아웃 |

**검증**: `scavenger start`, 지정 시간에 자동 실행 확인

### Phase 3: 안정성 & 로깅
**목표**: 안정적인 장시간 운영

| Step | 작업 | 상세 |
|------|------|------|
| 3.1 | 실행 이력 | history/ 디렉토리, 일별 기록 |
| 3.2 | 로그 시스템 | 태스크별 상세 로그, 로그 로테이션 |
| 3.3 | 에러 처리 | 예외 복구, 재시도 로직, 상태 복원 |
| 3.4 | 긴급 정지 | SIGTERM/SIGINT 처리, 안전한 종료 |
| 3.5 | 상태 조회 | `scavenger status` 상세 정보 |

**검증**: 장시간 실행, 에러 시나리오, 긴급 정지 테스트

### Phase 4: 리포팅
**목표**: 이메일로 결과 수신

| Step | 작업 | 상세 |
|------|------|------|
| 4.1 | 리포트 생성 | 일일 작업 요약 생성 |
| 4.2 | SMTP 연동 | 이메일 전송 기능 |
| 4.3 | 자동 발송 | 지정 시간에 리포트 전송 |
| 4.4 | 리포트 포맷 | HTML/텍스트 템플릿 |

**검증**: 이메일 수신 확인

### Phase 5: 고급 기능 (선택)
**목표**: 사용성 향상

| Step | 작업 | 상세 |
|------|------|------|
| 5.1 | 태스크 의존성 | 태스크 간 순서 지정 |
| 5.2 | 태스크 그룹 | 프로젝트별 태스크 그룹화 |
| 5.3 | 웹 UI | 간단한 로컬 웹 인터페이스 |
| 5.4 | 다중 LLM | Claude API 직접 호출, 다른 모델 지원 |

---

## 4. 파일 구조

```
scavenger/
├── pyproject.toml
├── README.md
├── PLAN.md
├── SPEC.md
└── src/
    └── scavenger/
        ├── __init__.py
        ├── __main__.py           # CLI 진입점
        ├── cli/
        │   ├── __init__.py
        │   ├── main.py           # Click/Typer 앱
        │   ├── task_commands.py  # add, list, remove
        │   ├── config_commands.py
        │   ├── daemon_commands.py
        │   └── report_commands.py
        ├── core/
        │   ├── __init__.py
        │   ├── task.py           # Task 모델
        │   ├── config.py         # Config 모델
        │   ├── executor.py       # Claude Code 실행
        │   ├── scheduler.py      # 스케줄러
        │   └── daemon.py         # 데몬 프로세스
        ├── storage/
        │   ├── __init__.py
        │   ├── base.py           # 저장소 인터페이스
        │   ├── json_storage.py   # JSON 파일 저장소
        │   └── history.py        # 이력 관리
        ├── notification/
        │   ├── __init__.py
        │   ├── email.py          # SMTP 이메일
        │   └── report.py         # 리포트 생성
        └── utils/
            ├── __init__.py
            ├── logging.py
            └── token_parser.py   # 토큰 사용량 파싱
```

---

## 5. 의존성

```toml
[project]
dependencies = [
    "typer>=0.9.0",      # CLI 프레임워크
    "rich>=13.0.0",       # 터미널 출력
    "pydantic>=2.0.0",    # 데이터 모델
    "python-daemon>=3.0", # 데몬 프로세스 (Unix)
    "apscheduler>=3.10",  # 스케줄러
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "ruff",
    "mypy",
]
```

---

## 6. 우선순위 및 일정 제안

| 우선순위 | Phase | 핵심 가치 |
|---------|-------|----------|
| P0 | Phase 1 | 기본 동작 - 태스크 추가/실행 |
| P0 | Phase 2 | 핵심 가치 - 자동 스케줄 실행 |
| P1 | Phase 3 | 안정성 - 장시간 운영 |
| P2 | Phase 4 | 편의성 - 결과 리포팅 |
| P3 | Phase 5 | 확장 - 고급 기능 |

---

## 7. 리스크 및 고려사항

1. **Claude Code 출력 형식**: 버전에 따라 `/usage` 출력 형식이 변경될 수 있음
2. **권한 문제**: `--dangerously-skip-permissions` 없이 실행 시 입력 대기 상태 처리
3. **데몬 안정성**: macOS/Linux 환경별 데몬 동작 차이
4. **사용량 조회 빈도**: `/usage` 호출 빈도와 정확도 트레이드오프
5. **자율 실행 규칙**: 시스템 규칙 주입이 Claude Code 동작에 미치는 영향 검증 필요
