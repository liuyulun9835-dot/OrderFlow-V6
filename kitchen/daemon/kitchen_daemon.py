import time, subprocess, sys, os

INTERVAL_SEC = int(os.environ.get("KITCHEN_INTERVAL","600"))
CMDS = [
  [sys.executable,"-m","kitchen.align.align_ab_streams","--atas","data/raw/atas/latest.jsonl","--binance","data/raw/binance/latest.csv"],
  [sys.executable,"-m","kitchen.features.make_features_micro"],
  [sys.executable,"-m","kitchen.features.make_features_macro"],
  [sys.executable,"-m","kitchen.publish.make_manifest"],
  [sys.executable,"-m","kitchen.publish.make_signatures"],
  [sys.executable,"-m","kitchen.publish.publish_snapshot"]
]

if __name__=="__main__":
  while True:
    for c in CMDS:
      try:
        subprocess.check_call(c)
      except Exception as e:
        print("step failed:", c, e)
    time.sleep(INTERVAL_SEC)
