import csv,io,json

def evidence_csv(run):
    out=io.StringIO();writer=csv.writer(out)
    result=run["result"]
    writer.writerow(["run_id","sha256","rule_version","kind","line","reason","evidence"])
    writer.writerow([run["id"],run["digest"],run["rule_version"],"manifest","","",json.dumps({"balance":result["balance"],"decision":run["decision"],"revision":run["revision"],"blocked":result.get("blocked",False),"cross_year":len(result.get("cross_year",[]))},ensure_ascii=False)])
    for row in result.get("cross_year",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"cross_year",row.get("line",""),"跨年合刊",json.dumps(row,ensure_ascii=False)])
    for row in result.get("final",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"result",row.get("line",""),row.get("status",""),json.dumps(row,ensure_ascii=False)])
    for row in result.get("binding_conflicts",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"conflict","",row["reason"],json.dumps(row,ensure_ascii=False)])
    for row in result.get("split_conflicts",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"conflict","",row["reason"],json.dumps(row,ensure_ascii=False)])
    for row in result.get("quarantine",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"quarantine",row.get("line",""),row["reason"],json.dumps(row,ensure_ascii=False)])
    return "\ufeff"+out.getvalue()
