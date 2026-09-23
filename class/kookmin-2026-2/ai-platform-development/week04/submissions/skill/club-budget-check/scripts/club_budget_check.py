# -*- coding: utf-8 -*-
"""
club-budget-check: 동아리 행사 회계·참가·구매계획 집계 (결정론적).

세 CSV를 읽어 참가 상태별 인원, 확정자 선택, 재원별 현재 잔액,
행사 순지출, 정원별 구매계획 예정비용을 집계한다.
회계 기준(부호·기초잔액·행사범위·구매산식)은 문서 조항을 그대로 적용한다.

원본 CSV는 읽기 전용. 결과 JSON만 -o 경로에 BOM 없는 UTF-8로 저장한다.
(PowerShell Out-File은 BOM을 붙여 한글이 깨지므로 스크립트가 직접 쓴다.)

미지의 값(부호 규정에 없는 유형, 기초잔액 미정의 재원, 미지 수량기준)은
임의로 처리하지 않고 '확인_필요'에 남긴다.

종료 코드:
  0  정상
  1  입력 오류(파일 없음·필수 컬럼 누락·빈 CSV)
  2  --expect 크로스체크 불일치
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

# 회계 기준(ACCOUNT-01) 기본값 — CLI로 덮어쓸 수 있다.
DEFAULT_OPENING = {"학교지원금": 0, "동아리회비": 800000}  # 제1조
PLUS_TYPES = {"수입", "환불입금"}      # 제2조: 잔액에 더함
MINUS_TYPES = {"지출", "환불지급"}     # 제2조: 잔액에서 뺌

APPLY_COLS = {"신청_ID", "행사_ID", "신청상태"}
LEDGER_COLS = {"거래_ID", "행사_ID", "재원", "유형", "금액"}
PLAN_COLS = {"항목_ID", "물품", "수량기준", "계수", "단가", "예정재원"}


def die(msg, code=1):
    print(f"[오류] {msg}", file=sys.stderr)
    sys.exit(code)


def read_csv(path, required_cols):
    if not os.path.isfile(path):
        die(f"파일 없음: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = set(reader.fieldnames or [])
    if not rows:
        die(f"빈 CSV: {path}")
    missing = required_cols - headers
    if missing:
        die(f"필수 컬럼 누락 {sorted(missing)}: {path}")
    return rows


def to_int(v, ctx):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        die(f"정수가 아닌 값 '{v}' ({ctx})")


def aggregate(apply_path, ledger_path, plan_path, event, capacities,
              opening, choice_cols):
    confirm_needed = []

    # 1) 참가신청
    apply_rows = read_csv(apply_path, APPLY_COLS)
    ids = [r["신청_ID"] for r in apply_rows]
    dup = [k for k, c in Counter(ids).items() if c > 1]
    if dup:
        die(f"신청_ID 중복: {dup}")

    status_all = Counter(r["신청상태"] for r in apply_rows)
    ev_rows = [r for r in apply_rows if r["행사_ID"] == event]
    status_event = Counter(r["신청상태"] for r in ev_rows)
    confirmed = [r for r in ev_rows if r["신청상태"] == "확정"]
    n_confirmed = len(confirmed)

    # 확정자 선택 열: 지정된 열(기본 자동감지: 신청_ID/행사_ID/이름/신청상태/신청일 제외)
    reserved = {"신청_ID", "행사_ID", "이름", "신청상태", "신청일"}
    if choice_cols:
        cols = choice_cols
    else:
        cols = [c for c in (apply_rows[0].keys()) if c not in reserved]
    choices = {c: dict(Counter(r.get(c, "") for r in confirmed)) for c in cols}

    # 2) 회계내역
    ledger_rows = read_csv(ledger_path, LEDGER_COLS)
    types_seen = Counter(r["유형"] for r in ledger_rows)
    unknown_types = set(types_seen) - PLUS_TYPES - MINUS_TYPES
    if unknown_types:
        confirm_needed.append(
            f"부호 규정(제2조)에 없는 회계 유형 {sorted(unknown_types)} — 잔액 미반영, 확인 필요")

    srcs = set(r["재원"] for r in ledger_rows)
    balance = {s: opening.get(s, 0) for s in srcs}
    for s in opening:
        balance.setdefault(s, opening[s])
    unknown_src = srcs - set(opening)
    if unknown_src:
        confirm_needed.append(
            f"기초잔액 미정의 재원 {sorted(unknown_src)} — 기초 0 가정, 확인 필요")

    for r in ledger_rows:
        amt = to_int(r["금액"], f"거래 {r['거래_ID']} 금액")
        if amt < 0:
            confirm_needed.append(f"음수 금액 거래 {r['거래_ID']}={amt} — 제2조상 금액은 양의 정수, 확인 필요")
        s, t = r["재원"], r["유형"]
        if t in PLUS_TYPES:
            balance[s] = balance.get(s, 0) + amt
        elif t in MINUS_TYPES:
            balance[s] = balance.get(s, 0) - amt

    # 행사 순지출 = 지출 + 환불지급 - 환불입금 (수입 제외, 제3조)
    ev_break = defaultdict(lambda: {"지출": 0, "환불지급": 0, "환불입금": 0, "수입": 0})
    for r in ledger_rows:
        if r["행사_ID"] != event:
            continue
        amt = to_int(r["금액"], f"거래 {r['거래_ID']} 금액")
        s, t = r["재원"], r["유형"]
        if t in ev_break[s]:
            ev_break[s][t] += amt
    ev_net = {s: b["지출"] + b["환불지급"] - b["환불입금"] for s, b in ev_break.items()}

    # 3) 구매계획: '참가자'=확정인원x계수, '고정'=계수. 예정비용=단가x수량. (제5조)
    plan_rows = read_csv(plan_path, PLAN_COLS)

    def plan_cost(n):
        per_src = defaultdict(int)
        items = []
        total = 0
        for r in plan_rows:
            기준, src = r["수량기준"], r["예정재원"]
            계수 = to_int(r["계수"], f"항목 {r['항목_ID']} 계수")
            단가 = to_int(r["단가"], f"항목 {r['항목_ID']} 단가")
            if 기준 == "참가자":
                qty = n * 계수
            elif 기준 == "고정":
                qty = 계수
            else:
                confirm_needed.append(f"미지 수량기준 '{기준}' (항목 {r['항목_ID']}) — 확인 필요")
                qty = None
            cost = 단가 * qty if qty is not None else None
            if cost is not None:
                per_src[src] += cost
                total += cost
            items.append({"항목_ID": r["항목_ID"], "물품": r["물품"], "수량기준": 기준,
                          "수량": qty, "단가": 단가, "예정재원": src, "예정비용": cost})
        return {"인원_가정": n, "재원별_예정비용": dict(per_src),
                "총_예정비용": total, "항목": items}

    plan = {str(n): plan_cost(n) for n in capacities}

    return {
        "행사": event,
        "읽은_행수": {"참가신청": len(apply_rows), "회계내역": len(ledger_rows),
                    "구매계획": len(plan_rows)},
        "참가": {
            "전체_상태별": dict(status_all),
            f"{event}_상태별": dict(status_event),
            f"{event}_확정_인원": n_confirmed,
            f"{event}_확정자_선택": choices,
        },
        "회계": {
            "유형_분포": dict(types_seen),
            "기초잔액": opening,
            "재원별_현재잔액": balance,
            f"{event}_재원별_상세": {s: dict(b) for s, b in ev_break.items()},
            f"{event}_재원별_순지출": ev_net,
        },
        "구매계획": {"설명": "제5조 산식. 제4조에 따라 회계 잔액/지급비용에 미합산(예정치).",
                  "정원별_시나리오": plan},
        "확인_필요": confirm_needed,
    }


def main():
    p = argparse.ArgumentParser(description="동아리 행사 회계·참가·구매 집계")
    p.add_argument("--apply", required=True, help="참가신청 CSV")
    p.add_argument("--ledger", required=True, help="회계내역 CSV")
    p.add_argument("--plan", required=True, help="구매계획 CSV")
    p.add_argument("--event", required=True, help="집계 대상 행사_ID (예: E04)")
    p.add_argument("--capacities", default="", help="구매 시나리오 인원, 쉼표구분 (예: 140,160,180). 비우면 확정인원 하나만")
    p.add_argument("--opening", default="", help="기초잔액 재정의 '재원=금액' 쉼표구분 (예: 학교지원금=0,동아리회비=800000)")
    p.add_argument("--choice-cols", default="", help="확정자 선택 집계 열, 쉼표구분. 비우면 자동감지")
    p.add_argument("-o", "--output", help="결과 JSON 저장 경로 (BOM 없는 UTF-8). 없으면 stdout")
    p.add_argument("--expect", default="", help="크로스체크: 'JSONPath식' 대신 간단히 '확정인원=140' 형태 쉼표구분")
    args = p.parse_args()

    opening = dict(DEFAULT_OPENING)
    if args.opening:
        for pair in args.opening.split(","):
            k, _, v = pair.partition("=")
            opening[k.strip()] = int(v.strip())

    caps = [int(x) for x in args.capacities.split(",") if x.strip()] if args.capacities else None
    choice_cols = [c.strip() for c in args.choice_cols.split(",") if c.strip()] or None

    # capacities 미지정이면 확정인원 하나만 — 먼저 확정인원을 구해야 하므로 임시 집계 후 결정
    result = aggregate(args.apply, args.ledger, args.plan, args.event,
                       caps if caps else [0], opening, choice_cols)
    if not caps:
        n = result["참가"][f"{args.event}_확정_인원"]
        result = aggregate(args.apply, args.ledger, args.plan, args.event,
                           [n], opening, choice_cols)

    # --expect 크로스체크
    if args.expect:
        mismatches = []
        for pair in args.expect.split(","):
            k, _, v = pair.partition("=")
            k, v = k.strip(), v.strip()
            if k == "확정인원":
                actual = result["참가"][f"{args.event}_확정_인원"]
                if str(actual) != v:
                    mismatches.append(f"확정인원: 기대 {v} ≠ 실제 {actual}")
            else:
                mismatches.append(f"미지 기대키 '{k}' — 확인 필요")
        if mismatches:
            print("[크로스체크 불일치] " + "; ".join(mismatches), file=sys.stderr)
            sys.exit(2)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"[저장] {args.output}")
    else:
        print(text)

    r = result
    ev = args.event
    print(f"[읽은 행수] {r['읽은_행수']}", file=sys.stderr)
    print(f"[{ev} 확정 인원] {r['참가'][f'{ev}_확정_인원']}", file=sys.stderr)
    print(f"[재원별 현재잔액] {r['회계']['재원별_현재잔액']}", file=sys.stderr)
    print(f"[{ev} 순지출] {r['회계'][f'{ev}_재원별_순지출']}", file=sys.stderr)
    print(f"[확인 필요] {r['확인_필요'] or '없음'}", file=sys.stderr)


if __name__ == "__main__":
    main()
