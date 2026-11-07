# Novel AED — 소설 이어쓰기 도구

[English](README.md) | [한국어](README.ko.md)

## 다운로드해서 바로 시작하기

**[사용자용 ZIP 다운로드 (v0.1.1)](https://github.com/lemon11341/Novel-AED/releases/download/v0.1.1/novel-aed-0.1.1-download.zip)** · [릴리스 안내](https://github.com/lemon11341/Novel-AED/releases/tag/v0.1.1)

ZIP을 풀고 `Novel-AED-0.1.1` 폴더 전체를 AI 에이전트의 프로젝트로 여세요. Python 3.11 이상이 필요하며, 아래 폴더 방식은 npm·MCP 설치 없이 시작할 수 있습니다. 파일 수정·명령 실행이 가능한 AI 환경에서 원문과 제목을 제공하고 아래 첫 요청문을 사용하세요.

**사용하는 AI에 연결해, 승인한 단계부터 미완결 소설을 이어 쓰는 도구입니다.**

Novel AED는 로컬 MCP 서버와 스킬을 AI 에이전트에 연결합니다. 선택한 모델이 원문을 분석하고, 결말까지의 개요를 만든 뒤 회차별 집필과 자기 검토를 수행합니다. 원문·확정 설정·초안·승인 이력은 로컬 파일로 보관합니다.

## 처음 사용한다면

**가장 간단한 방법은 이 폴더 전체를 AI 에이전트의 프로젝트로 여는 것입니다.** Python 3.11 이상과 파일 수정·명령 실행이 가능한 AI 환경을 준비하고, 아래 [폴더로 시작하기](#폴더를-에이전트-프로젝트로-사용하기)를 따라가세요. Node.js나 MCP 설치는 필요하지 않습니다.

- AI가 Novel AED를 도구로 호출하게 하려면 [MCP 설치](#소스에서-mcp-설치)를 선택하세요. Codex·Claude Code·Cursor용 설정을 제공합니다.
- **npm 공개 배포는 아직 준비 중입니다.** 지금은 저장소 폴더 방식이나 소스 MCP 설치를 사용하세요. 검증된 `.tgz` 파일을 받았다면 [압축파일 설치 안내](docs/releasing.md#로컬-검증과-압축파일)를 따르세요.

AI 모델과 계정은 사용자가 이용하는 AI 환경에서 제공합니다. 일반 채팅에 원문만 첨부하는 방식으로는 이 도구를 실행할 수 없습니다.

## 주요 기능

- 인물, 사건·시간, 세계관, 서술, 문체, 주제, 복선, 감정선의 8개 축으로 분석
- 승인된 분석을 바탕으로 회차별 완급과 실제 결말 계획
- 원문 인용, 설정 참조, 회차 순서, 글자 수, 제출 결과의 무결성 검사
- 분석·개요·회차마다 명시적 사용자 승인을 받고 제출 이력 보존
- MCP 도구 17개와 스킬 제공, CLI에서도 같은 검증·승인 코드 사용

모델 실행과 인증은 사용하는 AI 환경이 담당하며 별도 모델 API 키를 요구하지 않습니다. 소설 작업과 자기 검토는 선택한 모델 하나가 순서대로 수행합니다.

## 폴더를 에이전트 프로젝트로 사용하기

저장소 폴더를 내려받아 프로젝트로 열면 MCP 설치나 npm 게시 없이 사용할 수 있습니다. **Python 3.11 이상**과 **로컬 파일 읽기·수정 및 터미널 실행이 가능한 AI 에이전트**가 필요합니다.

1. GitHub에서 **Code → Download ZIP**으로 내려받아 압축을 풀거나 Git으로 복제합니다.
2. 압축을 푼 **Novel-AED 폴더 전체**를 에이전트의 프로젝트·작업 폴더로 엽니다. README나 원문만 첨부하는 대신 저장소 전체를 작업 대상으로 지정합니다.
3. 원문 파일과 제목을 제공하고 다음처럼 요청합니다.

   > AGENTS.md, workflow/WORKFLOW.md, workflow/STAGES.md를 읽고 진행해줘. 원문은 [파일 경로]이고 제목은 [제목]이야. 필요하면 새 작품으로 초기화하고 분석 결과를 보여준 뒤 내 승인을 기다려.

`[파일 경로]`와 `[제목]`을 실제 값으로 바꾸세요. 원문은 `stories/inputs/` 폴더를 만들어 넣으면 Git 추적에서 제외됩니다. 개인 원고를 저장소 최상위에 두지 마세요. 먼저 `python --version`(macOS/Linux는 `python3 --version`)으로 Python 3.11 이상인지 확인하세요. 명령을 찾지 못하면 Python을 설치한 뒤 터미널과 AI 앱을 다시 여세요.

첫 작업이 끝나면 AI가 분석 결과와 저장 경로, digest를 보여주고 승인을 기다려야 합니다. 내용을 확인한 뒤 승인하거나 수정할 부분을 알려주세요. 분석·개요·회차는 각각 승인하며, 설치만으로 작품을 생성하거나 자동으로 끝까지 집필하지 않습니다.

에이전트가 분석·집필을 수행하고 `scripts/workspace.py`로 검증과 승인 이력을 관리합니다. 이 파일·CLI 방식은 Python 표준 라이브러리만 사용하므로 Node.js·npm·MCP 의존성을 설치하지 않아도 됩니다. `AGENTS.md`를 자동으로 읽지 않는 환경에서도 위 요청으로 규칙을 명시적으로 읽게 할 수 있습니다.

작품은 프로젝트 안의 `stories/`에 저장됩니다. 이동·백업할 때는 해당 작품 폴더 전체를 보존하세요. 다시 시작할 때는 프로젝트를 열고 다음처럼 요청합니다.

> stories/[작품 폴더]의 현재 상태와 과거 기록을 읽고 현재 단계부터 이어서 진행해줘. 승인 대기 결과가 있으면 먼저 보여주고 기다려.

첨부파일만 읽고 파일 수정이나 명령 실행을 할 수 없는 채팅 환경에서는 이 절차를 직접 실행할 수 없습니다. 지원하는 AI 환경에 호출 가능한 도구로 연결하려면 아래 MCP 설치 방법을 사용합니다.

## 소스에서 MCP 설치

현재 체크아웃에서 사용할 수 있는 설치 방법입니다. Python 3.11 이상과 로컬 stdio MCP를 지원하는 AI 환경이 필요합니다. Codex·Claude Code·Cursor의 연결 설정을 지원합니다.

### Windows PowerShell

저장소 폴더에서 실행합니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-mcp.txt
python scripts/setup_mcp.py --client codex --write
.venv/Scripts/python.exe scripts/check_mcp.py
```

### macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mcp.txt
python3 scripts/setup_mcp.py --client codex --write
.venv/bin/python scripts/check_mcp.py
```

다른 환경은 `codex`를 `claude` 또는 `cursor`로 바꿉니다. `--write`를 빼면 설정만 미리보기합니다. 다른 설정은 보존하고 충돌하는 기존 항목은 거부하며, `--write --replace`를 지정하면 Novel AED 연결과 스킬을 백업한 뒤 교체합니다.

소스 설치의 기본 대상은 이 저장소의 프로젝트와 `stories/`입니다. 다른 프로젝트에 연결하려면 `--project /절대/프로젝트/경로`를 지정하세요. 선택한 프로젝트를 AI 앱에서 열고 신뢰한 뒤 앱을 다시 시작하거나 MCP 연결을 새로고침합니다. 도구가 계속 보이지 않으면 새 대화를 시작하고 연결 설정을 확인하세요. 설치 성공은 AI 앱이 도구를 불러왔다는 확인이 아니며, 스킬만 설치하면 MCP 서버가 등록되지 않습니다.

수동 JSON 설정·저장 위치 변경·문제 해결은 [MCP 연결 안내](docs/mcp.md)를 참고하세요.

## AI에게 요청하기

Codex에서는 `$novel-aed`를 호출합니다. 다른 환경에서는 Novel AED 도구와 작업 지침을 사용하도록 요청합니다.

**새 작품 시작:**

> Novel AED로 제공한 원문을 분석해줘. 제목은 [제목]이야. 필요하면 새 작품으로 초기화하고 분석 결과를 보여준 뒤 내 승인을 기다려.

AI에 원문을 제공하면 미등록 작품은 새 폴더로 초기화합니다. 작품이 여러 개면 대상을 지정하세요.

**기존 작품 재개:**

> Novel AED로 [작품 ID]를 이어서 진행해줘. 현재 상태와 과거 기록을 읽고, 승인 대기 결과가 있으면 먼저 보여주고 기다려.

`[작품 ID]`에는 `list_stories`가 반환한 `my-story` 같은 ID를 넣습니다. 절대 경로나 `stories/my-story`가 아닙니다. ID를 모르면 먼저 등록된 작품 목록을 보여 달라고 요청하세요.

작업은 다음 순서로 진행합니다.

```text
분석 → 사용자 승인 → 개요 → 사용자 승인
     → 회차 집필·자기 검토 → 사용자 승인 → 다음 회차
```

제시된 결과를 명시적으로 승인해야 해당 단계가 확정됩니다. “계속해”는 새로운 결과의 승인으로 간주하지 않습니다. 수정을 요청해도 이전 제출 이력은 보존합니다.

## npm 배포

**최초 npm 게시는 아직 하지 않았습니다.** 다음 명령은 게시 후 사용할 배포 진입점이며, 현재는 위의 소스 설치를 사용할 수 있습니다.

Node.js 22 이상, npm, Python 3.11 이상이 필요합니다.

```sh
npx novel-aed setup
# 현재 프로젝트에 비대화형으로 설치:
npx novel-aed setup --client codex --write
npx novel-aed doctor
```

대화형 setup은 연결 설정을 보여준 뒤 설치 여부를 확인합니다. `--client`만 지정하고 `--write`를 생략하면 미리보기만 합니다. Python 자체를 다운로드하지 않으며 MCP 의존성은 격리된 실행 환경에 설치합니다.

설치에 성공하면 연결한 프로젝트, 실제 작품 저장 경로, 복사해서 사용할 새 작품·재개 요청문을 출력합니다. 선택한 AI 앱에서 해당 프로젝트를 열고 신뢰한 뒤 앱을 다시 시작하거나 MCP 연결을 새로고침하고 요청문을 사용하세요. setup은 원문을 가져오지 않으며, AI 앱이 도구를 불러왔는지까지 확인하지는 않습니다.

`--client json`은 수동 설정용 JSON만 출력하며 `--write`와 함께 사용할 수 없습니다. JSON의 영구 실행 경로를 사용하려면 먼저 지원 클라이언트로 설치한 뒤 JSON 미리보기를 다시 실행합니다. `doctor`와 `mcp`는 실행 환경이 없더라도 자동 설치하지 않습니다.

npm 설치는 실행 환경을 npm 캐시 밖에 두고 작품을 별도로 저장합니다.

| 운영체제 | 기본 저장 루트 |
| --- | --- |
| Windows | `%LOCALAPPDATA%/NovelAED` |
| macOS / Linux | `$XDG_DATA_HOME/novel-aed`, 기본 `~/.local/share/novel-aed` |

루트 아래 `runtimes/`와 `stories/`를 분리합니다. `--home` 또는 `NOVEL_AED_HOME`으로 루트를, `--stories-root`로 기존 작품 폴더를 지정할 수 있습니다. 소스 설치와 npm 설치의 기본 위치는 다르며, npm 설치는 명시적으로 지정하지 않는 한 연결한 프로젝트의 `stories/`를 사용하지 않습니다. 설치 결과에 표시된 저장 경로 아래에 새 작품의 원문·초안·확정 회차·승인 이력을 보관하므로 작품 폴더 전체를 백업하세요. npm 갱신이나 캐시 정리로 작품을 삭제하지 않습니다.

새 버전으로 연결을 바꿀 때는 `npx novel-aed setup --client codex --write --replace`를 사용합니다. 검증된 압축파일로 설치하거나 npm에 게시하는 방법은 [배포 안내](docs/releasing.md)에 있습니다.

## 파일과 개인정보

작품 폴더는 다음과 같이 구성됩니다.

```text
source.md          원문
preferences.json   언어·분량·사용자 희망사항
references/        참고자료와 적용 범위
drafts/            수정 가능한 JSON 초안
history/           보존된 제출 결과
state.json         진행 상태·확정 결과·승인 이력
chapters/          확정 회차 사본
```

작품 폴더와 기존 `data/`는 Git과 npm 배포에서 제외합니다. 별도로 백업하세요. Novel AED 자체는 모델을 호출하지 않습니다. 도구는 로컬에서 실행되지만 도구가 반환한 원문 등의 내용은 AI 환경에 전달되며, 사용하는 모델 제공자의 데이터 정책에 따라 외부로 전송될 수 있습니다. 로컬 저장이 AI 처리까지 오프라인이라는 뜻은 아닙니다. 진단 결과를 공유할 때 호스트 자격 증명을 포함하지 말고, 설치 경로에도 개인 디렉터리 이름이 드러날 수 있음에 유의하세요.

결정적 검증은 문학적 품질이나 의미상 일관성을 보장하지 않습니다. 서버는 전달받은 승인 메시지를 기록하지만 실제 발화자를 인증하지 못합니다. 자기 검토도 같은 모델이 수행하며 독립 검증이 아닙니다.

## CLI와 개발

파일 기반 CLI는 Python 표준 라이브러리만으로 사용할 수 있습니다.

```sh
python scripts/workspace.py init stories/my-story --source /원문/경로.txt --title "작품 제목"
python scripts/workspace.py status stories/my-story
```

현재 활성화한 Python 환경에 MCP 의존성을 설치한 뒤 테스트와 패키징을 실행합니다.

```sh
npm test
npm run package
python scripts/verify_package.py artifacts
python scripts/smoke_package.py artifacts
```

배포본 검사는 압축파일을 임시 프로젝트에 설치해 MCP 호출과 영구 저장 위치를 확인합니다. CI는 Windows/Linux와 Python 3.11/3.12 조합으로 구성했습니다. npm 게시 작업은 수동 릴리스 워크플로에서 명시적으로 선택합니다.

## 문서

- [MCP 설치와 도구](docs/mcp.md)
- [작업 절차와 CLI 명령](workflow/WORKFLOW.md)
- [단계별 지침](workflow/STAGES.md)과 [JSON 스키마](workflow/schemas/)
- [에이전트 규칙](AGENTS.md)과 [스킬](skills/novel-aed/SKILL.md)
- [연구 참고와 적용 한계](docs/research.md)
- [배포와 릴리스](docs/releasing.md)

기존 데이터베이스는 작업 절차 문서의 읽기 전용 내보내기를 사용합니다. 과거 결과를 자동 승인하지 않습니다.

## 라이선스

[MIT](LICENSE)
