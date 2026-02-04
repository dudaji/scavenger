# Scavenger

**Automated task runner for Claude Code during inactive hours**

Scavenger is a CLI tool that automatically executes your Claude Code tasks during off-peak hours (e.g., overnight), making efficient use of your unused token budget. Wake up to find your tasks completed with a detailed report delivered to your inbox.

---

[English](#english) | [한국어](#한국어)

---

## English

### Features

- **Smart Scheduling** - Configure active hours (e.g., 01:00-06:00) when tasks should run
- **Usage Limit Management** - Set per-day token usage limits to control resource consumption
- **Priority Queue** - Tasks are processed by priority (1=highest, 10=lowest)
- **Email Reports** - Receive daily execution summaries via email
- **Web UI** - Monitor tasks and status through a Streamlit-based dashboard
- **Autonomous Execution** - Tasks run with Claude Code in autonomous mode

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/scavenger.git
cd scavenger

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Quick Start

```bash
# 1. Add a task
scavenger add "Refactor the authentication module for better error handling" -p 3

# 2. Start the daemon (runs scheduler + web UI)
scavenger start

# 3. Check status
scavenger status
```

### Usage

#### Adding Tasks

```bash
# Add a task with default priority (5)
scavenger add "Write unit tests for the user service"

# Add a high-priority task
scavenger add "Fix the login bug in production" --priority 1

# Add a task for a specific directory
scavenger add "Update documentation" --dir /path/to/project
```

#### Managing Tasks

```bash
# List pending tasks
scavenger list

# List all tasks including completed
scavenger list --all

# Remove a task
scavenger remove <task-id>

# Run a task manually (without waiting for active hours)
scavenger run <task-id>
```

#### Daemon Control

```bash
# Start daemon and web UI
scavenger start

# Start daemon only (no web UI)
scavenger start --no-web

# Start in foreground (for debugging)
scavenger start --foreground

# Stop daemon and web UI
scavenger stop

# Force stop
scavenger stop --force

# Check daemon status
scavenger daemon status

# View daemon logs
scavenger daemon logs
scavenger daemon logs --follow
```

#### Configuration

```bash
# Show current configuration
scavenger config show

# Set active hours (when tasks will run)
scavenger config set --active-start 01:00 --active-end 06:00

# Set usage limits by day (percentage)
scavenger config set --usage-limit "mon:20,tue:30,wed:20"

# Set default usage limit
scavenger config set --usage-limit-default 25

# Set task timeout (minutes)
scavenger config set --task-timeout 45

# Configure email notifications
scavenger config set --email your@email.com
scavenger config set --smtp-host smtp.gmail.com
scavenger config set --smtp-port 587
scavenger config set --smtp-username your@gmail.com

# Reset to defaults
scavenger config reset
```

#### Reports

```bash
# Generate a text report
scavenger report generate

# Generate HTML report
scavenger report generate --html

# Save report to file
scavenger report generate --output report.txt

# Send report via email
scavenger report send

# Test email configuration
scavenger report test

# Preview HTML report in browser
scavenger report preview
```

#### History

```bash
# Show today's execution history
scavenger history show

# Show history for a specific date
scavenger history show 2024-01-15

# Show last 7 days
scavenger history show --days 7

# Show statistics
scavenger history stats

# List dates with available history
scavenger history dates

# View detailed log for a task
scavenger history task <task-id>

# Clean old history (keep last 30 days)
scavenger history clean --days 30
```

### Configuration Reference

Configuration is stored in `~/.scavenger/config.json`.

| Setting | Description | Default |
|---------|-------------|---------|
| `active_hours.start` | Start time for task execution | `01:00` |
| `active_hours.end` | End time for task execution | `06:00` |
| `active_hours.timezone` | Timezone for scheduling | `Asia/Seoul` |
| `limits.usage_limit_by_day` | Per-day usage limits (%) | `20` for all days |
| `limits.usage_limit_default` | Default usage limit (%) | `20` |
| `limits.usage_reset_hour` | Hour when daily limit resets | `6` |
| `limits.task_timeout_minutes` | Maximum task execution time | `30` |
| `notification.email` | Email address for reports | - |
| `notification.smtp.host` | SMTP server | `smtp.gmail.com` |
| `notification.smtp.port` | SMTP port | `587` |
| `notification.report_time` | Daily report send time | `07:00` |

### Email Setup (Gmail)

1. Enable 2-Step Verification in your Google Account
2. Generate an App Password: Google Account → Security → App passwords
3. Set the environment variable:
   ```bash
   export SCAVENGER_SMTP_PASSWORD="your-app-password"
   ```
4. Configure Scavenger:
   ```bash
   scavenger config set --email your@gmail.com
   scavenger config set --smtp-username your@gmail.com
   ```
5. Test the configuration:
   ```bash
   scavenger report test
   ```

### Directory Structure

```
~/.scavenger/
├── config.json          # Configuration file
├── tasks.json           # Task queue
├── scavenger.pid        # Daemon PID file
├── web.pid              # Web UI PID file
├── logs/
│   ├── daemon.log       # Daemon logs
│   └── tasks/           # Per-task execution logs
│       └── <task-id>.log
└── history/
    └── YYYY-MM-DD.json  # Daily execution history
```

### How It Works

1. **Task Addition**: You add tasks with prompts describing what Claude Code should do
2. **Daemon Scheduling**: The daemon runs on a 60-second loop, checking if it's within active hours
3. **Usage Check**: Before executing, it queries Claude Code's `/usage` to ensure you're within limits
4. **Task Execution**: Tasks are executed with Claude Code in autonomous mode (`--print --dangerously-skip-permissions`)
5. **Result Recording**: Results are logged and stored in execution history
6. **Reporting**: At the configured time, a daily report is sent via email

### Web UI

Access the web dashboard at `http://localhost:8121` when the daemon is running. The web UI provides:
- Real-time daemon status monitoring
- Task queue visualization
- Configuration management
- Execution history viewing

### Requirements

- Python 3.12+
- Claude Code CLI installed and configured

---

## 한국어

### 소개

Scavenger는 야간 등 비활성 시간대에 Claude Code 작업을 자동으로 실행하는 CLI 도구입니다. 사용하지 않는 토큰 예산을 효율적으로 활용하여, 아침에 일어나면 완료된 작업과 상세 리포트를 확인할 수 있습니다.

### 주요 기능

- **스마트 스케줄링** - 작업 실행 시간대 설정 (예: 01:00-06:00)
- **사용량 제한 관리** - 요일별 토큰 사용량 제한 설정
- **우선순위 큐** - 우선순위에 따른 작업 처리 (1=가장 높음, 10=가장 낮음)
- **이메일 리포트** - 일일 실행 결과 이메일로 수신
- **웹 UI** - Streamlit 기반 대시보드로 작업 및 상태 모니터링
- **자율 실행** - Claude Code 자율 모드로 작업 실행

### 설치

```bash
# 저장소 클론
git clone https://github.com/yourusername/scavenger.git
cd scavenger

# uv로 설치 (권장)
uv pip install -e .

# 또는 pip으로 설치
pip install -e .
```

### 빠른 시작

```bash
# 1. 작업 추가
scavenger add "인증 모듈을 리팩토링하여 에러 처리 개선" -p 3

# 2. 데몬 시작 (스케줄러 + 웹 UI)
scavenger start

# 3. 상태 확인
scavenger status
```

### 사용법

#### 작업 추가

```bash
# 기본 우선순위(5)로 작업 추가
scavenger add "사용자 서비스에 대한 단위 테스트 작성"

# 높은 우선순위 작업 추가
scavenger add "프로덕션 로그인 버그 수정" --priority 1

# 특정 디렉토리에서 작업 추가
scavenger add "문서 업데이트" --dir /path/to/project
```

#### 작업 관리

```bash
# 대기 중인 작업 목록
scavenger list

# 완료된 작업 포함 전체 목록
scavenger list --all

# 작업 제거
scavenger remove <task-id>

# 수동으로 작업 실행 (활성 시간대 무시)
scavenger run <task-id>
```

#### 데몬 제어

```bash
# 데몬 및 웹 UI 시작
scavenger start

# 데몬만 시작 (웹 UI 없이)
scavenger start --no-web

# 포그라운드에서 시작 (디버깅용)
scavenger start --foreground

# 데몬 및 웹 UI 중지
scavenger stop

# 강제 중지
scavenger stop --force

# 데몬 상태 확인
scavenger daemon status

# 데몬 로그 확인
scavenger daemon logs
scavenger daemon logs --follow
```

#### 설정

```bash
# 현재 설정 확인
scavenger config show

# 활성 시간대 설정 (작업 실행 시간)
scavenger config set --active-start 01:00 --active-end 06:00

# 요일별 사용량 제한 설정 (%)
scavenger config set --usage-limit "mon:20,tue:30,wed:20"

# 기본 사용량 제한 설정
scavenger config set --usage-limit-default 25

# 작업 타임아웃 설정 (분)
scavenger config set --task-timeout 45

# 이메일 알림 설정
scavenger config set --email your@email.com
scavenger config set --smtp-host smtp.gmail.com
scavenger config set --smtp-port 587
scavenger config set --smtp-username your@gmail.com

# 기본값으로 초기화
scavenger config reset
```

#### 리포트

```bash
# 텍스트 리포트 생성
scavenger report generate

# HTML 리포트 생성
scavenger report generate --html

# 파일로 저장
scavenger report generate --output report.txt

# 이메일로 리포트 발송
scavenger report send

# 이메일 설정 테스트
scavenger report test

# 브라우저에서 HTML 리포트 미리보기
scavenger report preview
```

#### 히스토리

```bash
# 오늘의 실행 이력 확인
scavenger history show

# 특정 날짜의 이력 확인
scavenger history show 2024-01-15

# 최근 7일 확인
scavenger history show --days 7

# 통계 확인
scavenger history stats

# 이력이 있는 날짜 목록
scavenger history dates

# 특정 작업의 상세 로그 확인
scavenger history task <task-id>

# 오래된 이력 정리 (최근 30일만 유지)
scavenger history clean --days 30
```

### 설정 레퍼런스

설정 파일 위치: `~/.scavenger/config.json`

| 설정 | 설명 | 기본값 |
|-----|------|-------|
| `active_hours.start` | 작업 실행 시작 시간 | `01:00` |
| `active_hours.end` | 작업 실행 종료 시간 | `06:00` |
| `active_hours.timezone` | 스케줄링 시간대 | `Asia/Seoul` |
| `limits.usage_limit_by_day` | 요일별 사용량 제한 (%) | 모든 요일 `20` |
| `limits.usage_limit_default` | 기본 사용량 제한 (%) | `20` |
| `limits.usage_reset_hour` | 일일 제한 초기화 시각 | `6` |
| `limits.task_timeout_minutes` | 최대 작업 실행 시간 | `30` |
| `notification.email` | 리포트 수신 이메일 | - |
| `notification.smtp.host` | SMTP 서버 | `smtp.gmail.com` |
| `notification.smtp.port` | SMTP 포트 | `587` |
| `notification.report_time` | 일일 리포트 발송 시간 | `07:00` |

### 이메일 설정 (Gmail)

1. Google 계정에서 2단계 인증 활성화
2. 앱 비밀번호 생성: Google 계정 → 보안 → 앱 비밀번호
3. 환경 변수 설정:
   ```bash
   export SCAVENGER_SMTP_PASSWORD="앱-비밀번호"
   ```
4. Scavenger 설정:
   ```bash
   scavenger config set --email your@gmail.com
   scavenger config set --smtp-username your@gmail.com
   ```
5. 설정 테스트:
   ```bash
   scavenger report test
   ```

### 디렉토리 구조

```
~/.scavenger/
├── config.json          # 설정 파일
├── tasks.json           # 작업 큐
├── scavenger.pid        # 데몬 PID 파일
├── web.pid              # 웹 UI PID 파일
├── logs/
│   ├── daemon.log       # 데몬 로그
│   └── tasks/           # 작업별 실행 로그
│       └── <task-id>.log
└── history/
    └── YYYY-MM-DD.json  # 일일 실행 이력
```

### 동작 원리

1. **작업 추가**: Claude Code가 수행할 작업을 프롬프트로 추가
2. **데몬 스케줄링**: 데몬이 60초 간격으로 활성 시간대인지 확인
3. **사용량 확인**: 실행 전 Claude Code의 `/usage`를 조회하여 제한 내인지 확인
4. **작업 실행**: Claude Code 자율 모드로 작업 실행 (`--print --dangerously-skip-permissions`)
5. **결과 기록**: 결과를 로깅하고 실행 이력에 저장
6. **리포트 발송**: 설정된 시간에 일일 리포트를 이메일로 발송

### 웹 UI

데몬 실행 중 `http://localhost:8121`에서 웹 대시보드에 접속할 수 있습니다. 웹 UI 기능:
- 실시간 데몬 상태 모니터링
- 작업 큐 시각화
- 설정 관리
- 실행 이력 확인

### 요구 사항

- Python 3.12+
- Claude Code CLI 설치 및 설정 완료

---

## License

MIT License
