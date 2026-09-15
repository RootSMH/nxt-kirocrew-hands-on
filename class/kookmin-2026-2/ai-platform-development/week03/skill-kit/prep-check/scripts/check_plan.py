#!/usr/bin/env python3
"""준비 작업의 예상 소요시간과 마감 전 가용시간을 비교한다. Python 3.10+."""

import argparse
import csv
import html
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


class InputError(ValueError):
    """입력 자료의 형식이나 값이 계산 계약에 맞지 않는다."""


def parse_datetime(value, label):
    """시차가 있는 ISO 시각만 사용해 컴퓨터의 시간대에 따른 차이를 없앤다."""
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise InputError(f"{label}: ISO 시각이 필요합니다. 예: 2026-09-16T18:00+09:00") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise InputError(f"{label}: +09:00 같은 시간대 정보가 필요합니다.")
    return result


def read_rows(path, fields):
    """열 이름을 검사하고 UTF-8 BOM이 있는 CSV도 읽는다."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != set(fields):
            raise InputError(f"{Path(path).name}: 열은 {', '.join(fields)}여야 합니다.")
        if len(reader.fieldnames) != len(fields):
            raise InputError(f"{Path(path).name}: 열 이름이 중복되었습니다.")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise InputError(f"{Path(path).name} {reader.line_num}행: 열 수가 맞지 않습니다.")
            rows.append({key: value.strip() for key, value in row.items()})
        return rows


def number(value):
    """정확히 정수인 분은 정수로 표시하고, 나머지는 소수로 유지한다."""
    return int(value) if value == int(value) else float(value)


def duration_minutes(start, end):
    delta = end - start
    microseconds = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    return Decimal(microseconds) / Decimal(60000000)


def calculate(tasks_path, availability_path, as_of, deadline):
    start = parse_datetime(as_of, "기준 시각")
    finish = parse_datetime(deadline, "마감 시각")
    if finish <= start:
        raise InputError("마감 시각은 기준 시각보다 뒤여야 합니다.")

    tasks = read_rows(tasks_path, ("task_id", "task", "remaining_minutes", "status"))
    if not tasks:
        raise InputError("준비 작업이 한 개 이상 필요합니다.")
    seen = set()
    remaining = Decimal(0)
    for row in tasks:
        task_id = row["task_id"]
        if not task_id or not row["task"]:
            raise InputError("task_id와 task는 비어 있을 수 없습니다.")
        if task_id in seen:
            raise InputError(f"task_id가 중복되었습니다: {task_id}")
        seen.add(task_id)
        if row["status"] not in {"todo", "in_progress", "done"}:
            raise InputError(f"{task_id}: status는 todo, in_progress, done 중 하나입니다.")
        try:
            minutes = Decimal(row["remaining_minutes"])
        except InvalidOperation as exc:
            raise InputError(f"{task_id}: remaining_minutes는 숫자여야 합니다.") from exc
        if not minutes.is_finite() or minutes < 0:
            raise InputError(f"{task_id}: remaining_minutes는 유한한 0 이상의 숫자여야 합니다.")
        if row["status"] == "done" and minutes != 0:
            raise InputError(f"{task_id}: done 작업의 remaining_minutes는 0이어야 합니다.")
        remaining += minutes
        row["remaining_minutes"] = number(minutes)

    availability = read_rows(availability_path, ("start", "end", "label"))
    windows = []
    for index, row in enumerate(availability, 2):
        left = parse_datetime(row["start"], f"가용시간 {index}행 start")
        right = parse_datetime(row["end"], f"가용시간 {index}행 end")
        if right <= left:
            raise InputError(f"가용시간 {index}행: end는 start보다 뒤여야 합니다.")
        if not row["label"]:
            raise InputError(f"가용시간 {index}행: label은 비어 있을 수 없습니다.")
        # 기준 시각 이전과 마감 이후의 시간은 사용할 수 없다.
        clipped_start, clipped_end = max(left, start), min(right, finish)
        usable = clipped_start < clipped_end
        row["effective_start"] = clipped_start.isoformat() if usable else None
        row["effective_end"] = clipped_end.isoformat() if usable else None
        if usable:
            windows.append((clipped_start, clipped_end))

    # 겹치거나 맞닿은 구간을 합친다. 같은 시간을 두 번 세지 않는다.
    merged = []
    for left, right in sorted(windows):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    available = sum((duration_minutes(left, right) for left, right in merged), Decimal(0))
    return {
        "source_paths": {
            "tasks": str(Path(tasks_path).resolve()),
            "availability": str(Path(availability_path).resolve()),
        },
        "as_of": start.isoformat(),
        "deadline": finish.isoformat(),
        "assumptions": [
            "작업시간은 입력 자료에 적힌 예상값이며 실제 완료를 보장하지 않습니다.",
            "가용시간은 기준 시각부터 마감 시각까지 잘라낸 뒤 겹친 구간을 한 번만 계산합니다.",
            "시간의 총량을 비교합니다. 작업 순서·의존 관계·집중 가능 여부는 별도로 판단해야 합니다.",
        ],
        "summary": {
            "total_remaining_minutes": number(remaining),
            "available_minutes": number(available),
            "shortage_minutes": number(max(remaining - available, Decimal(0))),
            "remaining_capacity_minutes": number(max(available - remaining, Decimal(0))),
        },
        "tasks": tasks,
        "availability": availability,
        "merged_windows": [
            {"start": left.isoformat(), "end": right.isoformat(),
             "minutes": number(duration_minutes(left, right))}
            for left, right in merged
        ],
    }


def render_html(report):
    """JSON과 같은 계산 결과를 표시한다. 여기에서 다시 계산하지 않는다."""
    escape = lambda value: html.escape(str(value), quote=True)
    summary = report["summary"]
    # 표시는 기준 시각의 시간대로 통일한다. JSON의 원래 시각·경로는 그대로 둔다.
    display_zone = parse_datetime(report["as_of"], "기준 시각").tzinfo

    def local_time(value):
        return parse_datetime(value, "표시 시각").astimezone(display_zone)

    def date_label(value):
        weekday = "월화수목금토일"[value.weekday()]
        return f"{value.year}년 {value.month}월 {value.day}일 ({weekday})"

    def time_label(value):
        if value.second or value.microsecond:
            return value.time().isoformat()
        return f"{value.hour:02d}:{value.minute:02d}"

    def stamp(value):
        value = local_time(value)
        return f"{date_label(value)} {time_label(value)}"

    offset = local_time(report["as_of"]).strftime("%z")
    zone_label = f"UTC{offset[:3]}:{offset[3:5]}"
    if len(offset) > 5:
        zone_label += f":{offset[5:]}"
    if offset == "+0900":
        zone_label = f"한국 표준시 ({zone_label})"

    # 부족 0분을 '안심해도 된다'로 해석하지 않도록 여유를 따로 보여 준다.
    if summary["total_remaining_minutes"] == 0:
        tone, headline = "neutral", "등록된 작업의 남은 예상 시간은 0분입니다."
        guidance = "작업별 상태와 실제 완료 여부를 확인하세요."
    elif summary["shortage_minutes"] > 0:
        tone, headline = "shortage", f"예상 작업시간이 {summary['shortage_minutes']}분 부족합니다."
        guidance = "현재 등록된 시간만으로는 예상 작업량을 채울 수 없습니다. 작업 범위나 확보할 시간을 조정하세요."
    elif summary["remaining_capacity_minutes"] == 0:
        tone, headline = "tight", "여유 없음 · 예상 작업시간과 가능한 시간이 같습니다."
        guidance = "한 작업이라도 예상보다 길어지면 시간이 부족해집니다. 추가 작업이나 수정에 쓸 시간을 확보하세요."
    else:
        tone, headline = "neutral", f"계산상 {summary['remaining_capacity_minutes']}분의 여유가 있습니다."
        guidance = "입력한 예상시간을 기준으로 한 결과입니다. 수정과 재확인에 필요한 시간도 생각하세요."
    cards = "".join(
        f"<div><span>{title}</span><strong>{escape(summary[key])}분</strong></div>"
        for title, key in [("남은 작업 예상", "total_remaining_minutes"),
                           ("사용 가능한 시간", "available_minutes"),
                           ("부족한 시간", "shortage_minutes"),
                           ("남는 시간", "remaining_capacity_minutes")]
    )
    status_labels = {"done": "완료", "in_progress": "진행 중", "todo": "할 일"}
    rows = "".join(
        f"<tr><td class=task-id>{escape(row['task_id'])}</td>"
        f"<td class=task>{escape(row['task'])}</td>"
        f"<td class=minutes>{escape(row['remaining_minutes'])}분</td>"
        f"<td class=status>{escape(status_labels[row['status']])}</td></tr>"
        for row in report["tasks"]
    )
    window_rows = []
    for row in report["merged_windows"]:
        left, right = local_time(row["start"]), local_time(row["end"])
        end_label = time_label(right) if left.date() == right.date() else stamp(row["end"])
        window_rows.append(
            f"<tr><td>{escape(date_label(left))}</td>"
            f"<td>{escape(time_label(left))} → {escape(end_label)}</td>"
            f"<td class=minutes>{escape(row['minutes'])}분</td></tr>"
        )
    windows = (
        '<div class="table-wrap"><table class="windows"><thead><tr>'
        '<th scope="col">날짜</th><th scope="col">시간</th><th scope="col">사용 가능</th>'
        '</tr></thead><tbody>' + "".join(window_rows) + '</tbody></table></div>'
    ) if window_rows else '<p>기준 시각부터 마감 사이에 등록된 가용시간이 없습니다.</p>'
    assumptions = "".join(f"<p>{escape(item)}</p>" for item in report["assumptions"])
    source_labels = {"tasks": "준비 작업", "availability": "작업 가능한 시간"}
    sources = "".join(
        f"<div><dt>{escape(source_labels.get(key, key))}</dt><dd>{escape(Path(value).name)}</dd></div>"
        for key, value in report["source_paths"].items()
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>발표 준비 시간 점검</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f5f6;color:#20313c;font:16px/1.75 system-ui,"Malgun Gothic",sans-serif}}
main{{max-width:1000px;margin:40px auto;padding:44px;background:white;border-radius:16px}}
h1{{margin:0 0 12px;font-size:30px;line-height:1.4}}h2{{margin:0 0 14px;font-size:21px}}
p{{margin:0 0 14px}}section{{margin-top:36px}}.muted{{color:#56656d;font-size:14px}}
dl{{margin:0}}dt{{color:#56656d}}dd{{margin:0;overflow-wrap:anywhere}}
.dates>div,.sources>div{{display:grid;grid-template-columns:145px 1fr;gap:12px;margin-bottom:10px}}
.dates{{margin-top:24px}}.result{{padding:22px 24px;border-left:5px solid #426b78;background:#eef5f6;border-radius:8px}}
.result h2{{font-size:22px;margin-bottom:8px}}.result p{{margin:0}}
.tight{{border-color:#a56b16;background:#fff6e7}}.shortage{{border-color:#b34133;background:#fff0ed}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px}}
.cards div{{padding:18px 16px;background:#f4f7f8;border:1px solid #dce4e7;border-radius:10px}}
.cards span,.cards strong{{display:block}}.cards span{{font-size:14px;color:#56656d}}.cards strong{{font-size:27px;font-variant-numeric:tabular-nums}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:15px 12px;text-align:left;border-bottom:1px solid #dce4e7;vertical-align:top}}
th{{font-size:14px;color:#56656d;background:#f5f7f8}}tbody tr:nth-child(even){{background:#fafbfc}}
.task{{line-height:1.8;white-space:pre-line;overflow-wrap:anywhere}}.task-id{{color:#687780;font-size:14px;white-space:nowrap}}
.minutes,.status{{white-space:nowrap}}.minutes{{text-align:right;font-variant-numeric:tabular-nums}}
.table-wrap{{overflow-x:auto}}.notes{{padding:22px 24px;background:#f7f8f9;border-radius:10px}}.notes p:last-child{{margin-bottom:0}}
@media(max-width:650px){{main{{margin:0;padding:24px 18px;border-radius:0}}h1{{font-size:26px}}.cards{{grid-template-columns:repeat(2,1fr)}}
.dates>div,.sources>div{{grid-template-columns:1fr;gap:0}}th,td{{padding:12px 8px}}table{{font-size:14px}}.task-id{{font-size:12px}}.result,.notes{{padding:18px}}}}
@media print{{@page{{size:A4;margin:16mm}}body{{background:white;font-size:11pt}}main{{margin:0;padding:0;max-width:none}}
section{{margin-top:24px}}h2{{break-after:avoid}}tr,.result,.cards,.notes{{break-inside:avoid}}thead{{display:table-header-group}}
.table-wrap{{overflow:visible}}.cards strong{{font-size:22px}}th,td{{padding:10px 8px}}}}
</style></head><body><main><header><h1>발표 준비 시간 점검</h1>
<p class="muted">등록한 작업과 시간을 비교한 결과입니다.</p>
<dl class="dates"><div><dt>점검 기준</dt><dd>{escape(stamp(report['as_of']))}</dd></div>
<div><dt>발표 준비 마감</dt><dd>{escape(stamp(report['deadline']))}</dd></div></dl>
<p class="muted">모든 시각은 {escape(zone_label)} 기준입니다.</p></header>
<section class="result {tone}"><h2>{escape(headline)}</h2><p>{escape(guidance)}</p></section>
<section class="cards" aria-label="시간 계산 요약">{cards}</section>
<section><h2>작업별 준비 상태</h2>
<div class="table-wrap"><table><thead><tr><th scope="col">ID</th><th scope="col">작업</th>
<th scope="col" class="minutes">남은 예상 시간</th><th scope="col">상태</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2>작업에 쓸 수 있는 시간</h2><p class="muted">점검 기준부터 마감까지의 시간만 포함하고, 겹친 시간은 한 번만 셌습니다.</p>{windows}</section>
<section class="notes"><h2>결과를 읽을 때</h2>{assumptions}</section>
<section><h2>계산에 사용한 파일</h2><dl class="sources">{sources}</dl>
<p class="muted">파일의 전체 위치와 계산에 사용한 원래 값은 함께 저장한 JSON에서 확인할 수 있습니다.</p></section>
</main></body></html>"""


def ensure_distinct_paths(inputs, outputs):
    resolved_inputs = {Path(path).resolve() for path in inputs}
    resolved_outputs = [Path(path).resolve() for path in outputs]
    if resolved_inputs.intersection(resolved_outputs):
        raise InputError("출력 경로가 입력 파일과 같습니다. 다른 출력 경로를 지정하세요.")
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise InputError("JSON과 HTML은 서로 다른 출력 경로여야 합니다.")
    # 심볼릭 링크뿐 아니라 이미 존재하는 하드 링크도 같은 파일로 취급한다.
    for index, output in enumerate(resolved_outputs):
        if not output.exists():
            continue
        for other in [*resolved_inputs, *resolved_outputs[:index]]:
            if other.exists() and output.samefile(other):
                raise InputError("출력 경로가 입력이나 다른 출력과 같은 파일을 가리킵니다.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, type=Path, help="준비작업.csv")
    parser.add_argument("--availability", required=True, type=Path, help="작업가능시간.csv")
    parser.add_argument("--as-of", required=True, help="기준 시각. 예: 2026-09-16T14:00+09:00")
    parser.add_argument("--deadline", required=True, help="마감 시각. 시간대 필수")
    parser.add_argument("--output", required=True, type=Path, help="계산 결과 JSON 저장 경로")
    parser.add_argument("--html", type=Path, help="같은 계산 결과를 볼 HTML 저장 경로")
    args = parser.parse_args(argv)
    try:
        outputs = [args.output] + ([args.html] if args.html else [])
        ensure_distinct_paths([args.tasks, args.availability, Path(__file__)], outputs)
        report = calculate(args.tasks, args.availability, args.as_of, args.deadline)
        documents = [(args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")]
        if args.html:
            documents.append((args.html, render_html(report)))
        for path, content in documents:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"저장: {path.resolve()}")
    except (InputError, OSError, UnicodeError) as exc:
        parser.exit(2, f"오류: {exc}\n")


if __name__ == "__main__":
    main()
