# Week 03 · 내 일을 맡기고, 반복은 스킬로

[시작하기.html](시작하기.html)을 브라우저로 열어 진행합니다. 자료를 읽고 첫 결과를 확인한 뒤, 발표 준비 점검 스킬을 사용하고 자신이 정한 청중을 위한 설명 스킬을 만듭니다.

## 오늘 할 일

1. 자료를 읽고 내 판단을 세운 뒤 Kiro Crew에 첫 업무 맡기기
2. 내 조건을 반영하고 결과를 원문과 대조하기
3. 발표 준비 점검 스킬을 연결해 계산 결과 확인하기
4. 청중 맞춤 설명 스킬을 만들고 두 결과 비교하기
5. 추가 자료를 받아 새 세션에서 재사용하고 내 포크에 기록하기

## 자료 위치

아직 Week03를 받지 않았다면 Clone한 수업 저장소의 터미널에서 `git status`와 `git remote -v`를 확인합니다. 수정한 파일은 본인 작업만 먼저 커밋합니다. 아래 명령을 한 줄씩 실행하고 결과를 확인합니다.

```bash
git config --local pull.rebase false
git pull --no-edit upstream main
```

첫 줄은 이 저장소에서 처음 한 번 설정합니다. `--no-edit`는 기본 병합 메시지를 사용해 편집창을 생략합니다. Pull이 완료되면 `git push origin main`으로 자신의 포크에 반영한 뒤 `시작하기.html`을 엽니다. 충돌이나 오류가 보이면 기존 작업을 지우지 말고 강사와 확인합니다.

| 위치 | 내용 |
|---|---|
| [시작하기.html](시작하기.html) | 단계별 안내, 자료 읽기, 수정할 조건, 요청문 복사와 확인 항목 |
| [data/](data/README.md) | 발표 안내, 조사·준비 메모, 작업과 가용시간 |
| [skill-kit/prep-check/](skill-kit/prep-check/SKILL.md) | 공통 발표 준비 점검 스킬 |
| [skill-kit/audience-brief/](skill-kit/audience-brief/스킬작성가이드.md) | 청중 맞춤 설명 스킬을 만들 때 사용할 안내와 제작 코드 |
| [submissions/나의기준.md](submissions/나의기준.md) | 내 목적, 조건, 판단 기준 |
| [submissions/실습기록.md](submissions/실습기록.md) | 실행 결과, 원문 대조, 개선 내용과 최종 커밋 링크 |

Kiro Crew의 세션 프로젝트에는 이미 Clone한 `nxt-kirocrew-hands-on` 저장소의 최상위 폴더를 연결합니다. 공통 원자료는 `data/`에서 읽고, 개인 조건을 반영한 메모·CSV와 결과물은 `submissions/`에 저장합니다. 직접 만드는 스킬의 `SKILL.md`는 `skill-kit/audience-brief/`에 남깁니다.

스킬의 Python 코드는 입력 파일을 직접 읽어 계산하거나 검토된 원고를 HTML로 조립합니다. 코드가 정상 실행되었다는 사실과 설명의 근거가 맞다는 판단을 구분하고, 만들어진 파일을 실제로 열어 확인합니다.

Python 3.10 이상이 필요합니다. Kiro Crew 앱 설치와 터미널 Python 준비는 별개입니다. Mac은 `python3 --version`, Windows는 `py -3 --version` 또는 `python --version`으로 확인합니다. 명령이 없거나 버전이 낮으면 [시작하기의 Python 준비 안내](시작하기.html#python-ready)에 따라 공식 설치 프로그램으로 준비한 뒤 다시 확인합니다. 추가 Python 패키지는 필요 없습니다.

자료의 성격과 공개 출처는 `시작하기.html` 하단에 안내합니다.
