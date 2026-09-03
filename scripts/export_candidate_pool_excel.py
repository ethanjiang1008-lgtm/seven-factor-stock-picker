#!/usr/bin/env python3
"""Export the latest seven-factor candidate pool to a standalone .xlsx file.

Uses only Python's standard library to avoid an external spreadsheet dependency.
The workbook contains:
- 候选池: full daily candidate pool, sorted by pool priority and adjusted score
- 市场概览: scan metadata, market sentiment, factor weights and top sectors/concepts
"""
import html
import json
import os
import zipfile
from xml.sax.saxutils import escape as xml_escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(DATA_DIR, "candidate_pool_reviews")
DATA_FILE = os.path.join(DATA_DIR, "seven_factor_latest.json")
HISTORY_FILE = os.path.join(DATA_DIR, "candidate_pool_history.json")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def text(v):
    if v is None or v == "":
        return "-"
    if isinstance(v, (list, tuple)):
        return "；".join(str(x) for x in v) if v else "-"
    return str(v)


def col_name(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_xml(ref, value, style=0, kind=None):
    if value is None:
        return f'<c r="{ref}" s="{style}"/>'
    if kind == "number":
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    value = xml_escape(text(value))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{value}</t></is></c>'


def sheet_xml(rows, widths, freeze_rows=1, autofilter_end=None):
    cols = []
    for i, width in enumerate(widths, 1):
        cols.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    body = []
    for r_idx, row in enumerate(rows, 1):
        cells = []
        for c_idx, item in enumerate(row, 1):
            value, style, kind = item
            cells.append(cell_xml(f"{col_name(c_idx)}{r_idx}", value, style, kind))
        body.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    pane = f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="{freeze_rows}" topLeftCell="A{freeze_rows + 1}" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A{freeze_rows + 1}" sqref="A{freeze_rows + 1}"/></sheetView></sheetViews>' if freeze_rows else '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
    autofilter = f'<autoFilter ref="A1:{autofilter_end}"/>' if autofilter_end else ''
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
        + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' \
        + pane + '<cols>' + ''.join(cols) + '</cols><sheetData>' + ''.join(body) + '</sheetData>' + autofilter \
        + '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0" footer="0"/></worksheet>'


def build_xlsx(path, sheet_specs):
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
'''
    for i in range(1, len(sheet_specs) + 1):
        content_types += f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    content_types += '</Types>'

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''

    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
        + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' \
        + '<sheets>' \
        + ''.join(f'<sheet name="{xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _, _, _) in enumerate(sheet_specs, 1)) \
        + '</sheets></workbook>'

    wb_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' \
        + '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' \
        + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheet_specs) + 1)) \
        + '</Relationships>'

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="4"><numFmt numFmtId="164" formatCode="0.0"/><numFmt numFmtId="165" formatCode="0.00"/><numFmt numFmtId="166" formatCode="0.0%"/><numFmt numFmtId="167" formatCode="yyyy-mm-dd hh:mm:ss"/></numFmts>
<fonts count="3"><font><sz val="10"/><name val="Microsoft YaHei"/></font><font><b/><sz val="10"/><name val="Microsoft YaHei"/></font><font><b/><sz val="12"/><name val="Microsoft YaHei"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="D9EAF7"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/><diagonal/></border></borders>
<cellXfs count="9">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="1"/>
<xf numFmtId="167" fontId="0" fillId="0" borderId="1"/><xf numFmtId="0" fontId="1" fillId="0" borderId="1"/><xf numFmtId="0" fontId="2" fillId="2" borderId="1"/>
</cellXfs></styleSheet>'''

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', root_rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        z.writestr('xl/styles.xml', styles)
        for i, (_, rows, widths, end_ref) in enumerate(sheet_specs, 1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', sheet_xml(rows, widths, freeze_rows=1, autofilter_end=end_ref))


def style_value(value, style):
    return (value, style, None)


def num_cell(value, style=4):
    return (value, style, 'number')


def pct_cell(value):
    return (num(value) / 100.0, 6, 'number')


def main():
    data = load_json(DATA_FILE)
    history = load_json(HISTORY_FILE) if os.path.exists(HISTORY_FILE) else {}
    candidates = list(data.get('candidates') or [])
    if not candidates:
        raise SystemExit('candidate pool empty; refusing to create Excel review')

    scan_date = text(data.get('scan_date'))
    scan_time = text(data.get('scan_time'))
    sentiment = data.get('market_sentiment') or {}
    pool_order = {'重点观察': 0, '预备池': 1, '观察池': 2, '淘汰': 3}

    enriched = []
    for r in candidates:
        code = str(r.get('code') or '')
        h = history.get(code) if isinstance(history.get(code), dict) else {}
        rec = r.get('recency') or {}
        hist = r.get('history') or {}
        res = r.get('resonance') or {}
        scores = r.get('scores') or {}
        watch = r.get('next_day_watch') or []
        entered = h.get('entered_at') or r.get('pool_entry_time') or '-'
        enriched.append((r, entered, rec, hist, res, scores, watch))

    enriched.sort(key=lambda x: (pool_order.get(x[0].get('pool'), 9), -num(x[0].get('adjusted_total'))))

    headers = ['排名','入池时间','代码','名称','行业','价格','涨跌幅','换手率','流通市值(亿)','调整分','原始分','P级','P级标签','候选池','评级','三共振','连板概率','历史涨停次数','最高连板','距上次涨停(日)','次日重点1','次日重点2']
    rows = [[style_value(h, 1) for h in headers]]
    for i, (r, entered, rec, hist, res, scores, watch) in enumerate(enriched, 1):
        rows.append([
            num_cell(i, 3), style_value(entered, 2), style_value(str(r.get('code') or ''), 2), style_value(r.get('name'), 2),
            style_value(r.get('sector') or r.get('sw_industry'), 2), num_cell(num(r.get('price')), 4), pct_cell(r.get('change_pct')),
            pct_cell(r.get('turnover_rate')), num_cell(num(r.get('circ_mcap_yi')), 4), num_cell(num(r.get('adjusted_total')), 4),
            num_cell(num(scores.get('total')), 4), style_value('P' + text(rec.get('tier')), 2), style_value(rec.get('tag'), 2),
            style_value(r.get('pool'), 2), style_value(r.get('grade'), 2), num_cell(num(res.get('count')), 3),
            pct_cell(r.get('lianban_probability')), num_cell(num(hist.get('limit_up_count')), 3), num_cell(num(hist.get('max_consecutive')), 3),
            num_cell(num(hist.get('days_since_last_lu')), 3), style_value(watch[0] if len(watch) > 0 else '-', 2), style_value(watch[1] if len(watch) > 1 else '-', 2)
        ])

    overview = [
        [style_value('七因子候选池每日复盘', 8)],
        [style_value('扫描日期', 7), style_value(scan_date, 2)],
        [style_value('扫描时间', 7), style_value(scan_time, 2)],
        [style_value('系统版本', 7), style_value(data.get('system_version'), 2)],
        [style_value('模型', 7), style_value(data.get('model'), 2)],
        [],
        [style_value('市场情绪', 8), style_value('数值', 8)],
        [style_value('情绪分', 7), num_cell(num(sentiment.get('sentiment_score')), 4)],
        [style_value('情绪标签', 7), style_value(sentiment.get('sentiment_label'), 2)],
        [style_value('涨停数', 7), num_cell(num(sentiment.get('limit_up_count')), 3)],
        [style_value('跌停数', 7), num_cell(num(sentiment.get('limit_down_count')), 3)],
        [style_value('强势股数', 7), num_cell(num(sentiment.get('strong_count')), 3)],
        [style_value('炸板率', 7), pct_cell(sentiment.get('explosion_rate'))],
        [style_value('最高连板', 7), num_cell(num(sentiment.get('max_boards_est')), 3)],
        [],
        [style_value('七因子权重', 8), style_value('分值', 8)],
    ]
    for k, v in (data.get('weight_config') or {}).items():
        overview.append([style_value(k, 2), num_cell(num(v), 3)])
    overview += [[], [style_value('候选池数量', 8), style_value('数量', 8)]]
    for p in ['重点观察', '预备池', '观察池', '淘汰']:
        overview.append([style_value(p, 2), num_cell(sum(1 for r in candidates if r.get('pool') == p), 3)])
    overview += [[], [style_value('行业排名 TOP 15', 8), style_value('涨跌幅', 8), style_value('涨停', 8), style_value('强势', 8)]]
    for x in sorted(data.get('sector_rankings') or [], key=lambda x: num(x.get('rank')))[:15]:
        overview.append([style_value(x.get('name'), 2), pct_cell(x.get('avg_change')), num_cell(num(x.get('limit_up_count')), 3), num_cell(num(x.get('strong_count')), 3)])
    overview += [[], [style_value('概念排名 TOP 15', 8), style_value('涨跌幅', 8), style_value('涨停', 8), style_value('强势', 8)]]
    for x in sorted(data.get('concept_rankings') or [], key=lambda x: num(x.get('rank')))[:15]:
        overview.append([style_value(x.get('name'), 2), pct_cell(x.get('avg_change')), num_cell(num(x.get('limit_up_count')), 3), num_cell(num(x.get('strong_count')), 3)])

    output = os.path.join(OUT_DIR, f'候选池复盘_{scan_date}.xlsx')
    build_xlsx(output, [
        ('候选池', rows, [7, 21, 10, 14, 14, 10, 10, 10, 13, 10, 10, 8, 14, 12, 8, 9, 11, 12, 10, 16, 24, 24], f'V{len(rows)}'),
        ('市场概览', overview, [22, 18, 14, 14], None),
    ])
    print(f'Excel review exported: {output}')


if __name__ == '__main__':
    main()
