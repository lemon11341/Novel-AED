# Novel AED MCP 연결

Novel AED는 AI가 읽고 호출하는 **로컬 stdio MCP 서버 + 스킬**이다. AI 모델의 실행·인증은 호스트가 담당한다. 서버는 원문·초안·승인 이력을 관리하며 임의 셸 실행, 네트워크 접속, 자체 모델 호출을 제공하지 않는다. 웹 서버나 공개 포트를 열지 않는다.

## 설치와 연결

### npm 패키지로 연결

최초 npm 게시 전에는 이 명령을 사용할 수 없다. 게시 이후에는 Node.js 22 이상과 Python 3.11 이상이 있는 터미널에서 `npx novel-aed setup`을 실행한다. 클라이언트를 선택하고 출력된 경로와 설정을 확인한 뒤 설치에 동의한다. 비대화형 설치는 다음과 같다.

```sh
npx novel-aed setup --client codex --write
npx novel-aed doctor
```

`--client codex|claude|cursor`를 지원한다. `--write` 없이 클라이언트를 지정하면 설정만 출력하고 어떤 파일이나 Python 의존성도 설치하지 않는다. `--client json`은 다른 MCP 호스트용 JSON만 출력하며 `--write`와 함께 사용할 수 없다. JSON 설정의 영구 실행 경로를 수동으로 사용하려면 먼저 지원 호스트의 setup을 완료해 실행 환경을 설치한 뒤 JSON 미리보기를 다시 실행한다. `doctor`와 `mcp`는 준비되지 않은 실행 환경을 자동 설치하지 않는다.

npm 설치는 호출한 현재 프로젝트에 연결하며, 작품은 별도 영구 폴더를 사용한다. Windows는 `%LOCALAPPDATA%/NovelAED`, macOS/Linux는 `$XDG_DATA_HOME/novel-aed`(기본 `~/.local/share/novel-aed`) 아래에 `runtimes/`와 `stories/`를 분리한다. `NOVEL_AED_HOME` 또는 `--home`으로 변경한다. 다른 프로젝트나 기존 작품에 연결할 때는 경로를 명시한다.

```sh
npx novel-aed setup --client codex --project /path/to/project --stories-root /path/to/stories --write
# 업데이트: 기존 연결·스킬을 백업하고 교체
npx novel-aed setup --client codex --write --replace
```

MCP 설정은 Python과 스크립트의 영구 절대 경로를 저장하므로 npm 캐시가 없어져도 작동한다. Python 자체를 다운로드하거나 전역 패키지로 설치하지 않는다. 설치한 Python이 PATH에 없다면 `NOVEL_AED_PYTHON`에 실행 파일 경로를 지정한다. 최초 설치는 PyPI에서 MCP 의존성을 받기 위한 네트워크 접속이 필요하다. 소설 처리와 MCP 실행 자체는 모델 호스트 외에 별도 네트워크를 사용하지 않는다.

### 설치 성공 후 첫 요청

npm setup 성공 안내는 연결한 프로젝트, 실제 작품 저장 경로와 새 작품·재개 요청문을 출력한다. 설치 성공은 호스트에서 도구가 보인다는 확인이 아니다.

1. 안내된 프로젝트를 선택한 AI 앱에서 열고 신뢰한다.
2. AI 앱을 다시 시작하거나 MCP 연결을 새로고침한다. 도구가 계속 보이지 않으면 새 대화를 시작하고 연결 설정을 확인한다. 스킬만으로 MCP 도구가 등록되지는 않는다.
3. 원문과 제목을 AI에 제공한 뒤 요청한다. Codex에서는 `$novel-aed`를 함께 호출할 수 있다.

   > Novel AED로 제공한 원문을 분석해줘. 제목은 [제목]이야. 필요하면 새 작품으로 초기화하고 분석 결과를 보여준 뒤 내 승인을 기다려.

재개할 때는 다음처럼 요청한다.

> Novel AED로 [작품 ID]를 이어서 진행해줘. 현재 상태와 과거 기록을 읽고, 승인 대기 결과가 있으면 먼저 보여주고 기다려.

작품 ID는 `list_stories`가 반환한 `my-story` 같은 상대 ID이며, 절대 경로나 `stories/my-story`가 아니다. 모르면 먼저 작품 목록을 요청한다. “계속해”나 이전 단계의 승인은 새 결과의 승인이 아니다.

setup 자체는 원문을 가져오지 않는다. 새 작품은 안내된 저장 경로 아래에 원문·초안·확정 회차·승인 이력을 보관한다. npm 기본 저장 위치는 연결한 프로젝트의 `stories/`가 아니므로 안내된 경로를 확인하고 작품 폴더 전체를 백업한다.

로컬 파일 저장은 오프라인 AI 처리를 뜻하지 않는다. 원문을 포함한 도구 결과는 호스트에 전달되며 모델 제공자의 정책에 따라 외부로 전송될 수 있다. 서버 자체는 모델을 호출하지 않고 별도 모델 API 키도 요구하지 않는다.

### 소스에서 연결

Python 3.11 이상으로 저장소에서 실행한다. MCP SDK 버전은 `requirements-mcp.txt`에 고정되어 있다. 기존 CLI에는 설치하지 않아도 된다.

Windows PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-mcp.txt
python scripts/setup_mcp.py --client codex --write
.venv/Scripts/python.exe scripts/check_mcp.py
```

macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mcp.txt
python3 scripts/setup_mcp.py --client codex --write
.venv/bin/python scripts/check_mcp.py
```

Codex는 신뢰한 프로젝트의 `.codex/config.toml`을 사용하며 스킬은 `.agents/skills/novel-aed/`에 설치한다. 연결한 AI 앱을 다시 열거나 MCP를 새로고침한다. 실행 중인 대화에 새 도구가 즉시 추가된다고 가정하지 않는다. [공식 MCP 설정 안내](https://developers.openai.com/codex/mcp), [공식 스킬 안내](https://developers.openai.com/codex/skills).

다른 호스트도 같은 서버를 사용한다.

```powershell
# 먼저 설정만 출력해 확인 (파일 변경 없음)
python scripts/setup_mcp.py --client claude
python scripts/setup_mcp.py --client cursor
# 선택한 호스트의 프로젝트 설정과 스킬을 설치
python scripts/setup_mcp.py --client claude --write
python scripts/setup_mcp.py --client cursor --write
```

- `codex`: `.codex/config.toml`, `.agents/skills/novel-aed/`
- `claude`: Claude Code용 `.mcp.json`, `.claude/skills/novel-aed/`
- `cursor`: `.cursor/mcp.json`, `.cursor/skills/novel-aed/`
- `json`: 다른 MCP 호스트에 붙여 넣을 `mcpServers` JSON만 출력하며 `--write`는 지원하지 않는다. 그 호스트가 사용하는 스킬 경로에 `skills/novel-aed/`를 복사하거나, 스킬 대신 `get_guidance(topic="skill")`을 읽도록 요청한다.

설정 도구는 기본적으로 파일을 쓰지 않는다. `--write`는 선택한 프로젝트의 설정만 병합하고 스킬을 복사한다. 기존 다른 설정은 유지하고, 이름이 같은 서버나 스킬이 다르면 덮어쓰지 않고 중단한다. `--write --replace`를 명시하면 기존 설정과 스킬을 백업한 뒤 해당 항목만 교체한다. 같은 설정과 같은 스킬의 반복 설치는 변경하지 않는다. 생성 설정은 절대 경로를 포함하므로 Git에서 제외하며, 저장소를 옮기면 경로를 다시 설정한다.

다른 폴더에서 Novel AED를 쓰려면 대상 프로젝트를 명시한다. 작품은 계속 **Novel AED 저장소의 `stories/`**에 보관되며, 대상 프로젝트의 동명 폴더를 읽지 않는다.

```powershell
python scripts/setup_mcp.py --client codex --project "C:/path/to/my-project" --write
```

수동 등록 시 `python scripts/setup_mcp.py --client json`의 `command`와 `args`를 사용한다. SDK가 설치된 `.venv`가 있으면 그 Python을 선택하고 없으면 설정 도구를 실행한 Python을 사용한다. 작업 디렉터리에 의존하지 않는 절대 경로이다. 작품 루트를 직접 지정하려면 서버 인자 `--stories-root <절대 경로>`를 바꾼다. 서버가 노출하는 파일 범위는 그 폴더 내부이다. 경로 이탈과 심볼릭 링크·junction은 거부하며, 작품 내부의 원문·설정·초안·확정 파일을 직접 편집하는 비협조적 로컬 프로그램에 대한 보안 경계는 아니다.

## AI에게 요청하기

Codex 예시:

> $novel-aed를 사용해줘. 등록된 작품과 현재 단계를 확인하고 승인 대기 결과가 있으면 먼저 보여줘.

새 작품:

> Novel AED로 이 원문을 분석해줘. 제목은 [제목]이야. 분석 결과를 보여준 뒤 내 승인을 기다려.

스킬은 도구를 설치하지 않는다. MCP 연결과 스킬 설치가 둘 다 필요하다. 스킬 없이도 `get_guidance`를 통해 같은 지침과 스키마를 읽을 수 있다. 실제 분석·집필은 사용자가 선택한 모델 하나가 순차 수행하며, 자기 검토는 독립 검증이 아니다.

## 도구 계약

작품 ID `story`는 설정된 작품 루트 기준의 상대 경로이다. 예를 들어 `my-story`, `imported/story-001`이며 절대 경로나 `stories/my-story`가 아니다. 파일 경로도 작품 기준이며 구분자는 `/`이다.

| 도구 | 역할 |
| --- | --- |
| `list_stories` | 작품 목록과 현재 단계, 잘못된 작품의 오류 표시 |
| `get_guidance` | 규칙·절차·스킬 또는 분석·개요·회차 지침과 제출 스키마 |
| `initialize_story` | 제목과 완전한 원문으로 새 폴더 초기화, 기존 폴더 덮어쓰기 금지 |
| `get_status` | 최신 revision, 단계, 대기 파일과 digest |
| `get_context` | 선호 설정, 원문 구간 수, 페이지별 파일 목록 |
| `read_source_chunk` | 손실 없는 원문 구간, ID와 문자 offset |
| `read_story_file` | 원문·설정·참고자료·초안·이력·회차·과거 기록을 문자 단위 페이지로 읽기 |
| `read_approved` | 승인된 분석 항목·개요·회차·승인 이력을 항목 단위 페이지로 읽기 |
| `set_preferences` | 첫 제출 전 선호 설정 전체 지정 |
| `add_reference` | 첫 제출 전 적용 범위를 포함한 새 `.md` 참고자료 추가 |
| `save_draft` | JSON 초안 또는 부분 초안 저장, 확정하지 않음 |
| `assemble_draft` | 구간별 분석 또는 연속 개요 묶음을 최종 초안으로 조립 |
| `submit_draft` | 전체 계약을 검증하고 이력을 고정하여 승인 대기로 전환 |
| `approve_result` | 해당 결과에 대한 실제 사용자 승인 메시지와 revision·digest를 기록 |
| `reject_result` | 사용자 수정 요청 기록, 기존 이력 보존, 승인 대기 해제 |
| `validate_story` | 입력 fingerprint·인용·설정 참조·분량·digest·확정 회차 사본 검증 |
| `measure_text` | 제목 제외 본문에서 Unicode 공백을 뺀 글자 수 계산 |

`novel-aed://workflow`, `novel-aed://rules` 리소스도 제공한다. 리소스를 읽지 못하는 호스트는 `get_guidance`를 사용하면 된다. 도구는 텍스트 JSON과 `structuredContent`를 반환하며 실행 오류는 MCP의 `isError`로 전달한다. [MCP 도구 규격](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), [사용한 공식 SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0).

### 페이지·초안·승인

목록·승인 항목 페이지는 `offset`과 `limit`, 원문 구간은 `src-0001` 등의 ID를 사용한다. 파일은 Unicode 문자 단위 offset으로 읽고 `next_offset`이 null이 될 때까지 이어 읽는다. `total`은 목록의 항목 수 또는 파일의 문자 수이다. 회차 본문은 길 수 있으므로 `read_approved(section="chapters", limit=1)`로 읽는다. 읽지 않은 페이지를 읽었다고 주장하면 안 된다.

선호 설정·참고자료 추가·초안 저장·조립·제출·승인·거절은 최신 revision이 필요하고 성공하면 revision을 증가시킨다. 새 revision을 다음 호출에 사용한다. 오래된 revision, 살아 있는 잠금, 잘못된 인용·분량·검토·digest는 거부된다. 장편 분석은 구간별 JSON을 저장하고 `assemble_draft(kind="analysis", part_names=[...], header={})`로 조립한다. 장편 개요는 각 파일에 `{"chapters": [...]}`를 저장하고, 나머지 개요 필드를 `header`에 넣어 조립한다. 전체 검증은 `submit_draft`에서 수행한다.

`awaiting_approval`이면 대기 파일의 실제 결과와 경로·revision·digest를 보여주고 멈춘다. 사용자에게 해당 결과를 보여준 **이후 현재 대화에 기록된 명시적 승인**만 `approve_result.message`에 넣는다. “계속해”, 처음의 제작 지시, 이전 단계 승인, AI의 판단은 새 결과의 승인이 아니다. 도구는 메시지의 발화자를 인증하지 못하며 의미·문학적 품질을 보장하지 않는다. 같은 원칙이 CLI에도 적용된다. 직접 상태 파일을 고쳐 승인이나 검증을 우회하지 않는다.

## 검증과 문제 해결

```powershell
# 실제 stdio 연결, 초기화, 도구 목록, 지침 조회. 작품은 읽거나 바꾸지 않는다.
.venv/Scripts/python.exe scripts/check_mcp.py
# 기존 CLI·서비스·설정·실제 MCP 프로토콜 통합 테스트
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

MCP 의존성이 없는 일반 Python으로 테스트하면 MCP 연결 테스트만 skip하고 기존 기능은 검사한다. 전체 테스트를 실행하기 전에는 각 테스트의 fixture 위치와 접근 범위를 별도로 확인한다. 배포 CLI 테스트는 성공·실패 경로의 설치 및 설정 작업을 대체 함수로 검사하고, 실제 미리보기 검사는 시스템 임시 폴더에 만든 빈 프로젝트만 사용한다. 이 배포 CLI 테스트는 실제 원고나 모델을 사용하지 않는다. 임시 fixture는 테스트 종료 시 정리하며, 실제 설치 검사는 별도의 smoke test에서 수행한다. 다른 통합 테스트의 접근 범위까지 이 설명으로 보장하지는 않는다.

일부 Windows 샌드박스는 Python asyncio의 로컬 소켓 초기화까지 막는다. 빈 asyncio 실행도 멈추는 환경에서는 허용된 일반 터미널에서 연결 진단·통합 테스트를 실행한다.

- `Python 3.11+ was not found`: 진단의 `Tried` 목록에서 실행 파일과 실패 원인을 확인한다. `NOVEL_AED_PYTHON`을 지정하면 다른 Python으로 자동 전환하지 않으므로 해당 경로와 버전을 바로잡는다.
- `no verified runtime`: 출력된 버전별 실행 경로를 확인한다. setup 때와 같은 `--home` 또는 `NOVEL_AED_HOME`으로 지원 클라이언트의 setup을 실행하고 `--write`를 지정한다. 업그레이드로 기존 연결을 교체할 때만 `--replace`도 지정한다. 최초 npm 게시 전에는 npm 명령 대신 위 소스 설치 절차를 사용한다.
- `No module named mcp`: 설정의 `command`가 SDK를 설치한 Python을 가리키는지 확인한다.
- 도구가 안 보임: 설정된 프로젝트를 신뢰했는지, 앱을 다시 열거나 연결을 새로고침했는지 확인한다. 앱마다 로컬 stdio 지원 여부가 다르며 원격 HTTP 전용 호스트에 이 서버를 직접 등록할 수는 없다.
- `Stale revision`: `get_status`를 다시 읽는다. 재시도 전 이미 성공한 작업인지 확인한다.
- 입력 변경 오류: 승인/분석된 작품의 원문·참고자료·선호 설정을 바꾸려면 새 버전 폴더로 초기화한다. 과거 결과를 자동 승인하지 않는다.
- 잠금 오류: 다른 작업이 실행 중인지 확인한다. 살아 있는 잠금을 지우지 않는다. 중단된 프로세스의 잔여 잠금임이 확인되면 파일 작업 절차에 따라 휴지통으로 옮긴다.
- 문학적 품질: 테스트는 프로토콜과 결정적 검증을 확인하며 실제 소설의 품질이나 호스트 AI가 모든 지침을 지켰음을 증명하지 않는다.
