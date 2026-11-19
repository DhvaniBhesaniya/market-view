"""Evidence-based weekly mentor. No predictions, model calls, or invented trade data."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from market_view.config import IST

REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS trade_reviews (
  trade_id BIGINT PRIMARY KEY, reviewed_at TIMESTAMPTZ,
  risk_ok BOOLEAN, plan_ok BOOLEAN, selection_ok BOOLEAN, execution_ok BOOLEAN, note VARCHAR
);
"""
PLAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_actions (
  week_start DATE, action_index INTEGER, action_text VARCHAR, completed BOOLEAN, note VARCHAR,
  PRIMARY KEY(week_start, action_index)
);
CREATE TABLE IF NOT EXISTS weekly_action_events (
  ts TIMESTAMPTZ, week_start DATE, action_index INTEGER, completed BOOLEAN, note VARCHAR
);
"""


def save_plan(path: Path, day: date):
    if not path.exists():
        raise ValueError("No paper journal exists yet.")
    report = weekly_review(path, day)
    with duckdb.connect(str(path)) as c:
        c.execute(PLAN_SCHEMA)
        for index, text in enumerate(report["actions"]):
            c.execute("INSERT INTO weekly_actions VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                      [report["week_start"], index, text, False, ""])


def update_action(path: Path, day: date, index: int, completed: bool, note: str):
    if not 0 <= index <= 2 or len(note.strip()) < 10:
        raise ValueError("Select one of three actions and add an evidence note (at least 10 characters).")
    if not path.exists():
        raise ValueError("No paper journal exists yet.")
    monday = day-timedelta(days=day.weekday())
    with duckdb.connect(str(path)) as c:
        c.execute(PLAN_SCHEMA)
        if not c.execute("SELECT 1 FROM weekly_actions WHERE week_start=? AND action_index=?", [monday, index]).fetchone():
            raise ValueError("Save the review week's action plan before tracking it.")
        c.execute("BEGIN")
        c.execute("UPDATE weekly_actions SET completed=?, note=? WHERE week_start=? AND action_index=?", [completed, note.strip(), monday, index])
        c.execute("INSERT INTO weekly_action_events VALUES (?,?,?,?,?)", [datetime.now(IST), monday, index, completed, note.strip()])
        c.execute("COMMIT")


def annotate_trade(path: Path, trade_id: int, risk_ok: bool, plan_ok: bool, selection_ok: bool,
                   execution_ok: bool, note: str):
    if not path.exists():
        raise ValueError("No paper journal exists yet.")
    with duckdb.connect(str(path)) as c:
        if not c.execute("SELECT 1 FROM trades WHERE rowid=? AND mode='paper'", [trade_id]).fetchone():
            raise ValueError("Paper trade was not found.")
        c.execute(REVIEW_SCHEMA)
        c.execute("INSERT OR REPLACE INTO trade_reviews VALUES (?,?,?,?,?,?,?)",
                  [trade_id, datetime.now(IST), risk_ok, plan_ok, selection_ok, execution_ok, note])
        c.execute("UPDATE trades SET review_note=?, rule_followed=? WHERE rowid=? AND mode='paper'",
                  [note, plan_ok, trade_id])


def _summary(trades: pd.DataFrame) -> dict:
    n = len(trades)
    pnl = trades["net_pnl"].astype(float) if n else pd.Series(dtype=float)
    return {"trades": n, "net_pnl": round(float(pnl.sum()), 2),
            "win_rate_pct": round(float((pnl > 0).mean() * 100), 2) if n else None,
            "biggest_win": float(pnl[pnl > 0].max()) if (pnl > 0).any() else None,
            "biggest_loss": float(pnl[pnl < 0].min()) if (pnl < 0).any() else None,
            "charges": round(float(trades["charges"].sum()), 2) if n else 0,
            "avg_r": round(float(trades["r_multiple"].mean()), 3) if n else None,
            "avg_mae_pct": round(float(trades["mae_pct"].mean()), 2) if n else None,
            "avg_mfe_pct": round(float(trades["mfe_pct"].mean()), 2) if n else None,
            "avg_bars_held": round(float(trades["bars_held"].mean()), 1) if n else None,
            "pnl_basis": "Net P&L of complete trades closed this week, after recorded charges. Open positions and partial exits in unfinished trades are excluded; this is not total account weekly P&L."}


def weekly_review(path: Path, day: date) -> dict:
    monday = day - timedelta(days=day.weekday())
    start = datetime.combine(monday, time(), IST)
    end = start + timedelta(days=7)
    trades, prior, audits, signals, events = (pd.DataFrame() for _ in range(5))
    saved_actions, prior_actions, prior_audits = [], [], pd.DataFrame()
    if path.exists():
        with duckdb.connect(str(path)) as c:
            trades = c.execute("SELECT rowid AS trade_id, * FROM trades WHERE mode='paper' AND exit_time>=? AND exit_time<? ORDER BY exit_time", [start, end]).df()
            prior = c.execute("SELECT * FROM trades WHERE mode='paper' AND exit_time>=? AND exit_time<?", [start-timedelta(days=7), start]).df()
            tables = {row[0] for row in c.execute("SHOW TABLES").fetchall()}
            if "trade_reviews" in tables:
                audits = c.execute("SELECT r.* FROM trade_reviews r JOIN trades t ON r.trade_id=t.rowid WHERE t.mode='paper' AND t.exit_time>=? AND t.exit_time<?", [start, end]).df()
                prior_audits = c.execute("SELECT r.* FROM trade_reviews r JOIN trades t ON r.trade_id=t.rowid WHERE t.mode='paper' AND t.exit_time>=? AND t.exit_time<?", [start-timedelta(days=7), start]).df()
            if "weekly_actions" in tables:
                for week, rows in ((monday, saved_actions), (monday-timedelta(days=7), prior_actions)):
                    result = c.execute("SELECT action_index, action_text, completed, note FROM weekly_actions WHERE week_start=? ORDER BY action_index", [week]).fetchall()
                    rows.extend({"index": i, "text": text, "completed": done, "note": note} for i, text, done, note in result)
            signals = c.execute("SELECT stage, approved, reasons FROM signals WHERE mode='paper' AND ts>=? AND ts<?", [start, end]).df()
            events = c.execute("SELECT level, message FROM events WHERE mode='paper' AND ts>=? AND ts<?", [start, end]).df()
    summary = _summary(trades)
    previous = _summary(prior)
    n, reviewed = len(trades), len(audits)
    strengths, mistakes, patterns = [], [], []
    rejected = int((signals["approved"] == False).sum()) if len(signals) else 0  # noqa: E712
    if rejected:
        strengths.append(f"The system rejected {rejected} signal checks. A veto protects the account; it is not a trading mistake.")
    errors = int(events["level"].isin(["ERROR", "CRITICAL"]).sum()) if len(events) else 0
    if errors:
        mistakes.append(f"{errors} operational error events were recorded. Read their journal messages before resuming entries.")
    violations = {}
    for field, label in (("risk_ok", "risk management"), ("plan_ok", "plan discipline"),
                         ("selection_ok", "trade selection"), ("execution_ok", "execution")):
        bad = int((audits[field] == False).sum()) if reviewed else 0  # noqa: E712
        violations[field] = bad
        if bad:
            mistakes.append(f"{bad} reviewed trades failed {label}. Profit does not excuse this.")
            prior_bad = int((prior_audits[field] == False).sum()) if len(prior_audits) else 0  # noqa: E712
            if prior_bad:
                mistakes.append(f"Recurring {label} failure: {prior_bad} reviewed trades last week and {bad} this week. The prior issue has not been eliminated.")
        elif reviewed:
            strengths.append(f"All {reviewed} reviewed trades passed the recorded {label} check.")
    if n > reviewed:
        mistakes.append(f"{n-reviewed} of {n} closed trades have no complete process review. Their discipline is unknown.")
    groups = []
    if n:
        for strategy, df in trades.groupby("strategy_id"):
            groups.append({"strategy": strategy, **_summary(df)})
        for reason, count in trades["exit_reason"].value_counts().items():
            patterns.append(f"{count} trades exited for: {reason}.")
        patterns.append(f"Recorded charges were Rs {summary['charges']:.2f}. Compare net results, not gross profits.")
        patterns.append(f"Average result {summary['avg_r']:.2f}R; average holding time {summary['avg_bars_held']:.1f} bars. Average recorded adverse/favourable excursion: {summary['avg_mae_pct']:.2f}% / {summary['avg_mfe_pct']:.2f}%. Quote sampling can miss intraday extremes.")
        if n < 20:
            patterns.append(f"Only {n} closed trades: these observations do not establish a reliable winning or losing pattern.")
        beyond_stop = int((trades["r_multiple"] < -1).sum())
        if beyond_stop:
            patterns.append(f"{beyond_stop} losses exceeded 1R after costs. Check gaps, slippage and stop timing; a planned stop is not a guaranteed loss limit.")
    else:
        patterns.append("No paper trades closed this week. There is no win rate or trading edge to assess yet.")
    if previous["trades"]:
        patterns.append(f"Prior week: {previous['trades']} closed trades, net Rs {previous['net_pnl']:.2f}. This week's net change in closed-trade P&L is Rs {summary['net_pnl']-previous['net_pnl']:.2f}; sample sizes and positions differ.")
    strengths = strengths or ["No documented process strengths can be established yet."]
    mistakes = mistakes or ["No reviewed rule violations were recorded. This does not prove that every decision was correct."]
    actions = [
        "Review every closed trade against its entry signal, planned stop, size and exit rule; record the four process checks and evidence.",
        "Investigate every feed, reconciliation and execution error before allowing new entries; keep the configured risk limits unchanged.",
        "Keep one frozen strategy version for the next observation week; compare after-cost results and rejected signals with this week before proposing one new experiment.",
    ]
    if violations.get("risk_ok"):
        actions[0] = "For each failed risk check, identify the sizing or stop rule breached and reproduce the failure in a regression test before the next entry."
    if violations.get("plan_ok"):
        actions[2] = "For each plan violation, record the exact broken entry or exit condition and require that condition to pass before the next paper trade."
    if saved_actions:
        actions = [row["text"] for row in saved_actions]
    components, score = {}, None
    if n and reviewed == n:
        components = {"risk_management": round(float(audits.risk_ok.mean())*10, 1),
                      "discipline": round(float(audits.plan_ok.mean())*10, 1),
                      "selection_execution": round(float((audits.selection_ok.astype(float)+audits.execution_ok.astype(float)).mean())*5, 1),
                      "consistency": round(float(audits[["risk_ok", "plan_ok", "selection_ok", "execution_ok"]].all(axis=1).mean())*10, 1)}
        score = round(components["risk_management"]*.4 + components["discipline"]*.3 + components["selection_execution"]*.2 + components["consistency"]*.1, 1)
    records = []
    if n:
        review_map = {int(r["trade_id"]): r for r in audits.to_dict("records")} if reviewed else {}
        for row in trades.to_dict("records"):
            records.append({k: row[k] for k in ("trade_id", "symbol", "strategy_id", "entry_time", "exit_time", "net_pnl", "exit_reason")} | {"review": review_map.get(int(row["trade_id"]))})
    return {"week_start": monday.isoformat(), "week_end": (monday+timedelta(days=6)).isoformat(),
            "summary": summary, "strengths": strengths, "mistakes": mistakes, "patterns": patterns,
            "actions": actions, "by_strategy": groups, "trades": records,
            "plan_saved": bool(saved_actions),
            "previous": {"week_start": (monday-timedelta(days=7)).isoformat(), "summary": previous, "actions": prior_actions},
            "progress": (f"Prior saved plan: {sum(bool(a['completed']) for a in prior_actions)}/3 actions marked complete with operator notes. These are self-reports, not an independent audit." if prior_actions else "No saved prior action plan is available; follow-through cannot be assessed.") + " Emotions are not inferred from profit.",
            "rating": {"score": score, "components": components, "reviewed": reviewed, "total": n,
                       "basis": "Recorded process evidence; profit does not raise this score.",
                       "explanation": f"Based on {reviewed}/{n} complete human evidence reviews; a small sample is provisional. Risk 40%, discipline 30%, selection/execution 20%, consistency 10%." if score is not None else "Not rated: no closed trades or incomplete process evidence. A P&L-only score would be misleading."}}
