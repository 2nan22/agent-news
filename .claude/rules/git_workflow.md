# Rule: Git Workflow

## 브랜치 전략

```
main        ← 프로덕션 브랜치 (직접 push 금지, dev에서 PR로만 병합)
  └── dev   ← 개발 통합 브랜치
        ├── feat/crew-agents
        ├── feat/tavily-tool
        ├── fix/ollama-connection
        └── chore/docker-setup
```

### 브랜치 규칙
- `main`: 절대 직접 push 금지. dev에서 PR(--no-ff)로만 병합
- `dev`: 통합 브랜치. feature 브랜치에서 PR로 병합
- `feat/*`: 새 기능
- `fix/*`: 버그 수정
- `refactor/*`: 리팩토링 (로직 변경 없음)
- `chore/*`: 빌드, 설정, 의존성 변경
- `docs/*`: 문서만 변경

브랜치명 규칙: 영문 소문자, 하이픈 구분 (예: `feat/financial-analyst-agent`)

---

## Conventional Commits

```
<type>(<scope>): <subject>

[body - optional]
[footer - optional]
```

**Types:** `feat` | `fix` | `refactor` | `test` | `docs` | `chore` | `style` | `perf`

**Examples:**
```
feat(agents): add Financial_Analyst agent with Ollama LLM
fix(tools): handle Tavily rate-limit with graceful fallback
chore(docker): add extra_hosts for Linux Ollama access
docs(claude): add architecture rules for module responsibilities
```

**Subject 규칙:**
- 50자 이내
- 현재 시제 (add, fix, update — not added, fixed, updated)
- 마침표 없음

---

## PR 워크플로우

```bash
# 1. feature 브랜치 생성
git checkout dev && git pull origin dev
git checkout -b feat/my-feature

# 2. 작업 후 커밋
git add <specific files>
git commit -m "feat(scope): subject"

# 3. push 및 PR 생성 (base는 항상 dev, 절대 main 아님)
git push origin feat/my-feature
gh pr create --base dev --title "[feat] Feature name" --body "..."

# 4. PR 병합 (Merge Commit, --no-ff)
gh pr merge --merge --delete-branch
```

**PR 제목 형식:** `[feat] / [fix] / [chore] 기능명`
**병합 방식:** Merge Commit (--no-ff) — Squash 금지

---

## 세션 종료 체크리스트

```
[ ] feat/* 브랜치에서 작업 완료
[ ] WIP 커밋 없음 (필요시 git rebase -i로 정리)
[ ] git push origin feat/...
[ ] gh pr create --base dev
[ ] gh pr merge --merge --delete-branch
[ ] 세션 파일 → prompts/_complete/ 로 이동
```

---

## 마일스톤 → main 병합 기준

| 마일스톤 | 기준 |
|---------|------|
| M1 — Infrastructure `v0.1.0` | Docker + 스켈레톤 완성 |
| M2 — Core Crew `v0.2.0` | 에이전트 + Tavily 도구 E2E 동작 |
| M3 — Polish `v0.3.0` | 출력 포맷, 에러 처리, 문서화 완성 |
