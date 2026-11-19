from app.report import report
from app.coverage import pairs

def collisions(rows):
    owners={};conflicts=[]
    for r in rows:
        if r["status"]!="held":continue
        for y,issue in pairs(r):
            key=(r["journal_key"],y,issue,r["copy"])
            previous=owners.get(key)
            if previous is None:owners[key]=r;continue
            if previous["binding"]!=r["binding"]:conflicts.append({"issue":issue,"year":y,"copy":r["copy"],"left":previous["record_id"],"right":r["record_id"],"reason":"BINDING_CONFLICT"})
    return conflicts

def splits(rows):
    """同一刊同一复本同一装订号被不同年度分记：疑似一册重复登记。"""
    seen={};out=[]
    for r in rows:
        if r["status"]!="held":continue
        key=(r["journal_key"],r["copy"],r["binding"])
        for prev in seen.get(key,[]):
            if prev["year"]!=r["year"]:out.append({"binding":r["binding"],"copy":r["copy"],"left":prev["record_id"],"right":r["record_id"],"left_year":prev["year"],"right_year":r["year"],"reason":"CROSS_YEAR_SPLIT"})
        seen.setdefault(key,[]).append(r)
    return out

def cross_year(rows):
    """跨年归集：每册列出覆盖的年度与期次，实体册只在归集年度计一次。"""
    out=[]
    for r in rows:
        covered=pairs(r)
        years=sorted({y for y,_ in covered})
        if len(years)<2:continue
        out.append({"record_id":r["record_id"],"line":r.get("line",""),"journal_key":r["journal_key"],"title":r.get("canonical",""),"copy":r["copy"],"binding":r["binding"],"anchor_year":r["year"],"years":years,"coverage":[{"year":y,"issue":i} for y,i in covered],"coverage_text":"/".join(f"{y}:{i}" for y,i in covered),"physical_books":1,"covered_issues":len(covered)})
    return out

def apply(ctx):
    conflict=collisions(ctx["expanded"]);ctx["binding_conflicts"]=conflict
    split=splits(ctx["expanded"]);ctx["split_conflicts"]=split
    out=[dict(r,physical_books=1,covered_issues=len(r["issues"])) for r in ctx["expanded"] if r["status"]=="held"]
    ctx["held"]=out;ctx["cross_year"]=cross_year(out)
    return report(out,合刊=sum(len(r["issues"])>1 for r in out),跨年合刊=len(ctx["cross_year"]),装订冲突=len(conflict),跨年分册疑似=len(split))
