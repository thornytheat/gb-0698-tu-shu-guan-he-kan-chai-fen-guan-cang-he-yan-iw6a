import re,unicodedata
from app.report import report,quarantine
from app.errors import BusinessError

def parse(text):
    """把期号表达解析为(年度或None,期号)段序列。

    支持单期"1"、范围"1-3"、列举"3/4"、增刊"S1"，以及跨年合刊
    "2025:12/2026:1"：每段显式标注年度，年度须连续递增。
    """
    text=unicodedata.normalize("NFKC",text).strip().upper()
    if re.fullmatch(r"S[1-9][0-9]?",text):return [(None,text)]
    if re.fullmatch(r"[0-9]+-[0-9]+",text):
        a,b=map(int,text.split("-"))
        if not 1<=a<=b<=24:raise BusinessError("ISSUE_RANGE","期号范围无效")
        return [(None,str(x)) for x in range(a,b+1)]
    if "/" in text or ":" in text:
        raw=text.split("/")
        if any(not s for s in raw):raise BusinessError("ISSUE_SYNTAX","期号表达无效")
        marked=[":" in s for s in raw]
        if any(marked) and not all(marked):raise BusinessError("CROSS_YEAR_FORM","跨年合刊须每期都标年度")
        segs=[]
        for s in raw:
            if ":" in s:
                y,_,n=s.partition(":")
                if not re.fullmatch(r"[0-9]{4}",y) or not 1900<=int(y)<=2100:raise BusinessError("CROSS_YEAR_FORM","跨年期段年度无效")
                if not re.fullmatch(r"[0-9]+",n) or not 1<=int(n)<=24:raise BusinessError("CROSS_YEAR_FORM","跨年期段期号无效")
                segs.append((y,str(int(n))))
            else:
                if not re.fullmatch(r"[0-9]+",s):raise BusinessError("ISSUE_SYNTAX","期号表达无效")
                n=int(s)
                if not 1<=n<=24:raise BusinessError("ISSUE_RANGE","期号范围无效")
                segs.append((None,str(n)))
        if all(marked):
            years=[int(y) for y,_ in segs]
            if any(b!=a+1 for a,b in zip(years,years[1:])):raise BusinessError("CROSS_YEAR_SEQUENCE","跨年年度须连续递增")
        else:
            segs=sorted(segs,key=lambda t:int(t[1]))
        if len(set(segs))!=len(segs):raise BusinessError("ISSUE_RANGE","期号范围无效")
        return segs
    if not re.fullmatch(r"[0-9]+",text):raise BusinessError("ISSUE_SYNTAX","期号表达无效")
    n=int(text)
    if not 1<=n<=24:raise BusinessError("ISSUE_RANGE","期号范围无效")
    return [(None,str(n))]

def expand(text):
    return [issue for _,issue in parse(text)]

def apply(ctx):
    out=[]
    for r in ctx["canonical"]:
        try:
            if not r["year"].isdigit() or not 1900<=int(r["year"])<=2100:raise BusinessError("YEAR","年份无效")
            if r["status"] not in {"held","suspended","missing"}:raise BusinessError("STATUS","馆藏状态无效")
            if r["status"]=="held" and not r["binding"]:raise BusinessError("BINDING_REQUIRED","在馆记录缺少装订号")
            segs=parse(r["issue"])
            years={y for y,_ in segs if y}
            if years and r["year"] not in years:raise BusinessError("CROSS_YEAR_ANCHOR","记录年度不在跨年覆盖范围内")
            x=dict(r);x["issues"]=[f"{y}:{i}" if y and y!=r["year"] else i for y,i in segs];out.append(x)
        except BusinessError as e:quarantine(ctx,r,e.code)
    ctx["expanded"]=out;return report(out,展开期次=sum(len(r["issues"]) for r in out),实体记录=len(out))
