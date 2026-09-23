---
name: data_to_html
description: 여러 markdown(.md)/CSV(.csv/.tsv) 파일을 읽고 요약해 하나의 자기완결형 HTML로 만든다. CSV의 핵심 내용은 표로 담는다. 파일 하나만 그대로 변환하는 모드도 있다.
---

# data-to-html

markdown/CSV를 읽어 **의존성 없는 자기완결형 HTML**로 만든다.
결정론적이다 — 같은 입력이면 항상 같은 HTML이 나오고, 네트워크나 외부 패키지를 쓰지 않는다.
출력은 UTF-8(BOM 없음)이며, 스크립트가 파일에 직접 쓴다(PowerShell `Out-File`은 BOM을 붙여 한글이 깨지므로 쓰지 않는다).

## 두 가지 모드

| 모드 | 스크립트 | 입력 | 출력 |
|---|---|---|---|
| **요약(기본 용도)** | `scripts/summarize_to_html.py` | 여러 md·CSV(파일 여러 개 또는 디렉터리) | 요약 HTML **한 개**(목차 + md 요약 카드 + CSV 표) |
| 단일 변환 | `scripts/to_html.py` | md·CSV **하나** | 그 파일 하나를 그대로 변환한 HTML |

여러 파일을 읽어 요약본을 만드는 게 이 스킬의 주 용도다 — `summarize_to_html.py`를 쓴다.

## 요약 모드: `summarize_to_html.py`

- **markdown**: 제목(첫 `#`), 리드 문단(첫 문단), 섹션 제목 목록으로 **요약 카드**를 만든다. 본문 전체를 붙이지 않는다.
- **CSV**: 행/열 수와 전체 헤더를 보이고 **핵심 내용을 표로** 담는다. 기본은 앞 `--preview-rows`행(기본 10)만 발췌하고 몇 행이 생략됐는지 표시한다. `--full-csv`면 전체 행.
- 파일들은 목차(페이지 내부 앵커)로 묶인다. 모든 텍스트는 HTML 이스케이프(주입 방지).
- 유효한 입력이 하나도 없으면 HTML을 만들지 않고 종료 코드 1. 개별 파일 실패는 경고 후 건너뛴다.

```bash
cd scripts

# 디렉터리 두 개(documents + data)를 통째로 요약 -> HTML 한 개
python summarize_to_html.py \
  -i ../../../documents -i ../../../data \
  --title "E04 문서·데이터 요약" -o ../out/요약본.html

# 파일을 하나씩 지정 (-i 반복)
python summarize_to_html.py -i a.md -i b.md -i data.csv -o out.html

# CSV 전체 행을 표에 담기 / 미리보기 행 수 조정
python summarize_to_html.py -i ../../../data --full-csv -o out.html
python summarize_to_html.py -i ../../../data --preview-rows 20 -o out.html
```

### 요약 모드 옵션

- `-i/--input` (필수, 반복 가능): 파일 또는 디렉터리. 디렉터리면 안의 `.md/.csv/.tsv`를 이름순으로 수집
- `-o/--output`: 출력 HTML(UTF-8, BOM 없음). 없으면 stdout
- `--title`: 페이지 제목(기본 `문서·데이터 요약`)
- `--preview-rows N`: CSV 표에 담을 앞 행 수(기본 10)
- `--full-csv`: CSV 전체 행을 표에 담는다
- `--delimiter`: CSV 구분자 강제(`,` `;` 또는 탭은 `TAB`)

## 단일 변환 모드: `to_html.py`

파일 하나를 요약 없이 그대로 HTML로 바꾼다(md 전문 렌더 / CSV 전체 표).

## 입력 판별

| 확장자 | 처리 |
|---|---|
| `.md` / `.markdown` | markdown 부분집합을 HTML로 렌더 |
| `.csv` / `.tsv` | 헤더 1행 + 데이터를 `<table>`로 렌더 (구분자 자동 감지) |

확장자로 판별하며, `--kind md|csv`로 강제할 수 있다.

## 지원 범위

- **markdown**: 제목(`#`~`######`), 문단, 목록(`- * +`, `1.`), 코드블록(```` ``` ````), 인용(`>`), 수평선, GFM 표(`| a | b |`), 굵게 `**x**`, 기울임 `*x*`, 인라인코드 `` `x` ``, 링크 `[t](http…)`. (그 외 문법은 문단 텍스트로 처리)
- **CSV**: 첫 줄을 헤더로 보고 표를 만든다. 구분자는 `,` / 탭 / `;`를 자동 감지하며 `--delimiter`로 지정 가능. 행/열 수를 상단에 표시한다.
- 모든 텍스트는 HTML 이스케이프되어 삽입된다(주입 방지). markdown 링크는 `http/https`만 허용한다.

## 실행 절차

1. 입력 파일 종류를 확인한다(확장자 또는 `--kind`).
2. `scripts/to_html.py`로 변환한다. 오류(파일 없음·빈 CSV·판별 실패)면 HTML을 만들지 않고 종료 코드 1로 알린다.
3. 저장한 HTML을 **브라우저에서 열어 눈으로 확인**한 뒤 확정한다.

```bash
cd scripts

# markdown -> HTML (파일 저장)
python to_html.py -i ../../../documents/W04_04_행사안내.md -o ../out/행사안내.html

# CSV -> HTML (구분자 자동 감지)
python to_html.py -i ../../../data/참가신청.csv -o ../out/참가신청.html

# stdout으로 (파이프/미리보기)
python to_html.py -i input.md

# 종류·구분자·제목 지정
python to_html.py -i data.txt --kind csv --delimiter ";" --title "회계내역" -o out.html
python to_html.py -i data.tsv --delimiter TAB -o out.html
```

## 옵션

- `-i/--input` (필수): 입력 파일 경로
- `-o/--output`: 출력 HTML 경로(UTF-8, BOM 없음). 없으면 stdout
- `--kind md|csv`: 입력 종류 강제(확장자 무시)
- `--title`: 문서 제목(기본: 입력 파일명)
- `--delimiter`: CSV 구분자 강제(`,` `;` 또는 탭은 `TAB`)

Python 명령은 환경에 따라 `python` 또는 `py`를 쓴다(이 환경은 `python`, 3.12 확인).

> 주의: 이 스킬은 표시용 변환만 한다. 회계 집계·참가 인원 계산 같은 판단은 하지 않는다 —
> 그건 `club-budget-check` 등 집계 스킬의 몫이다.
