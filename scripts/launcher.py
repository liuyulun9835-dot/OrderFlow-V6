import subprocess, sys, time, os

procs=[]


def spawn(pyfile,*args):
    return subprocess.Popen([sys.executable, pyfile, *args])


if __name__=="__main__":
    procs.append(spawn("scripts/watchdog_atas.py"))
    procs.append(spawn("scripts/binance_runner.py"))
    # optional: kitchen daemon (commented by default)
    # procs.append(spawn("-m","kitchen.daemon.kitchen_daemon"))
    try:
        while True:
            for i,p in enumerate(procs):
                if p.poll() is not None:
                    # restart simple
                    args = p.args[1:]
                    procs[i] = subprocess.Popen([sys.executable, *args])
            time.sleep(5)
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
