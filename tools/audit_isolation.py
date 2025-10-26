import os, re, json, sys, shutil, hashlib, ast
from pathlib import Path

V6_ROOT = Path(os.environ.get("V6_ROOT", Path.cwd()))
V7_DIR  = Path(os.environ.get("V7_DIR", "OrderFlowV7")).resolve()

REPORT_DIR = Path("output/qa"); REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = REPORT_DIR/"v7_isolation_report.json"
REPORT_MD   = REPORT_DIR/"v7_isolation_report.md"

PATTERNS = {
    "hard_v6_name": re.compile(r"OrderFlow[-_]?V6", re.I),
    "pkg_v6_name":  re.compile(r"\borderflow_v_6\b"),
    "parent_ref":   re.compile(r"\.\./"),
}
PY_EXT = (".py",".pyi")

def sha1(p: Path)->str:
    h=hashlib.sha1()
    with open(p,"rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]

def parse_imports(py: Path):
    try:
        text = py.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
    except Exception as e:
        return {"error": str(e), "imports": []}
    imps=[]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imps.append(a.name)
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            imps.append(mod)
    return {"imports": imps}

def scan_file(p: Path):
    text = p.read_text(encoding="utf-8", errors="ignore")
    hits={}
    for k,pat in PATTERNS.items():
        m = list(pat.finditer(text))
        if m: hits[k] = [ (mm.start(), text[max(0,mm.start()-40):mm.start()+80].replace("\n"," ")) for mm in m ]
    res={"file":str(p.relative_to(V6_ROOT)), "hits":hits}
    if p.suffix in PY_EXT:
        res.update(parse_imports(p))
    return res

def find_external_refs(res):
    """return paths/imports that suggest coupling to V6 or parent"""
    external=[]
    # hardcoded
    if res["hits"].get("hard_v6_name") or res["hits"].get("pkg_v6_name") or res["hits"].get("parent_ref"):
        external.append({"type":"text_match", "file":res["file"], "snips":res["hits"]})
    # imports
    for m in res.get("imports", []):
        if m.startswith("orderflow_v_6") or m.startswith("OrderFlow_V6"):
            external.append({"type":"import", "file":res["file"], "module": m})
    return external

def main():
    if not V7_DIR.exists():
        print(f"[ERR] V7 dir not found: {V7_DIR}"); sys.exit(2)

    files = [p for p in V7_DIR.rglob("*") if p.is_file() and not any(s in p.parts for s in (".git","__pycache__",".venv",".mypy_cache"))]
    report = {"v7_root": str(V7_DIR), "files_scanned": len(files), "problems": []}
    md_lines = ["# V7 隔离性审计报告", "", f"- 根目录: `{V7_DIR}`", f"- 扫描文件数: {len(files)}", ""]
    for p in files:
        res = scan_file(p)
        ex = find_external_refs(res)
        if ex:
            report["problems"].append({"file": res["file"], "details": ex})
            md_lines.append(f"## {res['file']}")
            for e in ex:
                if e["type"]=="import":
                    md_lines.append(f"- 依赖 V6 包: `{e['module']}`")
                else:
                    md_lines.append(f"- 文本耦合: {list(res['hits'].keys())}")
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_MD.write_text("\n".join(md_lines) or "# 无问题", encoding="utf-8")
    print(f"[OK] report: {REPORT_JSON} ; {REPORT_MD}")

if __name__=="__main__":
    main()
