"""Resumable runner: python3 run.py <run ids...>   e.g. A-on A-off D-off.  Skips runs already done."""
import json, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(__file__))
from core import S, Workspace, score, Out
from strategies import STRATEGIES, Ctx

RUNS = f"{S}/exp/runs"
MINUTES = float(os.environ.get("RUN_MINUTES", 12))
for rid in sys.argv[1:]:
    d = f"{RUNS}/{rid}"
    if os.path.exists(f"{d}/result.json") and not os.environ.get("FORCE"): print(f"{rid}: already done", flush=True); continue
    strat, think = rid.split("-")
    ws = Workspace(d)
    open(ws.game, "w").close(); open(ws.notes, "w").close()
    c = Ctx(ws, think, time.time() + MINUTES * 60)
    t, err = time.time(), None
    try: STRATEGIES[strat](c)
    except Out: c.notes.append("hit the time limit")
    except Exception as e: err = traceback.format_exc(); print(err, flush=True)
    secs = round(time.time() - t)
    sc = score(ws.game)
    n_chats = sum(1 for e in c.log if "output" in e or "steps" in e)
    res = {"run": rid, "secs": secs, "model_calls": n_chats, "notes": c.notes, "error": err, "finished_tool": ws.finished, **sc}
    json.dump(c.log, open(f"{d}/log.json", "w"), indent=1)
    json.dump(res, open(f"{d}/result.json", "w"), indent=1)
    print(f"{rid}: {sc['points']}/5 pts {{{', '.join(k for k in ['compiles','runs','board','clicks_work','computer_moves'] if sc[k])}}} "
          f"ts_errors={sc['ts_errors']} lines={sc['lines']} minimax={sc['has_minimax']} calls={n_chats} {secs}s notes={c.notes}", flush=True)
print("ALL DONE", flush=True)
