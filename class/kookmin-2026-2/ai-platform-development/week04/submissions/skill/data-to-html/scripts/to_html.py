#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""markdown 또는 csv 파일을 읽어 하나의 자기완결형 HTML로 변환한다.

- 확장자(.md/.markdown, .csv/.tsv)로 입력 종류를 판별하며 --kind로 강제할 수 있다.
- 결정론적: 같은 입력 -> 같은 출력. 외부 네트워크·의존성 없음(표준 라이브러리만).
- markdown: 문단/제목/목록/코드블록/표/굵게·기울임/인라인코드/링크만 지원(부분집합).
- csv: 헤더 1행 + 데이터로 <table> 렌더. 구분자 자동 감지(,/\t/;) 또는 --delimiter.
- 출력은 UTF-8(BOM 없음). PowerShell Out-File 대신 이 스크립트가 직접 파일에 쓴다.

종료 코드: 0 성공 / 1 입력·스키마 오류.
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


# ---------- inline markdown ----------
def render_inline(text: str) -> str:
    # 먼저 escape 후, 안전한 토큰만 태그로 복원
    out = esc(text)
    # 인라인 코드 `code`
    out = re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1) + "</code>", out)
    # 링크 [text](url)
    out = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda m: f'<a href="{m.group(2)}" rel="noopener noreferrer">{m.group(1)}</a>',
        out,
    )
    # 굵게 **x**
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    # 기울임 *x*
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    return out


def md_table_block(lines):
    """lines: 표 후보 줄들. 유효한 GFM 표면 HTML 반환, 아니면 None."""
    if len(lines) < 2:
        return None
    sep = lines[1].strip()
    if not re.match(r"^\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?$", sep):
        return None

    def cells(row):
        row = row.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [c.strip() for c in row.split("|")]

    header = cells(lines[0])
    body = [cells(l) for l in lines[2:] if l.strip()]
    h = "".join(f"<th>{render_inline(c)}</th>" for c in header)
    rows = []
    for r in body:
        r = (r + [""] * len(header))[: len(header)]
        rows.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in r) + "</tr>")
    return (
        '<table class="md-table"><thead><tr>'
        + h
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def markdown_to_body(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 코드 펜스
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 닫는 펜스
            out.append("<pre><code>" + esc("\n".join(buf)) + "</code></pre>")
            continue

        # 빈 줄
        if stripped == "":
            i += 1
            continue

        # 제목
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{render_inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue

        # 인용
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + render_inline(" ".join(buf)) + "</blockquote>")
            continue

        # 수평선
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            out.append("<hr>")
            i += 1
            continue

        # 표
        if "|" in stripped and i + 1 < n:
            block = [lines[i]]
            j = i + 1
            while j < n and "|" in lines[j] and lines[j].strip():
                block.append(lines[j])
                j += 1
            tbl = md_table_block(block)
            if tbl:
                out.append(tbl)
                i = j
                continue

        # 목록 (- * + 또는 1.)
        if re.match(r"^([-*+]|\d+\.)\s+", stripped):
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            tag = "ol" if ordered else "ul"
            items = []
            while i < n and re.match(r"^([-*+]|\d+\.)\s+", lines[i].strip()):
                item = re.sub(r"^([-*+]|\d+\.)\s+", "", lines[i].strip())
                items.append(f"<li>{render_inline(item)}</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        # 문단(연속 비어있지 않은 줄)
        buf = []
        while i < n and lines[i].strip() != "" and not lines[i].strip().startswith(("#", ">", "```")):
            if re.match(r"^([-*+]|\d+\.)\s+", lines[i].strip()):
                break
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + render_inline(" ".join(buf)) + "</p>")

    return "\n".join(out)


# ---------- csv ----------
def sniff_delimiter(sample: str) -> str:
    try:
        return csvmod.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except Exception:
        # 첫 줄에서 가장 많이 나오는 후보
        first = sample.split("\n", 1)[0]
        counts = {d: first.count(d) for d in [",", "\t", ";"]}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def csv_to_body(text: str, delimiter: str | None) -> str:
    text = text.lstrip("\ufeff")
    if delimiter is None:
        delimiter = sniff_delimiter(text[:4096])
    reader = csvmod.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader]
    if not rows:
        raise ValueError("CSV에 데이터가 없습니다.")
    header, body = rows[0], rows[1:]
    ncol = len(header)
    h = "".join(f"<th>{esc(c)}</th>" for c in header)
    trs = []
    for r in body:
        r = (r + [""] * ncol)[:ncol]
        trs.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>")
    caption = f"<p class=\"meta\">행 {len(body)}개 · 열 {ncol}개 · 구분자 <code>{esc(repr(delimiter))}</code></p>"
    return (
        caption
        + '<table class="md-table"><thead><tr>'
        + h
        + "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table>"
    )


# ---------- page ----------
PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, "Segoe UI", "Malgun Gothic", system-ui, sans-serif;
    line-height: 1.6; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fff; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #e6e6e6; background: #16181c; }}
    a {{ color: #7cc4ff; }} code {{ background: #2a2d33; }} th {{ background: #23262c; }}
    tr:nth-child(even) td {{ background: #1c1f24; }} blockquote {{ border-color: #3a3f47; color: #b8bcc4; }} }}
  h1,h2,h3 {{ line-height: 1.25; }}
  h1 {{ border-bottom: 2px solid currentColor; padding-bottom: .3rem; }}
  code {{ background: #f1f2f4; padding: .1em .35em; border-radius: 4px; font-size: .9em; }}
  pre {{ background: #f1f2f4; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  table.md-table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .95em; }}
  th, td {{ border: 1px solid #d0d3d8; padding: .5rem .7rem; text-align: left; }}
  th {{ background: #f5f6f8; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  blockquote {{ margin: 1rem 0; padding: .2rem 1rem; border-left: 4px solid #c8ccd2; color: #555; }}
  .meta {{ color: #888; font-size: .85em; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #d0d3d8; color: #888; font-size: .8em; }}
</style>
</head>
<body>
<main>
{body}
</main>
<footer>data-to-html · 원본: {source}</footer>
</body>
</html>
"""


def detect_kind(path: str, forced: str | None) -> str:
    if forced:
        return forced
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown"):
        return "md"
    if ext in (".csv", ".tsv"):
        return "csv"
    raise ValueError(f"입력 종류를 알 수 없습니다(확장자 {ext!r}). --kind md|csv 로 지정하세요.")


def main():
    ap = argparse.ArgumentParser(description="markdown/csv -> 자기완결형 HTML")
    ap.add_argument("-i", "--input", required=True, help="입력 파일(.md/.markdown/.csv/.tsv)")
    ap.add_argument("-o", "--output", help="출력 HTML 경로(UTF-8, BOM 없음). 없으면 stdout")
    ap.add_argument("--kind", choices=["md", "csv"], help="입력 종류 강제(확장자 무시)")
    ap.add_argument("--title", help="문서 제목(기본: 입력 파일명)")
    ap.add_argument("--delimiter", help="CSV 구분자 강제(예: , 또는 ;). 탭은 TAB")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"[오류] 입력 파일이 없습니다: {args.input}", file=sys.stderr)
        return 1

    try:
        kind = detect_kind(args.input, args.kind)
    except ValueError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 1

    with open(args.input, "r", encoding="utf-8-sig") as f:
        text = f.read()

    title = args.title or os.path.basename(args.input)
    try:
        if kind == "md":
            body = markdown_to_body(text)
        else:
            delim = args.delimiter
            if delim == "TAB":
                delim = "\t"
            body = csv_to_body(text, delim)
    except ValueError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 1

    page = PAGE.format(title=esc(title), body=body, source=esc(os.path.basename(args.input)))

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        print(f"저장 완료: {args.output} ({kind})")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
