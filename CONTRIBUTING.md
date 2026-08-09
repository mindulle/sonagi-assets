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
