"""week06 미션 공용 장비 대여 오전 점검.
실행할 때마다 운영메모·대여현황·요청을 새로 읽고 submissions/mission/점검결과.md를 갱신한다.
변경사항.md는 읽지 않는다. 입력 파일은 수정하지 않는다.

실행(week06 폴더에서): python submissions/mission/check_rental.py
"""

import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9), 'Asia/Seoul')
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'practice' / 'mission'
OUT = Path(__file__).resolve().parent / '점검결과.md'
FMT = '%Y-%m-%d %H:%M'


def ts(value):
    return datetime.strptime(value, FMT).replace(tzinfo=KST) if value else None


def main():
    now = datetime.now(KST)
    memo = (SRC / '운영메모.md').read_text(encoding='utf-8')
    base = ts(re.search(r'업무 기준일시: \*\*(\d{4}-\d\d-\d\d \d\d:\d\d)', memo)[1])
    with (SRC / '대여현황.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    by_id = {r['대여ID']: r for r in rows}
    requests = re.findall(
        r'^## (Q\d+) · (.+?)\n.*?관련 대여ID: (\S+).*?요청자: (\S+).*?희망 반납일시: ([\d-]+ [\d:]+)'
        r'.*?요청 내용: (.+?)$',
        (SRC / '담당자에게_온_요청.md').read_text(encoding='utf-8'), re.M | re.S)

    active = [r for r in rows if r['상태'] == '대여중']
    overdue = [r for r in active if ts(r['반납예정일시']) < base]
    due_today = [r for r in active if ts(r['반납예정일시']) >= base
                 and ts(r['반납예정일시']).date() == base.date()]
    returned = [r for r in rows if r['상태'] == '반납완료']

    def nxt(r):
        return f"{r['다음예약자']} {r['다음예약시작']}~{r['다음예약종료']}" if r['다음예약시작'] else '없음'

    L = ['# 공용 장비 대여 오전 점검', '',
         f'- 업무 기준일시: {base:%Y-%m-%d %H:%M} (Asia/Seoul)',
         f'- 보고서 작성 시각: {now:%Y-%m-%d %H:%M} (Asia/Seoul)', '',
         f'## 1. 현재 대여 중 ({len(active)}건)', '',
         '| 대여ID | 장비명 | 대여자 | 반납예정일시 | 다음 예약 |', '|---|---|---|---|---|']
    L += [f"| {r['대여ID']} | {r['장비명']} | {r['대여자']} | {r['반납예정일시']} | {nxt(r)} |" for r in active]
    L += ['', f'## 2. 연체 ({len(overdue)}건)', '']
    L += ([f"- {r['대여ID']} {r['장비명']} · {r['대여자']} · 반납예정 {r['반납예정일시']} · 다음 예약 {nxt(r)}"
           for r in overdue] or ['- 없음'])
    L += ['', f'## 3. 오늘(10월 7일) 반납 예정 ({len(due_today)}건)', '']
    L += ([f"- {r['대여ID']} {r['장비명']} · {r['대여자']} · 반납예정 {r['반납예정일시']} · 다음 예약 {nxt(r)}"
           for r in due_today] or ['- 없음'])
    L += ['', f'## 4. 반납 완료 기록 ({len(returned)}건, 위 목록에서 제외)', '']
    L += [f"- {r['대여ID']} {r['장비명']} · {r['대여자']} · 실제반납 {r['실제반납일시']}" for r in returned]

    L += ['', '## 5. 처리할 요청', '']
    for qid, title, lid, who, wish, body in requests:
        r = by_id.get(lid)
        if r is None:
            L.append(f'- {qid} {title}: 관련 대여ID {lid}를 현황에서 찾을 수 없음 · 확인 필요')
            continue
        start = ts(r['다음예약시작'])
        if r['상태'] != '대여중':
            conflict = f"현재 상태 {r['상태']} · 연장 필요 여부 확인"
        elif start and ts(wish) > start:
            conflict = f"예약 충돌 (다음 예약 {nxt(r)} 시작보다 늦음)"
        elif start:
            conflict = f'충돌 없음 (다음 예약 {nxt(r)})'
        else:
            conflict = '충돌 없음 (확정된 다음 예약 없음)'
        L += [f'### {qid} · {title}', '',
              f"- 관련 대여ID: {lid} ({r['장비명']}, 대여자 {who}, 상태 {r['상태']})",
              f"- 현재 반납예정일시: {r['반납예정일시']} → 희망 반납일시: {wish}",
              f'- 사유: {body.strip()}',
              f'- 다음 예약과의 관계: {conflict}',
              '- 처리: 담당자 판단 필요. 승인 확정 전에는 반납예정일시를 바꾸지 않음.', '']

    L += ['## 6. 요약', '',
          '확인한 사실',
          f'- 현재 대여 중 {len(active)}건, 연체 {len(overdue)}건'
          f"({', '.join(r['대여ID'] for r in overdue) or '없음'}), "
          f"오늘 반납 예정 {len(due_today)}건({', '.join(r['대여ID'] for r in due_today) or '없음'})", '',
          '후속 처리 필요']
    L += [f"- {r['대여ID']} 연체: 대여자 {r['대여자']}에게 반납 요청 연락 처리안 마련"
          + (f" (다음 예약 {nxt(r)} 전 회수 필요)" if r['다음예약시작'] else '') for r in overdue]
    L += [f'- {qid} 연장 요청 회신 (담당자 승인 여부 결정 필요)' for qid, *_ in requests]
    OUT.write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
