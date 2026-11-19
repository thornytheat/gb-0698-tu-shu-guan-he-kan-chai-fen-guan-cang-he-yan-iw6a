# 跨年合刊：期次各归其年，实体册只计一次
from app.pipeline import run
from app.modules.m3_issues.rules import expand, parse
from app.modules.m4_combined.rules import splits, cross_year
from app import store
from app.exporter import evidence_csv
from app.errors import BusinessError
import pytest

HEADER = "record_id,title,issn,year,volume,issue,copy,binding,status,note"

def csv_text(*rows):
    return "\n".join([HEADER, *rows])

def held(rid, issue, year="2025", binding=None, status="held"):
    return ",".join([rid, "数据工程月刊", "1000-0001", year, "001", issue, "01", binding or ("B" + rid), status, "期刊"])

def base_rows(cross="2025:12/2026:1"):
    rows = [held(f"R{i:02d}", str(i)) for i in range(1, 12)]
    rows.append(held("R12", cross))
    rows += [held(f"N{i:02d}", str(i), year="2026") for i in range(2, 13)]
    return rows

def gap(result, year):
    return next(g for g in result["gaps"] if g["year"] == year)

# --- 语法解析 ---

def test_parse_cross_pairs():
    assert parse("2025:12/2026:1") == [("2025", "12"), ("2026", "1")]

def test_expand_cross_issues():
    assert expand("2025:12/2026:1") == ["12", "1"]

def test_parse_cross_fullwidth():
    assert parse("２０２５：１２／２０２６：１") == [("2025", "12"), ("2026", "1")]

@pytest.mark.parametrize("bad", ["2025:12/1", "2025:11-12", "2025:S1/2026:1", "1899:12/1900:1", "2025:0/2026:1"])
def test_parse_cross_form_rejected(bad):
    with pytest.raises(BusinessError) as caught:
        parse(bad)
    assert caught.value.code == "CROSS_YEAR_FORM"

@pytest.mark.parametrize("bad", ["2025:12/2027:1", "2026:1/2025:12", "2026:1/2026:2"])
def test_parse_cross_sequence_rejected(bad):
    with pytest.raises(BusinessError) as caught:
        parse(bad)
    assert caught.value.code == "CROSS_YEAR_SEQUENCE"

# --- 缺期与补录：按每期实际覆盖 ---

def test_cross_clears_false_gap():
    r = run(csv_text(*base_rows()))
    assert gap(r, "2025")["status"] == "COMPLETE"
    assert gap(r, "2026")["status"] == "COMPLETE"
    assert r["final"] == []

def test_cross_naive_record_would_false_report():
    r = run(csv_text(*base_rows(cross="12")))
    assert gap(r, "2026")["missing"] == ["1"]
    assert [(t["year"], t["issue"]) for t in r["final"]] == [("2026", "1")]

def test_cross_marker_on_next_year():
    r = run(csv_text(*base_rows()))
    assert gap(r, "2026")["cross"] == ["1"]
    assert gap(r, "2025")["cross"] == []

# --- 实体册：同一册不重复计 ---

def test_cross_book_counted_once():
    r = run(csv_text(*base_rows()))
    assert r["books"] == 23
    volume = r["cross_year"][0]
    assert volume["physical_books"] == 1 and volume["covered_issues"] == 2

def test_cross_aggregation_reviewable():
    r = run(csv_text(*base_rows()))
    volume = r["cross_year"][0]
    assert volume["years"] == ["2025", "2026"]
    assert volume["coverage"] == [{"year": "2025", "issue": "12"}, {"year": "2026", "issue": "1"}]
    assert volume["anchor_year"] == "2025" and volume["binding"] == "BR12" and volume["line"]

def test_cross_anchor_may_be_later_year():
    rows = base_rows()
    rows[11] = held("R12", "2025:12/2026:1", year="2026")
    r = run(csv_text(*rows))
    assert r["books"] == 23
    assert r["cross_year"][0]["anchor_year"] == "2026"
    assert gap(r, "2025")["cross"] == ["12"]
    assert gap(r, "2025")["status"] == "COMPLETE"

# --- 未核清记录不混入正式结果 ---

def test_cross_anchor_unrelated_quarantined():
    rows = base_rows()
    rows[11] = held("R12", "2025:12/2026:1", year="2024")
    r = run(csv_text(*rows))
    assert any(q["reason"] == "CROSS_YEAR_ANCHOR" for q in r["quarantine"])
    assert all(h["record_id"] != "R12" for h in r["held"])
    assert gap(r, "2026")["missing"] == ["1"]

def test_cross_bad_form_quarantined_not_counted():
    rows = base_rows()
    rows[11] = held("R12", "2025:12/1")
    r = run(csv_text(*rows))
    assert any(q["reason"] == "CROSS_YEAR_FORM" for q in r["quarantine"])
    assert r["books"] == 22
    assert gap(r, "2025")["missing"] == ["12"]

# --- 一册被两个年度分记：疑似重复，阻断复核 ---

def test_split_detected_and_blocking():
    rows = base_rows()
    rows[11] = held("R12", "12", binding="BX")
    rows.append(held("N01", "1", year="2026", binding="BX"))
    r = run(csv_text(*rows))
    assert [c["reason"] for c in r["split_conflicts"]] == ["CROSS_YEAR_SPLIT"]
    assert r["blocked"] is True

def test_split_review_rejected():
    text = csv_text(*[held("A1", "12", binding="BX"), held("A2", "1", year="2026", binding="BX")])
    item = store.save(text, run(text))
    with pytest.raises(BusinessError, match="阻断"):
        store.review(item["id"], item["revision"], "通过")

def test_splits_same_year_not_flagged():
    r = {"journal_key": "i", "year": "2026", "copy": "01", "binding": "a", "record_id": "1", "status": "held"}
    assert splits([r, dict(r, record_id="2")]) == []

def test_cross_year_helper_ignores_single_year():
    r = {"issues": ["1", "2"], "year": "2026", "record_id": "1", "copy": "01", "binding": "a"}
    assert cross_year([r]) == []

# --- 晚到修正不改写已确认覆盖 ---

def test_late_conflicting_record_flagged_not_applied():
    rows = base_rows() + [held("L99", "1", year="2026", binding="BLATE")]
    r = run(csv_text(*rows))
    assert [c["reason"] for c in r["binding_conflicts"]] == ["BINDING_CONFLICT"]
    assert {c["left"] for c in r["binding_conflicts"]} == {"R12"}
    assert r["blocked"] is True
    assert gap(r, "2026")["status"] == "COMPLETE"

def test_confirmed_coverage_immutable_after_correction():
    text = csv_text(*base_rows())
    a = store.save(text, run(text))
    corrected = csv_text(*base_rows()[:-1])
    b = store.save(corrected, run(corrected))
    assert a["id"] != b["id"]
    again = store.get(a["id"])
    assert again["result"]["cross_year"][0]["years"] == ["2025", "2026"]
    assert again["result"]["books"] == 23

# --- 重跑同一批不新增补录或册数 ---

def test_rerun_same_batch_adds_nothing():
    rows = [held(f"Q{i:02d}", str(i)) for i in range(1, 12)]
    rows.append(held("Q12", "2025:12/2026:1"))
    text = csv_text(*rows)
    before = len(store.history())
    a = store.save(text, run(text))
    b = store.save(text, run(text))
    assert a["id"] == b["id"]
    assert len(store.history()) == before + 1
    assert b["result"]["books"] == 12
    assert len(b["result"]["final"]) == 11
    assert b["result"]["final"] == a["result"]["final"]

# --- 证据导出保留依据 ---

def test_export_keeps_cross_year_basis():
    item = store.save(csv_text(*base_rows()), run(csv_text(*base_rows())))
    text = evidence_csv(item)
    assert "cross_year" in text and "2025:12" in text and "2026:1" in text
    assert "BR12" in text and item["digest"] in text

def test_export_lists_split_conflict():
    text = csv_text(*[held("A1", "12", binding="BX"), held("A2", "1", year="2026", binding="BX")])
    item = store.save(text, run(text))
    assert "CROSS_YEAR_SPLIT" in evidence_csv(item)
