import os, re, json, shutil
from pathlib import Path

V6_ROOT = Path(os.environ.get("V6_ROOT",".")).resolve()
V7_DIR  = Path(os.environ.get("V7_DIR","OrderFlowV7")).resolve()
REPORT_JSON = Path("output/qa/v7_isolation_report.json")
TARGET_BASE = V7_DIR/"third_party"/"v6_legacy"

def safe_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)

def rewrite_imports(p: Path):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    new = re.sub(r"\borderflow_v_6\b", "v6_legacy", txt)
    if new != txt:
        p.write_text(new, encoding="utf-8")

def main():
    if not REPORT_JSON.exists():
        raise SystemExit("report missing. run audit_isolation.py first.")
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    problems = report.get("problems",[])
    if not problems:
        print("[OK] no problems found."); return

    copied=set(); touched=0
    for item in problems:
        for det in item["details"]:
            if det["type"]=="import":
                mod = det["module"].split(".")[0]  # orderflow_v_6
                # 试图在 V6_ROOT 找这个包
                src_pkg = V6_ROOT/mod
                if src_pkg.exists():
                    dst_pkg = TARGET_BASE/mod.replace("orderflow_v_6","v6_legacy")
                    safe_copy(src_pkg, dst_pkg)
                    copied.add(str(src_pkg))
            elif det["type"]=="text_match":
                pass

    # 重写 V7 内部文件的 import
    for p in V7_DIR.rglob("*.py"):
        rewrite_imports(p); touched+=1

    print(f"[OK] copied deps: {len(copied)} ; rewritten py files: {touched}")
    print(f"[OK] legacy copied under: {TARGET_BASE}")

if __name__=="__main__":
    main()
