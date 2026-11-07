# 파일 기반 작업 절차

## 시작과 재개

실제 글 작성은 연결한 AI 에이전트의 선택 모델 하나가 수행한다. 로컬 MCP와 스킬로 연결하려면 `docs/mcp.md`를 따른다. MCP는 공식 Python SDK가 필요하고, 아래 CLI는 Python 3.11 이상의 표준 라이브러리만으로 실행된다. 별도 모델 API 키는 도구가 요구하지 않는다.

MCP에서는 `get_guidance`로 규칙·단계별 스키마를 읽고 `list_stories` → `get_status` → `get_context`로 시작한다. `read_source_chunk`, `read_story_file`, `read_approved`의 페이지를 끝까지 읽는다. 초안은 `save_draft`와 필요시 `assemble_draft`로 저장하고 `submit_draft`로 제출한다. `approve_result`와 `reject_result`도 아래 CLI와 같은 검증을 사용한다. MCP의 초안 저장·조립·선호 설정·참고자료 추가 역시 revision을 증가시키므로 반환된 최신 값을 사용한다. CLI로 직접 초안을 편집하는 것만으로는 revision이 바뀌지 않는다.

```powershell
python scripts/workspace.py init stories/my-story --source C:/path/story.txt --title "작품 제목"
python scripts/workspace.py status stories/my-story
python scripts/workspace.py context stories/my-story
```

`context`는 원문을 손실 없이 `src-0001` 등의 10,000자 구간으로 나눈 결과, 승인된 상태, 참고자료 파일 경로를 출력한다. 장편은 전체 출력을 한 번에 읽지 말고 구간별로 읽는다. 참고자료 경로가 나왔다고 내용까지 읽은 것은 아니다. 자료의 적용 시대·범위를 확인하고 본편과 충돌하면 본편을 우선한다.

폴더 구조:

- `source.md`: 보존할 본편 원문
- `preferences.json`: 출력 언어, 회차 수·분량 선택 방식, 사용자 희망사항
- `references/`: 세계관 자료와 각 자료의 적용 범위
- `drafts/`: 수정 가능한 분석·개요·본문·자기 검토 JSON
- `history/`: 제출한 원본 JSON. 수정하지 않는다.
- `state.json`: 승인된 분석·개요·회차, 현재 대기 결과, revision, 승인 기록
- `chapters/`: 확정 회차의 읽기 쉬운 Markdown 사본. 상태의 본문이 기준이다.

## 선호 설정

분석 전 `preferences.json`을 편집한다. `count_mode`와 `length_mode`는 각각 `recommended` 또는 `custom`이다. 직접 지정할 때는 `chapters_count`(양의 정수), `target_chars`(100~12000)를 넣는다. 추천 시 모델이 분석에 근거해 선택 이유와 압축의 한계를 개요에 기록한다. 분량은 제목과 Unicode 공백을 제외한 본문 글자 수이며 정확히 맞춰야 한다. 문장을 자르거나 군더더기를 넣어 맞추지 않는다.

## 단계와 제출 형식

`workflow/schemas/*.json`은 기계 검증 계약이다. 단계별 세부 지시는 `STAGES.md`에 있다.

1. **analysis**: `{"parts": [분석 구간 결과, ...]}`. 각 원문 구간을 빠짐없이 순서대로 분석한다. 각 원소는 `analysis.json` 스키마를 따른다. 긴 작품은 구간별 초안을 저장하고 마지막에 묶는다.
2. **outline**: `outline.json` 계약. 승인된 설정 ID를 사용한다. 남은 전개 속도 평가와 근거, 회차별 장면·완급, 실제 결말을 포함한다. 장편은 초안을 연속된 회차 묶음으로 저장한 뒤 전체를 조립해 검증한다. 회차 수 상한은 없다.
3. **chapter**: `{"draft": draft.json 계약, "review": review.json 계약}`. 다음 미확정 회차 하나만 작성한다. 같은 모델이 현재 본문을 다시 읽고 자기 검토한다. 중간·높음 문제가 있거나 verdict가 revise이면 수정하고 새 본문으로 다시 검토한다. 수정 전 검토를 재사용하지 않는다.

```powershell
python scripts/workspace.py submit stories/my-story --input stories/my-story/drafts/analysis.json --revision 0
python scripts/workspace.py validate stories/my-story
```

제출하면 revision이 증가하고 `awaiting_approval`이 된다. 에이전트는 결과 내용, 한계, 경로, digest를 사용자에게 보여주고 멈춘다. 승인 대기 중 중복 제출은 거부된다.

## 승인과 수정

사용자가 그 결과를 명시적으로 승인한 후에만 최신 status의 revision과 digest로 실행한다.

```powershell
python scripts/workspace.py approve stories/my-story --revision 1 --digest <status의-digest> --message "사용자의 실제 승인 메시지"
```

수정 요청이 오면 결과를 보존한 채 대기를 해제하고 요청을 반영한 새 초안을 제출한다.

```powershell
python scripts/workspace.py reject stories/my-story --revision 1 --reason "사용자의 수정 요청"
```

마지막 회차 승인 후 `complete`가 된다. 자동으로 후속 회차를 추가하지 않는다. 작업 중 중단되면 status부터 다시 읽는다. 프로세스가 중단되어 `.workflow.lock`만 남았다면 다른 작업이 실행 중인지 확인한 뒤 해당 잠금 파일을 휴지통으로 옮긴다.

## 검증의 범위

스크립트는 구간 누락, 실제 인용, 설정·복선 ID, 회차 순번·개수, 분량, 검토 인용, 대기 결과 digest, 입력 변경, revision을 검사한다. 검토가 실제로 충실했는지, 인용이 주장을 의미상 뒷받침하는지, 승인 메시지의 진위, 문학적 품질까지 보장하지 않는다. 단계 규칙과 사용자 검토를 함께 사용한다. 직접 파일 수정이나 비협조적인 다른 도구에 대한 보안 경계는 아니다.

## 기존 데이터

`data/novel-aed.sqlite3`는 보존한다. `stories/imported/legacy-export.json`에는 기존 작품과 작업 기록의 전체 JSON이 있고 각 `story-NNN` 폴더에 원문·참고자료와 `legacy-project.json`, `legacy-jobs.json`이 있다. 과거 결과는 보존하되 새 상태에 자동 승인하지 않는다. 기존 승인 분석·개요·회차가 있으면 먼저 사용자에게 가져오기 범위를 확인한다. 현재 단계를 이어가기 전에 과거 기록을 읽고 중복 집필을 피한다.

다른 기존 DB는 다음 명령으로 읽기 전용 내보내기가 가능하다. 대상 폴더는 새 경로여야 한다.

```powershell
python scripts/workspace.py export-legacy data/novel-aed.sqlite3 stories/another-import
```
