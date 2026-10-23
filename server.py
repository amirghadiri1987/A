# server.py
import sqlite3, time
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH    = "signals.db"
PASSPHRASE = "GCI_SECRET_2026"

def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker       TEXT NOT NULL,
                bar_time_utc TEXT NOT NULL,
                detected_at  TEXT,
                bS  INTEGER DEFAULT 0, buS INTEGER DEFAULT 0,
                bH  INTEGER DEFAULT 0, buH INTEGER DEFAULT 0,
                bA  INTEGER DEFAULT 0, buA INTEGER DEFAULT 0,
                comment      TEXT,
                processed    INTEGER DEFAULT 0,
                created_at   REAL,
                UNIQUE(ticker, bar_time_utc)
            )
        """)
        c.commit()
init_db()

def iso_to_mdy(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return f"{dt.month}/{dt.day}/{dt.year} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return ""

@app.post("/push")
async def push(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "invalid json")

    if data.get("passphrase") != PASSPHRASE:
        raise HTTPException(401, "unauthorized")

    ticker  = str(data.get("ticker", "")).strip()
    bar_utc = str(data.get("bar_time_utc", "")).strip()
    if not ticker or not bar_utc:
        raise HTTPException(400, "missing ticker or bar_time_utc")

    def bi(v):
        if isinstance(v, bool): return int(v)
        if isinstance(v, (int, float)): return 1 if v else 0
        if isinstance(v, str): return 1 if v.lower() in ("1","true","yes") else 0
        return 0

    bS  = bi(data.get("bS"));  buS = bi(data.get("buS"))
    bH  = bi(data.get("bH"));  buH = bi(data.get("buH"))
    bA  = bi(data.get("bA"));  buA = bi(data.get("buA"))

    bear, bull = [], []
    if bS: bear.append("S")
    if bH: bear.append("H")
    if bA: bear.append("A")
    if buS: bull.append("S")
    if buH: bull.append("H")
    if buA: bull.append("A")

    if bear and bull:
        return JSONResponse({"status": "conflict"}, 200)
    if not bear and not bull:
        return JSONResponse({"status": "no_signal"}, 200)

    comment = (",".join(bear) + " Bearish") if bear else (",".join(bull) + " Bullish")

    with sqlite3.connect(DB_PATH) as c:
        try:
            c.execute("""
                INSERT INTO signals
                (ticker, bar_time_utc, detected_at,
                 bS, buS, bH, buH, bA, buA, comment, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (ticker, bar_utc, data.get("detected_at",""),
                  bS, buS, bH, buH, bA, buA, comment, time.time()))
            c.commit()
            inserted = True
        except sqlite3.IntegrityError:
            inserted = False

    return JSONResponse({
        "status": "accepted" if inserted else "duplicate",
        "ticker": ticker,
        "bar_time_mdy": iso_to_mdy(bar_utc),
        "comment": comment,
    })

@app.get("/poll")
async def poll(ticker: str = "", mark: int = 0, format: str = "plain"):
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        q = "SELECT * FROM signals WHERE processed=0"
        params = []
        if ticker:
            q += " AND ticker=?"
            params.append(ticker)
        q += " ORDER BY id ASC LIMIT 50"
        rows = [dict(r) for r in c.execute(q, params).fetchall()]

        if rows and mark:
            ids = [r["id"] for r in rows]
            ph = ",".join("?" * len(ids))
            c.execute(f"UPDATE signals SET processed=1 WHERE id IN ({ph})", ids)
            c.commit()

    if format == "plain":
        lines = [
            f"{r['id']}|{r['ticker']}|{r['bar_time_utc']}|{r['comment']}|{r['bS']}|{r['buS']}|{r['bH']}|{r['buH']}|{r['bA']}|{r['buA']}"
            for r in rows
        ]
        return PlainTextResponse("\n".join(lines) if lines else "")

    for r in rows:
        r["bar_time"] = iso_to_mdy(r["bar_time_utc"])
    return {"count": len(rows), "signals": rows}

@app.get("/ack")
async def ack(ids: str = ""):
    if not ids:
        return {"acked": 0}
    try:
        idList = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    except Exception:
        return {"acked": 0}
    if not idList:
        return {"acked": 0}
    with sqlite3.connect(DB_PATH) as c:
        ph = ",".join("?" * len(idList))
        c.execute(f"UPDATE signals SET processed=1 WHERE id IN ({ph})", idList)
        c.commit()
    return {"acked": len(idList)}

@app.get("/unacked")
async def unacked():
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT id, ticker, bar_time_utc, comment FROM signals WHERE processed=0"
        ).fetchall()]
    return {"count": len(rows), "signals": rows}

@app.get("/health")
async def health():
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}

@app.delete("/reset")
async def reset():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM signals")
        c.commit()
    return {"status": "cleared"}
