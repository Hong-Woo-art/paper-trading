"""모의투자 공용 모듈: 설정·원장·가격 조회·체결."""
import json
import datetime as dt
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
LEDGER_PATH = ROOT / "ledger.json"


def load_ledger():
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {"trades": []}


def save_ledger(ledger):
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def download(tickers, start):
    """일별 종가 표 (날짜 x 티커). 휴장일 공백은 직전 값으로 채움."""
    tickers = sorted(set(tickers))
    d = yf.download(tickers, start=start, auto_adjust=False, progress=False, threads=False)["Close"]
    if isinstance(d, pd.Series):
        d = d.to_frame(tickers[0])
    d.index = pd.to_datetime(d.index).tz_localize(None)
    return d


def market_of(ticker):
    return CFG["tickers"][ticker]["market"]


def latest_quotes(tickers):
    """티커별 (마지막 종가, 그 날짜)와 환율을 돌려준다."""
    start = (dt.date.today() - dt.timedelta(days=12)).isoformat()
    d = download(list(tickers) + [CFG["fx_ticker"]], start)
    fx = float(d[CFG["fx_ticker"]].dropna().iloc[-1])
    out = {}
    for t in tickers:
        s = d[t].dropna()
        out[t] = (float(s.iloc[-1]), s.index[-1].date().isoformat())
    return out, fx


def holdings_and_cash(ledger, team, upto=None):
    """원장을 처음부터 재생해 보유수량·평균단가(원)·현금을 구한다."""
    cash = CFG["initial_cash"]
    pos = {}  # ticker -> [qty, cost_krw_total]
    for tr in ledger["trades"]:
        if tr["team"] != team or (upto and tr["date"] > upto):
            continue
        q, c = pos.get(tr["ticker"], [0, 0.0])
        if tr["side"] == "buy":
            cash -= tr["krw_gross"] + tr["fee"]
            pos[tr["ticker"]] = [q + tr["qty"], c + tr["krw_gross"] + tr["fee"]]
        else:
            cash += tr["krw_gross"] - tr["fee"]
            avg = c / q if q else 0
            pos[tr["ticker"]] = [q - tr["qty"], avg * (q - tr["qty"])]
    pos = {t: v for t, v in pos.items() if v[0] > 0}
    return pos, cash


def execute(ledger, team, side, ticker, qty, price, price_date, fx, reason="", exit_rule=""):
    mk = market_of(ticker)
    krw_px = price * (fx if mk == "US" else 1)
    gross = round(krw_px * qty)
    fee = round(gross * CFG["fees"][mk][side])
    pos, cash = holdings_and_cash(ledger, team)
    if side == "buy" and gross + fee > cash:
        raise ValueError(f"{team}: 현금 부족 (필요 {gross + fee:,} / 보유 {cash:,.0f})")
    if side == "sell" and pos.get(ticker, [0])[0] < qty:
        raise ValueError(f"{team}: {ticker} 보유수량 부족")
    ledger["trades"].append({
        "date": price_date, "team": team, "side": side, "ticker": ticker, "qty": qty,
        "price_local": round(price, 4), "fx": round(fx, 2) if mk == "US" else 1,
        "krw_gross": gross, "fee": fee, "reason": reason, "exit_rule": exit_rule,
    })
    return gross, fee
