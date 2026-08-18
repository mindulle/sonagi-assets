# Contributing Guidelines

이 문서는 `sonagi-eagle-gallery` 프로젝트의 이슈 및 코드 기여(Pull Request) 워크플로우에 대한 가이드라인입니다. 팀 내 모든 기여자 및 AI 에이전트는 아래 규칙을 엄격히 준수해야 합니다.

## 1. 이슈 관리 (Issue Tracking)
모든 작업(Task)의 할당과 상태 관리는 **Paperclip** 컨트롤 플레인을 통해 진행됩니다. (예: `CEO-881`)
새로운 작업을 시작하기 전에 반드시 Paperclip 이슈를 할당(`in_progress`)받은 후 진행하세요.

## 2. 브랜치 전략
작업을 시작할 때는 항상 `main` 브랜치를 기준으로 새로운 기능 브랜치를 생성합니다.
브랜치 이름에는 가능한 Paperclip 이슈 ID를 포함하여 목적을 명확히 합니다.

* **기능 추가:** `feat/CEO-881-api-integration`
* **버그 수정:** `fix/CEO-227-cors-error`
* **리팩토링:** `refactor/CEO-572-cleanup`

## 3. 커밋 메시지 규칙 (Conventional Commits)
커밋 메시지는 반드시 [Conventional Commits](https://www.conventionalcommits.org/) 형식을 따릅니다.

* `feat:` 새로운 기능 추가
* `fix:` 버그 수정
* `docs:` 문서 수정
* `style:` 코드 포맷팅, 세미콜론 누락, 코드 변경이 없는 경우
* `refactor:` 코드 리팩토링
* `test:` 테스트 코드 추가 및 수정
* `chore:` 빌드 업무 수정, 패키지 매니저 수정

**예시:** `feat: 디자인 큐레이션 API 연동 (CEO-881)`

## 4. 코드 스타일 및 훅 (Pre-commit)
본 프로젝트는 `.pre-commit-config.yaml`을 통해 코드 스타일을 관리합니다.
* **Python:** `ruff` (포맷팅 및 린트)
* **JS/JSON/기타:** `biome`

커밋 전 자동으로 훅이 실행되므로, 훅 통과에 실패한 경우 코드를 수정한 뒤 다시 커밋하세요.

## 5. Pull Request (PR) 가이드라인 ⭐ (매우 중요)
GitHub에 PR을 생성할 때는 다음 사항을 반드시 지켜주세요:

1. **PR 제목 규칙:** PR 제목에 반드시 **Paperclip 이슈 ID (예: `CEO-881`)**를 포함해야 합니다.
   * `feat: 디자인 큐레이션 API 연동 추가 (CEO-881)`
2. **이유:** GitHub Actions(`.github/workflows/paperclip-sync.yml`)가 PR 제목에서 정규식(`CEO-[0-9]+`)을 통해 이슈 ID를 추출합니다.
3. **상태 자동 동기화:** PR이 `main` 브랜치에 **Merge** 되면, 위 Actions 워크플로우가 자동으로 Paperclip API를 호출하여 해당 이슈에 성공 코멘트를 남기고 상태를 `done`으로 변경합니다.
4. 따라서 **작업이 끝났다고 Paperclip 이슈를 수동으로 `done` 처리하지 마시고, PR을 올린 뒤 Merge 되기를 기다리세요.**

## 6. 리뷰 및 병합 (Merge)
* 리뷰어의 승인(Approve)을 받은 후에만 `main` 브랜치로 병합(Merge)이 가능합니다.
* 테스트가 실패하거나 린트 에러가 있는 경우 병합이 제한될 수 있습니다.

## 7. 알려진 이슈 (Known Issues)

### 7.1 배포(파드 재시작) 직후 MCP 세션 끊김 (CEO-938)
`asset_hub_app.py`의 `/mcp/sse` + `/mcp/messages` 엔드포인트는 Python MCP SDK의
`SseServerTransport`를 사용합니다. 이 트랜스포트는 세션 상태(발급된 `session_id` ↔
스트림 매핑)를 서버 프로세스의 **인메모리**로만 관리합니다.

**증상:** ArgoCD를 통해 새 이미지가 배포되어 파드가 재시작되면, 그 이전에 발급된 모든
MCP 세션이 즉시 무효화됩니다. 이미 연결되어 있던 에이전트(MCP 클라이언트)가 재시작 이전에
발급받은 `session_id`로 `POST /mcp/messages`를 계속 호출하면, 다음 에러가 발생합니다:

```
Error POSTing to endpoint (HTTP 404): Could not find session
```

**원인:** MCP SDK의 `SseServerTransport.handle_post_message`가 `session_id`를 자신의
인메모리 딕셔너리(`_read_stream_writers`)에서 조회하는데, 파드가 재시작되면 이 딕셔너리가
비워지기 때문입니다. 표준 MCP 프로토콜/SDK 차원에서 세션을 영속화하거나 클라이언트가
자동으로 재연결하도록 강제하는 메커니즘은 현재 버전(SDK 1.27.x)에 내장되어 있지 않습니다.

**현재 대응 (운영 가이드):**
- 배포(`chore: update K8s manifests to deploy vX.Y.Z` PR merge) 직후에는, 이미 이 서버에
  연결되어 있던 에이전트/MCP 클라이언트 세션에서 `push_to_canvas`, `assets_search` 등
  모든 MCP 툴 호출이 실패할 수 있습니다. `Could not find session` 에러가 보이면 **재시도하지
  말고**, MCP 클라이언트(에이전트 세션)를 재시작하여 `GET /mcp/sse`로 새 세션을 다시 발급받으세요.
- 이는 알려진 제약이며, 파드가 재시작될 때마다(신규 배포, OOM, 노드 재스케줄 등) 재현됩니다.

**향후 검토 과제 (미착수):**
- MCP SDK의 최신 Streamable HTTP 트랜스포트(`mcp.server.streamable_http`)로 마이그레이션하고,
  세션/이벤트 스토어를 Redis 등 외부 저장소로 백엔드화하면 파드 재시작을 넘어 세션을 유지할 수
  있음. 다만 이는 트랜스포트 계층 전체를 교체하는 큰 변경이라 별도 이슈(CEO-933 아키텍처 개편과
  함께)로 계획하고 스테이징 검증 후 진행할 것.
