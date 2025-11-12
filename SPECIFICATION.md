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
\--adl-file "\[*.]adl.yaml" \\  
\--code-exts .py .yaml .json \\  
\--output "training\_dataset.jsonl"

* \--repo (필수): 분석할 로컬 Git 저장소의 경로.
* \--adl-file (필수): 저장소 내에서 추적할 ADL 파일의 상대 경로.
* \--code-exts (선택, 기본값: .py): ADL 변경과 연관시킬 소스 코드 파일의 확장자 목록 (공백으로 구분).
* \--output (선택, 기본값: stdout): 결과를 저장할 출력 파일 경로. 지정하지 않으면 표준 출력(stdout)으로 jsonl 데이터를 스트리밍합니다.

## **4\. 출력 데이터 스키마 (JSONL)**

도구는 \--output으로 지정된 파일 또는 stdout에 **Line-Delimited JSON (.jsonl)** 형식으로 훈련 데이터를 출력해야 합니다. 각 라인은 다음 스키마를 따르는 하나의 JSON
객체입니다.

이 스키마는 프로토타입의 DiffDataPair 튜플을 확장하여, 추적 및 분석에 필요한 메타데이터를 포함합니다.

{  
"target\_commit\_hash": "a1b2c3d4...",  
"parent\_commit\_hash": "e5f6g7h8...",  
"intent\_data": {  
"message": "ADL: Add Loki logging stack (V-3.1)\\n\\n- Adds dep-promtail and dep-loki to V-3.1\\n- Links to ADR-3
rationale.",  
"author\_name": "KMilhan",  
"author\_email": "milhan@example.com",  
"timestamp\_utc": "2025-11-12T08:30:00Z"  
},  
"code\_diffs": \[  
{  
"file\_path": "spam\_bootstrapper/logging/config.py",  
"diff\_text": "--- a/spam\_bootstrapper/logging/config.py\\n+++ b/spam\_bootstrapper/logging/config.py\\n@@ \-1,5 \+1,8
@@\\n import logging\\n
\\n+LOKI\_URL \= '\[http://loki.default.svc.cluster.local:3100\](http://loki.default.svc.cluster.local:3100)'\\n+\\n def
get\_logger():\\n \# ... (code changes) ..."  
},  
{  
"file\_path": "spam\_bootstrapper/deploy/k8s/loki.yaml",  
"diff\_text": "--- /dev/null\\n+++ b/spam\_bootstrapper/deploy/k8s/loki.yaml\\n@@ \-0,0 \+1,50 @@\\n+apiVersion:
v1\\n+kind: StatefulSet\\n+metadata:\\n+ name: loki\\n\# ... (new file content) ..."  
}  
\],  
"adl\_diff": {  
"file\_path": "spam-filter-adl.yaml",  
"diff\_text": "--- a/spam-filter-adl.yaml\\n+++ b/spam-filter-adl.yaml\\n@@ \-215,6 \+215,18 @@\\n name: \\"Model
registry\\"\\n description: \\"Storage server managing model's status and artifact\\"\\n+ \- id: dep-promtail\\n+
name: \\"Promtail DaemonSet\\"\\n+ description: \\"DaemonSet shipping spam-filter pod logs with redaction filters\\"
\\n+ \- id: dep-loki\\n+ name: \\"Loki StatefulSet\\"\\n+ description: \\"Single-replica Loki storing structured logs \+
exposing query API\\"\\n+ \- id: dep-grafana-loki\\n+ name: \\"Grafana Loki Datasource\\"\\n+ description: \\"Grafana
datasource pointing at Loki for SRE dashboards\\"\\n connections:\\n \- source: dep-api-gateway\\n target:
dep-inference-service\\n@@ \-223,6 \+235,15 @@\\n \- source: dep-inference-service\\n target: dep-model-registry\\n
purpose: \\"Query the latest stable version of model\\"\\n+ \- source: dep-inference-service\\n+ target:
dep-promtail\\n+ purpose: \\"Pods emit structured JSON logs scraped by Promtail\\"\\n+ \- source: dep-promtail\\n+
target: dep-loki\\n+ purpose: \\"Promtail pushes logs with request/trace IDs to Loki\\"\\n+ \- source: dep-loki\\n+
target: dep-grafana-loki\\n+ purpose: \\"Grafana queries Loki for troubleshooting and SLO dashboards\\""  
}  
}

## **5\. 핵심 로직 및 엣지 케이스 처리**

1. **커밋 순회:** 프로토타입과 동일하게 repo.iter\_commits(paths=adl\_file)를 사용하여 adl-file을 변경한 커밋(target\_commit)만 효율적으로 순회합니다.
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
