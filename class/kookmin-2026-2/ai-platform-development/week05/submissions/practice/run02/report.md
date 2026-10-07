# 재고 요약 보고서 (2차 · 품목별 총수량 기준)

입력: warehouse-a.md, warehouse-b.md, warehouse-c.md

## 창고별 합계

| 창고 | 합계 |
|---|---:|
| A | 22 |
| B | 16 |
| C | 16 |

## 품목별 총수량

| 품목 | 총수량 |
|---|---:|
| mug | 17 |
| bottle | 12 |
| sensor | 11 |
| hub | 13 |
| cable | 1 |

전체 수량: 54

## 저재고

기준: 전체 창고의 품목별 총수량이 5 미만 (low_stock_basis = item_total)

| 품목 | 총수량 |
|---|---:|
| cable | 1 |
