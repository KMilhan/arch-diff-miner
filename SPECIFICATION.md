# **ADL Diff Miner: Complete Specification (v2.0)**

## **1. 개요 (Overview)**

ADL Diff Miner v2.0은 Git 저장소의 커밋 히스토리를 순회하여 ADL(Architecture Description Language) 변경과 코드 변경, 커밋 의도(Intent), 그리고 변경이 일어난 배경(Context)을 함께 추출하는 데이터 마이닝 도구입니다.

v2.0의 목표는 (Context + Intent) -> (ADL Diff) 관계를 학습하는 Guiding LLM(DLM v0.1)을 위한 고품질 jsonl 데이터셋을 구성하는 것입니다. 이를 위해 v1.0이 제공하던 Intent/Code Diff/ADL Diff 추출 능력은 그대로 유지하면서, **context_signals** 블록을 새롭게 도입해 code diff 대상 파일들의 "사회적 신호"(변경 빈도, 참여자 등)를 추가로 기록합니다.

## **2. 핵심 요구사항 (Core Requirements)**

1. **설정 가능성 (Configurability):** 저장소 경로, ADL 파일명, 대상 코드 확장자, 출력 경로, 컨텍스트 분석 기간 등 모든 주요 변수를 Typer 기반 CLI 인자를 통해 주입합니다.
2. **구조화된 출력 (Structured Output):** jsonl 포맷으로 UTF-8 레코드를 스트리밍하며, v1.1에서 도입된 hunk 구조(`header`, `added`, `removed`, `context`)를 정식 스키마로 채택합니다.
3. **견고성 (Robustness):** 루트/머지 커밋, 빈 diff, 인코딩 오류, 리네임/삭제 등의 엣지 케이스를 우아하게 처리하고 필요한 경우 경고 로그를 남깁니다.
4. **[v2.0] 컨텍스트 마이닝 (Context Mining):** ADL 변경과 함께 touch된 code 파일들을 식별하고, 해당 파일들이 "직전" 커밋(parent) 기준으로 과거 N일 동안 얼마나 자주, 누가 변경했는지를 계산해 `context_signals` 블록으로 내보냅니다.

## **3. 커맨드 라인 인터페이스 (CLI) 사양**

도구는 Typer CLI를 통해 호출하며, v2.0에서는 컨텍스트 분석을 위한 신규 인자를 추가로 제공합니다.

```
uv run python -m arch_diff_miner mine \
    --repo "/path/to/spam-bootstrapper" \
    --adl-file "adl.yaml" \
    --code-exts .py --code-exts .rs \
    --output "training_dataset_v2.jsonl" \
    --context-days 90
```

* `--repo` (필수): 분석할 로컬 Git 저장소 경로.
* `--adl-file` (필수): 추적할 ADL 파일의 상대 경로. 현재는 정확 일치 + 대소문자 무시 비교만 지원합니다.
* `--code-exts` (선택, 기본 `.py`): 연관 코드 diff로 포함할 확장자. 인자를 반복해 여러 확장자를 전달할 수 있습니다.
* `--output` (선택, 기본 stdout): jsonl 결과를 쓸 경로. 지정하지 않으면 표준 출력에 스트리밍합니다.
* `[v2.0] --context-days` (선택, 기본 `90`): parent 커밋 시점을 기준으로 되돌아볼 일수(timespan). 이 기간 동안의 변경 내역을 기반으로 사회적 신호를 계산합니다.

> 팁: ADL 파일 glob 매칭이나 다중 경로 지원은 여전히 로드맵에 있으며, v2.0에서는 단일 경로 입력만 보장됩니다.

## **4. 출력 데이터 스키마 (JSONL) v2.0**

각 커밋 레코드는 Line-Delimited JSON으로 출력되며, 다음 블록을 포함해야 합니다.

| 블록 | 필드 | 타입 | 설명 |
| --- | --- | --- | --- |
| `commit` | `hash`, `parent_hash` | str | 대상 커밋과 첫 번째 부모 SHA. |
|  | `authored_at`, `committed_at` | str (ISO-8601 UTC) | 작성/커밋 타임스탬프. |
|  | `author`, `committer` | obj | `{ "name": str, "email": str }`. |
|  | `is_merge` | bool | 부모가 둘 이상인 경우 `true`. |
| `intent` | `message` | str | 커밋 메시지 전문. |
|  | `source` | obj | `{ "type": "commit_message" }` (향후 PR/이슈 확장 예정). |
| `adl_diff` | `path`, `previous_path?`, `status` | str | ADL 파일 diff 메타데이터. |
|  | `hunks` | list[obj] | `{ "header", "added", "removed", "context" }` 구조. |
|  | `stats` | obj | `{ "additions": int, "deletions": int }`. |
| `code_diffs` | list[obj] |  | 허용된 확장자만 포함. 각 항목은 `{ "path", "status", "extension", "language", "hunks", "stats" }`. |
| `[v2.0] context_signals` | `analysis_parent_hash` | str | 컨텍스트 기준 커밋 SHA (C(k)). |
|  | `analysis_timespan_days` | int | CLI에서 지정한 `--context-days`. |
|  | `files_analyzed` | list[str] | `code_diffs`에 등장한 파일 경로. |
|  | `aggregate_stats` | obj | `{ "total_commits", "total_unique_authors", "most_recent_change_days_ago" }`. |
|  | `per_file_stats` | list[obj] | 각 파일별 `{ "path", "churn_count", "unique_authors", "last_modified_days_ago", "top_authors"? }`. |
| `metadata` | `dataset_version` | str | 예: `"adl-diff-miner-schema-v2.0"`. |
|  | `generated_at` | str (ISO-8601 UTC) | 레코드 생성 시각. |

예시 (요약):

```json
{
  "commit": {
    "hash": "ac68f4b02babb01437789a99a292d1995485ba6b",
    "parent_hash": "ff6d26707692b8851dccca7ce6f338996e8953fe",
    "author": {"name": "KMilhan", "email": "kimmilhan@gmail.com"},
    "committer": {"name": "KMilhan", "email": "kimmilhan@gmail.com"},
    "authored_at": "2025-11-12T07:58:10Z",
    "committed_at": "2025-11-12T08:03:41Z",
    "is_merge": false
  },
  "intent": {
    "message": ":white_check_mark: align ADL logging correspondences",
    "source": {"type": "commit_message"}
  },
  "adl_diff": {
    "path": "adl.yaml",
    "status": "modified",
    "hunks": [
      {
        "header": "@@ -91,6 +91,13 @@ risks:",
        "added": ["  - id: R-3", "    owner: platform"],
        "removed": [],
        "context": ["risks:"]
      }
    ],
    "stats": {"additions": 42, "deletions": 2}
  },
  "code_diffs": [
    {
      "path": "tests/test_adl_validator.py",
      "status": "modified",
      "extension": ".py",
      "hunks": ["@@ -1,3 +1,6 @@"],
      "stats": {"additions": 60, "deletions": 3}
    }
  ],
  "context_signals": {
    "analysis_parent_hash": "ff6d26707692b8851dccca7ce6f338996e8953fe",
    "analysis_timespan_days": 90,
    "files_analyzed": ["tests/test_adl_validator.py"],
    "aggregate_stats": {
      "total_commits": 12,
      "total_unique_authors": 4,
      "most_recent_change_days_ago": 5
    },
    "per_file_stats": [
      {
        "path": "tests/test_adl_validator.py",
        "churn_count": 12,
        "unique_authors": 4,
        "last_modified_days_ago": 5,
        "top_authors": ["kimmilhan@gmail.com", "mlops-bot@example.com"]
      }
    ]
  },
  "metadata": {
    "dataset_version": "adl-diff-miner-schema-v2.0",
    "generated_at": "2025-11-12T08:04:05Z"
  }
}
```

## **5. 핵심 로직 및 엣지 케이스 처리 (v2.0)**

1. **커밋 순회:** `repo.iter_commits(paths=adl_file)` 또는 기존 `repo.walk()`를 사용해 ADL 파일을 touch한 커밋(target_commit = C(k+1))을 식별합니다. 루트 커밋(부모 없음)은 diff가 없어 건너뜁니다.
2. **부모/시점 식별:** `parent_commit = target_commit.parents[0]`을 기준으로 분석 시점을 정의합니다. `analysis_until = parent_commit.committed_datetime`, `analysis_since = analysis_until - timedelta(days=context_days)`로 범위를 계산합니다.
3. **Diff 생성:** `parent_commit.diff(target_commit, create_patch=True)`로 전체 diff를 구한 뒤 ADL 파일과 허용된 코드 확장자를 필터링해 `adl_diff`와 `code_diffs`를 구성합니다. 빈 diff는 훈련 레코드를 제외합니다.
4. **[v2.0] 컨텍스트 계산:** `code_diffs`에 나타난 파일 경로를 `target_files`로 정의합니다. 각 파일에 대해 `repo.iter_commits(parent_commit.id, paths=file_path, since=analysis_since, until=analysis_until)`를 호출해 과거 N일 간 커밋 목록을 만들고, 아래 통계를 도출합니다.
   * `churn_count = len(commits_for_file)`
   * `unique_authors = len(set(c.author.email for c in commits_for_file))`
   * `last_modified_days_ago = (analysis_until - commits_for_file[0].committed_datetime).days`
   * 필요 시 최근 작성자 상위 목록을 `top_authors`에 기록합니다.
5. **집계:** `per_file_stats`를 누적한 뒤 `aggregate_stats.total_commits = sum(churn_count)`, `aggregate_stats.total_unique_authors = len({email ...})`, `aggregate_stats.most_recent_change_days_ago = min(last_modified_days_ago)`로 계산합니다. 컨텍스트 대상 파일이 없으면 `context_signals`를 비우지 말고 빈 리스트/0 값을 명시합니다.
6. **머지 커밋:** 부모가 둘 이상인 경우 v1.0 정책과 동일하게 첫 번째 부모만 사용하되, `commit.is_merge`를 true로 설정해 다운스트림에서 병합 여부를 구분할 수 있게 합니다.
7. **인코딩 및 예외 처리:** diff decoding 중 UnicodeDecodeError가 발생하면 해당 파일을 건너뛰고 경고 로그를 남기며, 컨텍스트 계산 중 예외는 개별 파일에 한정해 처리하여 레코드 생성을 중단하지 않습니다.

## **6. 향후 개선 사항 (v2.1+)**

* **[v2.1] PR/Issue 연동:** intent 블록을 커밋 메시지뿐 아니라 연관 PR/Issue 토론 전체로 확장해 richer intent 신호를 제공합니다.
* **[v2.2] 기술 부채 컨텍스트:** pygount, radon 등을 사용해 parent 상태의 SLOC, Cyclomatic Complexity를 추출하여 `context_signals`에 포함합니다.
* **[v2.3] ADL 구조 컨텍스트:** parent ADL을 파싱해 변경된 컴포넌트의 직전 의존성 개수를 context에 추가합니다.
* **추가 백로그:** 대형 저장소를 위한 병렬 diff 생성, DB 출력 모드(`--output-db`), glob 기반 ADL 경로 매칭 등을 후속 릴리스에서 계속 추적합니다.
