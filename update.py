"""최신 종가를 받아 평가금액을 다시 계산하고 data.json / dashboard.html 을 만든다."""
import sys
import json
import datetime as dt

import sim

sys.stdout.reconfigure(encoding="utf-8")
CFG = sim.CFG
INIT = CFG["initial_cash"]


def main():
    ledger = sim.load_ledger()
    tickers = sorted({t["ticker"] for t in ledger["trades"]})
    bench = CFG["benchmarks"]
    start = (dt.date.fromisoformat(CFG["start_date"]) - dt.timedelta(days=10)).isoformat()
    px = sim.download(tickers + list(bench.values()) + [CFG["fx_ticker"]], start).ffill()
    px = px[px.index >= CFG["start_date"]]
    # 시세를 일부라도 못 받으면 깨진 화면을 만들지 말고 멈춘다
    if px.empty or px.isna().any().any():
        bad = [c for c in px.columns if px[c].isna().any()]
        sys.exit(f"시세를 받지 못했어요: {bad or '전체'}")
    fxs = px[CFG["fx_ticker"]]

    dates = [d.date().isoformat() for d in px.index]
    out = {
        "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
        "dates": ["시작"] + dates,
        "teams": {}, "bench": {}, "trades": ledger["trades"],
        "names": {t: v["name"] for t, v in CFG["tickers"].items()},
        "config": {k: CFG[k] for k in ("initial_cash", "fees_note", "teams")},
        "learn": json.loads((sim.ROOT / "learn.json").read_text(encoding="utf-8")),
    }

    for team in CFG["teams"]:
        series, last_pos, last_cash = [INIT], {}, INIT
        for d in dates:
            pos, cash = sim.holdings_and_cash(ledger, team, upto=d)
            val = cash
            for tk, (q, _) in pos.items():
                p = px.loc[d, tk]
                mult = fxs.loc[d] if sim.market_of(tk) == "US" else 1
                val += q * p * mult
            series.append(round(float(val)))
            last_pos, last_cash = pos, cash
        rows = []
        for tk, (q, cost) in last_pos.items():
            p = float(px[tk].iloc[-1])
            mult = float(fxs.iloc[-1]) if sim.market_of(tk) == "US" else 1
            value = q * p * mult
            rows.append({"ticker": tk, "name": CFG["tickers"][tk]["name"], "qty": q,
                         "avg_krw": cost / q, "price_krw": p * mult, "value": value,
                         "pnl_pct": (value / cost - 1) * 100})
        out["teams"][team] = {"nav": series, "cash": last_cash, "holdings": rows}

    for name, tk in bench.items():
        s = px[tk]
        out["bench"][name] = [INIT] + [round(float(INIT * v / s.iloc[0])) for v in s]

    (sim.ROOT / "data.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    tpl = (sim.ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*DATA*/null", json.dumps(out, ensure_ascii=False))
    (sim.ROOT / "dashboard.html").write_text(html, encoding="utf-8")

    print(f"기준일 {dates[-1]} (미국은 직전 거래일 종가)")
    for team, v in out["teams"].items():
        nav = v["nav"][-1]
        print(f"  {team}: {nav:,}원 ({(nav / INIT - 1) * 100:+.2f}%)")
    for name, s in out["bench"].items():
        print(f"  {name}: {(s[-1] / INIT - 1) * 100:+.2f}%")


if __name__ == "__main__":
    main()
