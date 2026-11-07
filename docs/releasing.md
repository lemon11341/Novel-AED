# 배포·릴리스

이 저장소는 npm 패키지 `novel-aed`로 배포하도록 구성되어 있다. 현재 준비 버전은 `package.json`의 `0.1.1`이며 실제 npm 게시·GitHub push·태그 생성은 이 설정 작업에 포함하지 않는다. 패키지 이름의 사용 가능 여부와 게시 계정의 권한은 최초 게시자가 확인한다.

## 배포 구성

- `package.json`: 공개 메타데이터, `novel-aed` 실행 명령, 배포 파일 허용 목록. npm 런타임 의존성·자동 설치 hook 없음.
- `bin/novel-aed.mjs`: `setup`, `doctor`, `mcp`, `--help`, `--version`. Node.js 22 이상과 Python 3.11 이상 필요.
- `scripts/install_runtime.py`: 패키지 내용 hash별 실행 환경을 영구 경로에 설치하고 공식 MCP SDK를 격리된 venv에 설치. 완료 marker와 입력 hash로 준비 상태 확인. 중단된 설치는 같은 코드로 재시도할 수 있으며 살아 있는 설치 잠금은 제거하지 않음.
- `scripts/setup_mcp.py`: 프로젝트별 MCP 설정과 스킬 설치. `--replace`에서 백업 후 해당 연결만 교체.
- `scripts/verify_package.py`: 패키지의 필수 파일, 경로 이탈·링크·중복 항목 및 개인 자료 제외 검사.
- `scripts/smoke_package.py`: 실제 `.tgz`를 격리된 위치에 풀어 빈 프로젝트에 설치한 뒤, npm 캐시가 없는 상태에서도 MCP 연결과 작품 저장이 작동하는지 검사.

작품은 npm 패키지 안에 넣지 않는다. `stories/`, `data/`, `.env`, `.venv/`, `.git/`, 호스트 설정, 생성 스킬 사본, 테스트 fixture는 배포 허용 목록 밖이다. `artifacts/`도 Git·npm에서 제외한다. 서버는 npm 캐시가 아닌 별도 runtime 경로에서 실행되고, 작품은 버전 간 공유하는 별도 `stories/`에 보관한다. 패키지 업데이트는 작품 파일을 마이그레이션하거나 승인하지 않는다.

## 로컬 검증과 압축파일

Node.js/npm과 Python 3.11 이상으로 실행한다. Python 환경에는 `requirements-mcp.txt`를 설치한다. Windows의 저장소 전용 venv를 사용한다면 먼저 활성화하거나 아래 `python`을 `.venv/Scripts/python.exe`로 바꾼다. `npm test`도 같은 환경의 Python을 PATH에서 사용해야 한다.

```sh
python -m pip install -r requirements-mcp.txt
npm test
npm run package
python scripts/verify_package.py artifacts
python scripts/smoke_package.py artifacts
```

`npm run package`는 `artifacts/novel-aed-0.1.1.tgz`를 만든다. 실제 버전은 `package.json`을 따른다. `verify_package.py`의 폴더 인자는 `.tgz`가 정확히 하나 있을 때만 동작하므로 여러 버전을 남겨뒀다면 특정 파일을 지정한다. 테스트용 생성물은 기존 작품과 분리된 임시 폴더에서 처리한다. 일부 Windows 샌드박스가 asyncio를 막으면 일반 허용 터미널에서 MCP 테스트를 실행한다.

최초 npm 게시 전에 배포본을 공유하려면 이 **검증된 `.tgz`**를 사용한다. 레포 전체를 압축해 개인 원고를 섞지 않는다. 소비자는 다음처럼 로컬 배포본을 사용할 수 있다.

```sh
npm exec --package ./novel-aed-0.1.1.tgz -- novel-aed setup --client codex --write
```

받은 `.tgz`를 소비자가 선택한 프로젝트 폴더에 복사한 뒤 위 명령을 실행한다. 다른 위치에 보관했다면 `./novel-aed-0.1.1.tgz`를 그 파일의 실제 경로로 바꾼다. 경로에 공백이 있으면 따옴표로 감싼다. 이 명령은 현재 프로젝트의 설정을 바꾼다. Python 의존성 설치는 setup에서 수행한다. 단순한 `npm install`이나 npx 패키지 취득 단계에는 자동 실행 hook이 없다.

## CI와 검토용 릴리스

`ci.yml`은 push/PR에서 Windows·Linux × Python 3.11·3.12 조합으로 Python/Node 테스트, 실제 npm pack, 배포 파일 검사와 설치 smoke 검사를 실행한다. Linux/Python 3.12에서 검증한 `.tgz`를 Actions artifact로 남긴다. 이는 원격 CI가 실제 실행되어 통과했다는 뜻이 아니며, 저장소에 반영 후 Actions 결과를 확인해야 한다.

`release.yml`은 **수동 실행만** 지원하며 `publish=false`가 기본이다. 이 모드에서는 동일한 빌드·검증과 artifact 생성만 수행한다. push나 태그 생성만으로 npm에 게시하지 않는다. 저장소의 `npm-release` GitHub Environment에 필요한 검토자와 태그 제한을 설정할 수 있다.

## 최초 npm 게시

1. 계정과 패키지 이름의 소유·사용 권한을 확인한다. `npm view novel-aed`로 현재 등록 여부를 확인할 수 있지만 빈 이름이라는 확인은 예약이나 권한 보장이 아니다. 이름을 바꾼다면 메타데이터뿐 아니라 `scripts/distribution.py`의 이름 검사·파일명 검사, 문서·테스트도 함께 맞춘다.
2. 검증한 버전을 `package.json`에 기록하고 README의 “최초 게시 전” 안내를 실제 상태에 맞춘다. 변경사항을 검토해 커밋·push하고 `v<version>` 태그를 준비한다. 이 문서는 해당 GitHub 작업을 자동 수행하지 않는다.
3. 소유자의 일반 터미널에서 `npm login` 후 **검증된 tarball**로 최초 게시한다. 토큰이나 비밀번호를 저장소·채팅·워크플로 파일에 넣지 않는다.

```sh
npm publish ./artifacts/novel-aed-0.1.1.tgz --access public
```

4. npm의 패키지 설정에서 GitHub Actions Trusted Publisher를 등록한다: owner `lemon11341`, repository `Novel-AED`, workflow `release.yml`, environment `npm-release`. OIDC를 사용하므로 장기 npm 토큰을 GitHub Secret에 저장할 필요가 없다. [npm Trusted Publishing 공식 안내](https://docs.npmjs.com/trusted-publishers/).

최초 버전을 위 절차로 수동 게시한 뒤에는 같은 버전을 다시 워크플로로 게시하지 않는다. npm 버전은 재사용할 수 없다. 이후 다음 버전을 준비하고 해당 태그에서 Release workflow를 `publish=true`로 실행한다. publish job은 모든 플랫폼 검증 후 `v<package.json version>` 태그 일치를 확인하고 OIDC와 provenance로 **검증한 artifact 자체**를 게시한다. 태그를 만들거나 이미 게시한 버전을 덮어쓰지 않는다.

## 갱신과 운영 한계

- Python MCP SDK는 `requirements-mcp.txt`에서 고정한다. 전이 의존성은 설치 시 PyPI에서 해석되므로 의존성 갱신 때 동일한 플랫폼 테스트를 재실행한다.
- 사용자 설치가 가리키는 기존 runtime과 작품을 자동 삭제하지 않는다. 새 버전에는 별도 runtime을 만들고 `setup --write --replace`로 연결을 갱신한다. 기존 config와 스킬은 백업되며 변경된 사용자 스킬도 보존된다.
- 이 설치 도구는 자체 모델·모델 계정·API 키를 제공하지 않는다. 로컬 stdio MCP를 지원하는 호스트가 필요하다. 원격 HTTP 전용 서비스용 공개 서버는 제공하지 않는다.
- `skills/novel-aed/SKILL.md`는 원본 배포 스킬이다. 스킬 저장소 경로를 지원하는 설치 도구로도 배포할 수 있지만 스킬만 받으면 MCP 런타임과 연결은 설치되지 않는다.

## GitHub에서 내려받아 쓰는 ZIP

GitHub의 Code → Download ZIP으로 받은 저장소는 README의 폴더 방식으로 바로 사용할 수 있다. Python 3.11 이상과 파일·명령 도구가 있는 AI 에이전트가 필요하며 MCP나 npm 설치는 필수가 아니다. 저장소 전체 대신 사용자용 최소 파일만 공유하려면 다음 명령을 실행한다.

```sh
python scripts/build_download.py
```

`artifacts/novel-aed-<version>-download.zip`에 허용 목록의 코드·문서, 빈 stories 폴더, .gitignore만 담는다. 기존 원고·인증정보·호스트 설정은 포함하지 않는다. 소비자는 ZIP을 풀고 최상위 Novel-AED 폴더를 AI 프로젝트로 열어 README를 따른다. 이 ZIP은 소스 실행용이며 개발 테스트 파일은 포함하지 않는다. GitHub Release에 첨부하는 작업은 소유자가 별도로 수행한다.
