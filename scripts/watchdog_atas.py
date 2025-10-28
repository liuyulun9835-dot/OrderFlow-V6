import time, pathlib, datetime as dt, os

HB = pathlib.Path("data/raw/atas/.heartbeat")
THRESH = int(os.environ.get("ATAS_HEARTBEAT_MAX_GAP_SEC","180"))

if __name__=="__main__":
  while True:
    ok = HB.exists()
    if ok:
      try:
        ts = dt.datetime.fromisoformat(HB.read_text().strip())
        age = (dt.datetime.utcnow()-ts.replace(tzinfo=None)).total_seconds()
        if age > THRESH:
          print("ATAS heartbeat stale:", age, "sec")  # TODO: alert/restart policy
      except Exception as e:
        print("read heartbeat failed:", e)
    else:
      print("heartbeat file missing")
    time.sleep(30)
