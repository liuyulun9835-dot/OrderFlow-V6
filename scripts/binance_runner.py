import subprocess, time, datetime as dt, pathlib, sys, os

SYMBOL = os.environ.get("BINANCE_SYMBOL","BTCUSDT")     # fetch_binance_1m.py expects "BTC/USDT" or "BTCUSDT"? keep as in user's script
OUTDIR = pathlib.Path(os.environ.get("BINANCE_OUTDIR","data/raw/binance/BTCUSDT"))
SCRIPT = pathlib.Path("scripts/fetch_binance_1m.py")


def run_day(d):
    return subprocess.call([sys.executable, str(SCRIPT), "--symbol", SYMBOL, "--date", d.strftime("%Y-%m-%d"), "--out", str(OUTDIR)])


if __name__=="__main__":
    while True:
        utc_today = dt.datetime.utcnow().date()
        for d in [utc_today - dt.timedelta(days=1), utc_today]:
            run_day(d)
        time.sleep(15*60)
