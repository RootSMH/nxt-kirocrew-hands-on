# -*- coding: utf-8 -*-
"""
빛담 가을사진전(E04) data CSV 3개 전체 집계.

근거 문서/조항:
- ACCOUNT-01 제1조: 기초잔액 학교지원금 0, 동아리회비 800,000. 거래 120건, E01~E04 혼재.
- ACCOUNT-01 제2조: 수입/환불입금 +, 지출/환불지급 -. 금액은 양의 정수 원.
- ACCOUNT-01 제3조: 재원별 현재잔액 = 기초 + 수입 + 환불입금 - 지출 - 환불지급.
                    E04 재원별 순지출 = 지출 + 환불지급 - 환불입금 (수입 제외).
- ACCOUNT-01 제5조: 구매계획 '참가자'=확정인원x계수, '고정'=계수 자체가 수량.
                    예정비용 = 단가 x 수량. (제4조: 회계에 합산하지 않음.)
- CLUB-01 제1조: 물품 구매 기본 인원 = 확정 인원.
- APPROVAL-SPACE-04 / RULE-02 제1조: 유효 정원 160명 (홍보 180명은 미승인).

원본은 읽기 전용. 결과 JSON만 저장.
"""
import csv, json, os, sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(BASE, "..", "data"))

APPLY_CSV   = os.path.join(DATA, "참가신청.csv")
LEDGER_CSV  = os.path.join(DATA, "회계내역.csv")
PLAN_CSV    = os.path.join(DATA, "구매계획.csv")

# ACCOUNT-01 제1조: 기초 잔액
OPENING = {"학교지원금": 0, "동아리회비": 800000}
# ACCOUNT-01 제2조: 부호
PLUS_TYPES  = {"수입", "환불입금"}
MINUS_TYPES = {"지출", "환불지급"}
EVENT = "E04"
CAPACITIES = [140, 160, 180]  # 140=현재 확정 추정, 160=승인정원, 180=홍보정원

confirm_needed = []  # 확인 필요 항목


def read_csv(path):
    # UTF-8 BOM 안전 처리
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


# ---------- 1) 참가신청 ----------
apply_rows = read_csv(APPLY_CSV)
apply_read = len(apply_rows)

status_counts = Counter()
e04_status = Counter()
for r in apply_rows:
    status_counts[r["신청상태"]] += 1
    if r["행사_ID"] == EVENT:
        e04_status[r["신청상태"]] += 1

# 확정자의 선택 (E04 확정자 기준)
confirmed_e04 = [r for r in apply_rows if r["행사_ID"] == EVENT and r["신청상태"] == "확정"]
n_confirmed = len(confirmed_e04)
inhwa = Counter(r["인화체험"] for r in confirmed_e04)
food  = Counter(r["식음료"] for r in confirmed_e04)

# ---------- 2) 회계내역 ----------
ledger_rows = read_csv(LEDGER_CSV)
ledger_read = len(ledger_rows)

types_seen = Counter(r["유형"] for r in ledger_rows)
unknown_types = set(types_seen) - PLUS_TYPES - MINUS_TYPES
if unknown_types:
    confirm_needed.append(
        f"회계 유형 중 부호 규정(ACCOUNT-01 제2조)에 없는 값: {sorted(unknown_types)} — 확인 필요"
    )

# 재원별 현재 잔액 (전체 동아리, E01~E04 포함)
balance = {src: OPENING.get(src, 0) for src in set(r["재원"] for r in ledger_rows)}
for src in OPENING:
    balance.setdefault(src, OPENING[src])
unknown_src = set(r["재원"] for r in ledger_rows) - set(OPENING)
if unknown_src:
    confirm_needed.append(f"기초잔액이 정의되지 않은 재원: {sorted(unknown_src)} — 기초 0 가정, 확인 필요")

for r in ledger_rows:
    amt = int(r["금액"])
    src = r["재원"]
    t = r["유형"]
    if t in PLUS_TYPES:
        balance[src] = balance.get(src, 0) + amt
    elif t in MINUS_TYPES:
        balance[src] = balance.get(src, 0) - amt
    # unknown 유형은 잔액에 미반영 (확인 필요로 이미 기록)

# E04 재원별 순지출 = 지출 + 환불지급 - 환불입금 (수입 제외)
e04_net = defaultdict(int)
e04_breakdown = defaultdict(lambda: {"지출": 0, "환불지급": 0, "환불입금": 0, "수입": 0})
for r in ledger_rows:
    if r["행사_ID"] != EVENT:
        continue
    amt = int(r["금액"]); src = r["재원"]; t = r["유형"]
    if t in e04_breakdown[src]:
        e04_breakdown[src][t] += amt
for src, b in e04_breakdown.items():
    e04_net[src] = b["지출"] + b["환불지급"] - b["환불입금"]

# ---------- 3) 구매계획 ----------
plan_rows = read_csv(PLAN_CSV)
plan_read = len(plan_rows)

def plan_cost(confirmed_n):
    """수량기준 '참가자'=확정인원x계수, '고정'=계수. 예정비용=단가x수량."""
    per_src = defaultdict(int)
    items = []
    total = 0
    for r in plan_rows:
        기준 = r["수량기준"]; 계수 = int(r["계수"]); 단가 = int(r["단가"]); src = r["예정재원"]
        if 기준 == "참가자":
            qty = confirmed_n * 계수
        elif 기준 == "고정":
            qty = 계수
        else:
            confirm_needed.append(f"구매계획 수량기준 미지값: {기준} (항목 {r['항목_ID']}) — 확인 필요")
            qty = None
        cost = 단가 * qty if qty is not None else None
        if cost is not None:
            per_src[src] += cost
            total += cost
        items.append({"항목_ID": r["항목_ID"], "물품": r["물품"], "수량기준": 기준,
                      "수량": qty, "단가": 단가, "예정재원": src, "예정비용": cost})
    return {"확정인원_가정": confirmed_n, "재원별_예정비용": dict(per_src),
            "총_예정비용": total, "항목": items}

plan_scenarios = {str(c): plan_cost(c) for c in CAPACITIES}

# ---------- 결과 ----------
result = {
    "생성일": "2026-09-23",
    "근거": {
        "회계": "ACCOUNT-01 제1~5조",
        "참가확정_기본인원": "CLUB-01 제1조 (확정 인원)",
        "유효정원": "APPROVAL-SPACE-04 승인정원 160 / RULE-02 제1조 (홍보 180 미승인)",
    },
    "읽은_행수": {"참가신청": apply_read, "회계내역": ledger_read, "구매계획": plan_read},
    "참가신청": {
        "전체_상태별": dict(status_counts),
        "E04_상태별": dict(e04_status),
        "E04_확정_인원": n_confirmed,
        "E04_확정자_인화체험": dict(inhwa),
        "E04_확정자_식음료": dict(food),
    },
    "회계": {
        "유형_분포": dict(types_seen),
        "기초잔액(ACCOUNT-01 제1조)": OPENING,
        "재원별_현재잔액(제3조)": balance,
        "E04_재원별_상세": {k: dict(v) for k, v in e04_breakdown.items()},
        "E04_재원별_순지출(제3조: 지출+환불지급-환불입금, 수입제외)": dict(e04_net),
    },
    "구매계획": {
        "설명": "ACCOUNT-01 제5조 산식. 제4조에 따라 회계 잔액/지급비용에 합산하지 않음.",
        "정원별_시나리오": plan_scenarios,
    },
    "확인_필요": confirm_needed,
}

OUT = os.path.join(BASE, "집계결과.json")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 콘솔 요약
print(f"[읽은 행수] 참가신청={apply_read}, 회계내역={ledger_read}, 구매계획={plan_read}")
print(f"[참가 전체 상태별] {dict(status_counts)}")
print(f"[E04 상태별] {dict(e04_status)}")
print(f"[E04 확정 인원] {n_confirmed}")
print(f"[E04 확정자 인화체험] {dict(inhwa)}")
print(f"[E04 확정자 식음료] {dict(food)}")
print(f"[회계 유형 분포] {dict(types_seen)}")
print(f"[재원별 현재잔액] {balance}")
print(f"[E04 재원별 순지출] {dict(e04_net)}")
for c in CAPACITIES:
    s = plan_scenarios[str(c)]
    print(f"[구매계획 {c}명] 재원별={s['재원별_예정비용']} 총={s['총_예정비용']}")
print(f"[확인 필요] {confirm_needed if confirm_needed else '없음'}")
print(f"[저장] {OUT}")
