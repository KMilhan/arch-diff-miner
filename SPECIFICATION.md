# **ADL Diff Miner: Complete Specification (v1.0)**

## **1\. 개요 (Overview)**

ADL Diff Miner는 Git 저장소의 커밋 히스토리를 스캔하여, 아키텍처 기술 언어(ADL) 파일의 변경과 그에 수반되는 소스 코드 변경 및 커밋 의도(Intent)를 추출하는 데이터 마이닝 도구입니다.

이 도구의 목적은 (Code Diff \+ Intent) \-\> (ADL Diff) 관계를 학습하는 'Diff-to-Diff' LLM 번역기(DLM v0.1)를 위한 고품질의 훈련 데이터셋을 생성하는 것입니다.

이 문서는 v1.0의 공식 사양을 정의합니다.

## **2\. 핵심 요구사항 (Core Requirements)**

1. **설정 가능성 (Configurability):** 저장소 경로, ADL 파일명, 대상 코드 확장자 등 모든 주요 변수는 하드코딩되지 않고, 커맨드 라인 인터페이스(CLI)를 통해 주입되어야 합니다.
2. **구조화된 출력 (Structured Output):** 단순 콘솔 로그가 아닌, LLM 학습에 즉시 사용 가능한 표준 형식(예: line-delimited JSON, jsonl)으로 데이터를 출력해야
   합니다.
3. **견고성 (Robustness):** 루트 커밋, 머지(merge) 커밋, 빈 커밋, 인코딩 오류 등 Git 히스토리의 다양한 엣지 케이스(edge case)를 우아하게 처리해야 합니다.

## **3\. 커맨드 라인 인터페이스 (CLI) 사양**

이 도구는 Python의 Typer 모듈을 기반으로 다음 CLI 인자를 받아야 합니다.
 
\--repo "/path/to/repo" \\  
\--adl-file "adl.yaml" \\  
\--code-exts .py .yaml .json \\  
\--output "training\_dataset.jsonl"

* \--repo (필수): 분석할 로컬 Git 저장소의 경로.
* \--adl-file (선택, 기본값: `adl.yaml`): 저장소 내에서 추적할 ADL 파일의 상대 경로.
* \--code-exts (선택, 기본값: .py): ADL 변경과 연관시킬 소스 코드 파일의 확장자 목록 (공백으로 구분).
* \--output (선택, 기본값: stdout): 결과를 저장할 출력 파일 경로. 지정하지 않으면 표준 출력(stdout)으로 jsonl 데이터를 스트리밍합니다.

> 현재 구현은 ADL 경로를 **정확 일치 + 대소문자 무시** 방식으로만 비교합니다. 향후 glob-style 패턴 지원은 로드맵에 있지만 아직 CLI에서는 단일 경로 문자열만 정상 동작합니다.

## **4\. 출력 데이터 스키마 (JSONL)**

도구는 \--output으로 지정된 파일 또는 stdout에 **Line-Delimited JSON (.jsonl)** 형식으로 UTF-8 레코드를 스트리밍해야 합니다. 각 레코드는 아래 필드를 포함합니다.

| 블록 | 필드 | 타입 | 설명 |
| --- | --- | --- | --- |
| `commit` | `hash` | str | 대상 커밋 SHA. |
|  | `parent_hash` | str | 첫 번째 부모 SHA. |
|  | `authored_at` / `committed_at` | str (ISO-8601 UTC) | 작성/커밋 타임스탬프. |
|  | `author` / `committer` | obj | `{ "name": str, "email": str }`. committer가 없는 경우 author 정보 재사용 가능. |
|  | `is_merge` | bool | 부모가 둘 이상이면 `true`. |
| `intent` | `message` | str | 커밋 메시지 전문. |
|  | `source` | obj | `{ "type": "commit_message" }` (추후 PR/이슈 연동 확장). |
| `adl_diff` | `path` | str | 최신 커밋에서의 ADL 경로. |
|  | `previous_path` | str? | 리네임 발생 시 이전 경로. |
|  | `status` | str | `added`/`modified`/`deleted`/`renamed`. |
|  | `hunks` | list[obj] | 각 요소는 `{ "header", "added", "removed", "context" }`. 최소 1개 이상 존재해야 함. |
|  | `stats` | obj | `{ "additions": int, "deletions": int }`. |
| `code_diffs` | list[obj] |  | 허용한 확장자(.py 등)만 포함. 각 요소는 `{ "path", "status", "extension", "language", "hunks", "stats" }`. |
| `metadata` | `dataset_version` | str | 예: `"adl-diff-miner-schema-2025-01"`. |
|  | `generated_at` | str (ISO-8601 UTC) | 레코드 생성 시각. |

예시 (요약):

```json
{
  "commit": {
    "hash": "0bff65a6fb3b0b7bfbc6f5cb9f947f1f22dc5678",
    "parent_hash": "9a2b3a4c5d6e7f8091a2b3c4d5e6f708192a3b4c",
    "authored_at": "2025-11-12T07:58:10Z",
    "committed_at": "2025-11-12T08:03:41Z",
    "author": {"name": "KMilhan", "email": "milhan@example.com"},
    "committer": {"name": "KMilhan", "email": "milhan@example.com"},
    "is_merge": false
  },
  "intent": {
    "message": "ADL: add Loki logging stack",
    "source": {"type": "commit_message"}
  },
  "adl_diff": {
    "path": "architectures/decisions.yaml",
    "previous_path": "adl.yaml",
    "status": "renamed",
    "hunks": [
      {
        "header": "@@ -10,3 +10,8 @@",
        "added": ["+  - id: dep-loki", "+    description: Loki log store"],
        "removed": ["-  - id: dep-syslog"],
        "context": ["   title: Observability"]
      }
    ],
    "stats": {"additions": 2, "deletions": 1}
  },
  "code_diffs": [
    {
      "path": "svc/logging/config.py",
      "status": "modified",
      "extension": ".py",
      "language": null,
      "hunks": ["@@ -1,3 +1,6 @@", " import logging", "+LOKI_URL = 'http://loki:3100'"] ,
      "stats": {"additions": 2, "deletions": 0}
    }
  ],
  "metadata": {
    "dataset_version": "adl-diff-miner-schema-2025-01",
    "generated_at": "2025-11-12T08:04:05Z"
  }
}
```

## **5\. 핵심 로직 및 엣지 케이스 처리**

1. **커밋 순회:** 구현체는 `repo.walk(head_id, pygit2.GIT_SORT_TOPOLOGICAL)`로 전체 히스토리를 순회한 뒤, 각 커밋 diff에서 ADL 파일과 코드 확장자를 **사후 필터링**합니다. (향후 최적화로 `repo.iter_commits(paths=adl_file)` 같은 사전 필터링을 도입할 수 있습니다.)
2. **루트 커밋 (Root Commit):** target\_commit.parents가 비어있는 경우(루트 커밋), diff 대상이 없으므로 해당 커밋을 건너뛰고(skip) 정보 로그를 남깁니다.
3. **머지 커밋 (Merge Commits):** len(target\_commit.parents) \> 1인 경우, v1.0의 정책은 다음과 같습니다.
    * **'첫 번째 부모'**(target\_commit.parents\[0\])를 '직전 커밋'(parent\_commit)으로 간주하고 diff를 생성합니다. 이는 git pull이나 git merge의
      표준적인 동작을 모방합니다.
    * 이 커밋이 머지 커밋이었음을 식별할 수 있도록, 출력 스키마의 intent\_data에 is\_merge: true 플래그를 추가하는 것을 권장합니다 (v1.1). (v1.0에서는 경고 로그만 남겨도
      무방합니다.)
4. **Diff 생성 (Diff Generation):**
    * parent\_commit.diff(target\_commit, create\_patch=True)를 사용하여 텍스트 diff를 생성합니다.
    * code\_diffs는 \--code-exts 인자와 일치하는 파일들의 diff만 필터링하여 수집합니다.
    * adl\_diff는 \--adl-file 인자와 일치하는 파일의 diff만 수집합니다.
5. **빈 Diff 처리 (Empty Diffs):** code\_diffs와 adl\_diff가 모두 비어있는 경우(예: adl-file만 touch하고 내용은 변경되지 않은 경우), 해당 커밋은 훈련 데이터로
   저장하지 않습니다.
6. **인코딩 (Encoding):** get\_diff\_text 함수에서와 같이, diff\_obj.diff.decode('utf-8') 시 UnicodeDecodeError가 발생하면, 해당 diff는
   건너뛰고 경고 로그를 남깁니다.

## **6\. 향후 개선 사항 (v1.1+)**

* **병렬 처리:** 대형 저장소의 경우, 커밋 목록을 받아 multiprocessing을 사용해 diff 생성을 병렬화합니다.
* **데이터베이스 출력:** jsonl 외에 \--output-db "sqlite:///training.db"와 같이 DB에 직접 적재하는 옵션을 추가합니다.
* **PR/Issue 연동:** 커밋 메시지에서 (\#123) 같은 PR/Issue 번호를 파싱하여, intent\_data에 GitHub/GitLab API를 통해 가져온 PR/Issue의 본문(body)과
  토론(comments)을 추가합니다. (이는 2단계 마이닝을 위한 핵심 기능이 될 것입니다.)
