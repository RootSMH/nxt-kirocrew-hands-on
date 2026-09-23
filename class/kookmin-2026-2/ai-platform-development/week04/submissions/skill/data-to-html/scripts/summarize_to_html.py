#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""여러 markdown/CSV 파일을 읽어 요약한 결과를 하나의 자기완결형 HTML로 만든다.

- 여러 입력을 받는다(-i 를 여러 번, 또는 디렉터리를 주면 그 안의 .md/.csv 를 정렬해 수집).
- markdown: 제목(첫 #), 앞 문단(리드), 섹션 제목 목록으로 '요약 카드'를 만든다.
- CSV: 행/열 수와 전체 헤더를 보이고, 핵심 내용을 표로 담는다(기본 앞 N행 미리보기, --full-csv 로 전체).
- 결정론적: 같은 입력이면 같은 출력. 외부 네트워크·의존성 없음(표준 라이브러리만).
- 모든 텍스트는 HTML 이스케이프(주입 방지). 출력은 UTF-8(BOM 없음), 스크립트가 직접 파일에 쓴다.

종료 코드: 0 성공 / 1 입력·스키마 오류(유효한 입력이 하나도 없을 때).
"""
import argparse
import csv as csvmod
import html
import io
import os
import re
import sys


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slugify(s: str, idx: int) -> str:
    base = re.sub(r"[^0-9A-Za-z가-힣]+", "-", s).strip("-").lower()
    return f"s{idx}-{base}" if base else f"s{idx}"


# ---------- markdown 요약 ----------
def summarize_md(text: str):
    """제목, 리드 문단, 섹션 제목 목록을 뽑는다."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    title = None
    headings = []  # (level, text)
    lead = None
    in_fence = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl, htext = len(m.group(1)), m.group(2).strip()
            if title is None and lvl == 1:
                title = htext
            else:
                headings.append((lvl, htext))
            continue
        if lead is None and s and not s.startswith((">", "-", "*", "+", "|")) and not re.match(r"^\d+\.\s", s):
            lead = s
    return {"title": title, "lead": lead, "headings": headings}


def render_inline(text: str) -> str:
    out = esc(text)
    out = re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1) + "</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    return out


def md_card(name: str, summary: dict) -> str:
    title = summary["title"] or name
    parts = [f'<h3 class="doc-title">{render_inline(title)}</h3>']
    parts.append(f'<p class="meta">markdown · {esc(name)}</p>')
    if summary["lead"]:
        parts.append(f'<p class="lead">{render_inline(summary["lead"])}</p>')
    if summary["headings"]:
        items = "".join(
            f'<li class="lvl{lvl}">{render_inline(h)}</li>' for lvl, h in summary["headings"]
        )
        parts.append(f'<p class="meta">섹션 {len(summary["headings"])}개</p>')
        parts.append(f'<ul class="headings">{items}</ul>')
    return "".join(parts)


# ---------- csv 요약 ----------
def sniff_delimiter(sample: str) -> str:
    try:
        return csvmod.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except Exception:
        first = sample.split("\n", 1)[0]
        counts = {d: first.count(d) for d in [",", "\t", ";"]}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def csv_card(name: str, text: str, delimiter, preview_rows: int, full: bool) -> str:
    text = text.lstrip("\ufeff")
    if delimiter is None:
        delimiter = sniff_delimiter(text[:4096])
    rows = [r for r in csvmod.reader(io.StringIO(text), delimiter=delimiter)]
    if not rows:
        raise ValueError(f"CSV에 데이터가 없습니다: {name}")
    header, body = rows[0], rows[1:]
    ncol = len(header)
    shown = body if full else body[:preview_rows]
    hidden = len(body) - len(shown)

    h = "".join(f"<th>{esc(c)}</th>" for c in header)
    trs = []
    for r in shown:
        r = (r + [""] * ncol)[:ncol]
        trs.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>")

    meta = f"행 {len(body)}개 · 열 {ncol}개 · 구분자 <code>{esc(repr(delimiter))}</code>"
    if hidden > 0:
        meta += f" · 표에는 앞 {len(shown)}행만 표시({hidden}행 생략, 핵심 내용 발췌)"
    return (
        f'<h3 class="doc-title">{esc(name)}</h3>'
        f'<p class="meta">CSV · {meta}</p>'
        '<div class="table-wrap"><table class="md-table"><thead><tr>'
        + h
        + "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )


# ---------- 페이지 ----------
PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, "Segoe UI", "Malgun Gothic", system-ui, sans-serif;
    line-height: 1.6; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fff; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #e6e6e6; background: #16181c; }}
    a {{ color: #7cc4ff; }} code {{ background: #2a2d33; }} th {{ background: #23262c; }}
    tr:nth-child(even) td {{ background: #1c1f24; }} .card {{ border-color: #2a2d33; }}
    .meta {{ color: #9aa0aa; }} }}
  h1 {{ line-height: 1.25; border-bottom: 2px solid currentColor; padding-bottom: .3rem; }}
  h2 {{ margin-top: 2.5rem; }}
  .doc-title {{ margin: 0 0 .2rem; }}
  nav.toc {{ background: #f5f6f8; border-radius: 8px; padding: .8rem 1.2rem; }}
  @media (prefers-color-scheme: dark) {{ nav.toc {{ background: #1c1f24; }} }}
  nav.toc ul {{ margin: .3rem 0; padding-left: 1.2rem; }}
  .card {{ border: 1px solid #e0e3e8; border-radius: 10px; padding: 1rem 1.2rem; margin: 1rem 0; }}
  .lead {{ font-size: 1.02em; }}
  ul.headings {{ margin: .3rem 0; padding-left: 1.2rem; }}
  ul.headings li {{ list-style: "· "; }}
  ul.headings li.lvl3 {{ margin-left: 1rem; }}
  ul.headings li.lvl4, ul.headings li.lvl5, ul.headings li.lvl6 {{ margin-left: 2rem; }}
  code {{ background: #f1f2f4; padding: .1em .35em; border-radius: 4px; font-size: .9em; }}
  .table-wrap {{ overflow-x: auto; }}
  table.md-table {{ border-collapse: collapse; width: 100%; margin: .6rem 0; font-size: .92em; }}
  th, td {{ border: 1px solid #d0d3d8; padding: .45rem .6rem; text-align: left; white-space: nowrap; }}
  th {{ background: #f5f6f8; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  .meta {{ color: #888; font-size: .85em; margin: .2rem 0; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #d0d3d8; color: #888; font-size: .8em; }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p class="meta">markdown {n_md}개 · CSV {n_csv}개 요약</p>
<nav class="toc"><strong>목차</strong><ul>{toc}</ul></nav>
{sections}
</main>
<footer>data-to-html (요약) · 입력 {n_total}개 파일</footer>
</body>
</html>
"""


def detect_kind(path: str, forced):
    if forced:
        return forced
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown"):
        return "md"
    if ext in (".csv", ".tsv"):
        return "csv"
    return None


def collect_inputs(inputs):
    """파일·디렉터리 섞인 목록을 (경로 정렬된) 파일 목록으로 편다."""
    files = []
    for p in inputs:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                full = os.path.join(p, name)
                if os.path.isfile(full) and detect_kind(full, None):
                    files.append(full)
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"[경고] 건너뜀(파일 없음): {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser(description="여러 markdown/CSV -> 요약 HTML 한 개")
    ap.add_argument("-i", "--input", action="append", required=True,
                    help="입력 파일 또는 디렉터리(여러 번 지정 가능)")
    ap.add_argument("-o", "--output", help="출력 HTML(UTF-8, BOM 없음). 없으면 stdout")
    ap.add_argument("--title", default="문서·데이터 요약", help="페이지 제목")
    ap.add_argument("--preview-rows", type=int, default=10, help="CSV 표에 담을 앞 행 수(기본 10)")
    ap.add_argument("--full-csv", action="store_true", help="CSV 전체 행을 표에 담는다")
    ap.add_argument("--delimiter", help="CSV 구분자 강제(예: , 또는 ;). 탭은 TAB")
    args = ap.parse_args()

    files = collect_inputs(args.input)
    if not files:
        print("[오류] 유효한 입력 파일이 없습니다.", file=sys.stderr)
        return 1

    delim = args.delimiter
    if delim == "TAB":
        delim = "\t"

    toc_items = []
    sections = []
    n_md = n_csv = 0
    for idx, path in enumerate(files, 1):
        name = os.path.basename(path)
        kind = detect_kind(path, None)
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except OSError as e:
            print(f"[경고] 읽기 실패, 건너뜀: {path} ({e})", file=sys.stderr)
            continue
        try:
            if kind == "md":
                summary = summarize_md(text)
                anchor = slugify(summary["title"] or name, idx)
                card = md_card(name, summary)
                label = summary["title"] or name
                n_md += 1
            else:
                anchor = slugify(name, idx)
                card = csv_card(name, text, delim, args.preview_rows, args.full_csv)
                label = name
                n_csv += 1
        except ValueError as e:
            print(f"[경고] 요약 실패, 건너뜀: {path} ({e})", file=sys.stderr)
            continue
        toc_items.append(f'<li><a href="#{anchor}">{esc(label)}</a></li>')
        sections.append(f'<section id="{anchor}" class="card">{card}</section>')

    if not sections:
        print("[오류] 요약할 수 있는 파일이 없습니다.", file=sys.stderr)
        return 1

    page = PAGE.format(
        title=esc(args.title),
        toc="".join(toc_items),
        sections="\n".join(sections),
        n_md=n_md,
        n_csv=n_csv,
        n_total=n_md + n_csv,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        print(f"저장 완료: {args.output} (markdown {n_md}, CSV {n_csv})")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
