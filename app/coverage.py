def pairs(record):
    """展开记录实际覆盖的(年度,期次)。

    期号段可带显式年度前缀(跨年合刊,如"2026:1")；无前缀时归记录自身年度。
    """
    out = []
    for entry in record["issues"]:
        year, sep, issue = entry.partition(":")
        out.append((year, issue) if sep else (record["year"], entry))
    return out
