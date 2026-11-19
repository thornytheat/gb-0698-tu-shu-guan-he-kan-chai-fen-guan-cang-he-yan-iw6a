from app.report import report
from app.coverage import pairs

def missing(covered,suspended,expected=12):
    return sorted(set(map(str,range(1,expected+1)))-set(covered)-set(suspended),key=int)

def apply(ctx):
    groups={}
    for r in ctx["expanded"]:
        for y,issue in pairs(r):groups.setdefault((r["journal_key"],y,r["canonical"]),[]).append((r,issue))
    out=[]
    for (issn,year,title),entries in groups.items():
        covered={i for r,i in entries if r["status"]=="held"};suspended={i for r,i in entries if r["status"]=="suspended"}
        cross=sorted({i for r,i in entries if r["status"]=="held" and r["year"]!=year},key=int)
        absent=missing(covered,suspended)
        out.append({"issn":issn,"title":title,"year":year,"missing":absent,"covered":sorted(covered),"suspended":sorted(suspended),"cross":cross,"status":"GAP" if absent else "COMPLETE"})
    ctx["gaps"]=out;return report(out,缺期=sum(len(r["missing"]) for r in out),年度=len(out))
