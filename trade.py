"""매매 입력: python trade.py 팀 buy|sell 티커 수량 "이유" "청산조건"  (최근 종가로 체결)"""
import sys
import sim

sys.stdout.reconfigure(encoding="utf-8")


def main():
    if len(sys.argv) < 5:
        sys.exit('사용법: trade.py 팀 buy|sell 티커 수량 "이유" "청산조건"')
    team, side, ticker, qty = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    reason = sys.argv[5] if len(sys.argv) > 5 else ""
    exit_rule = sys.argv[6] if len(sys.argv) > 6 else ""
    if team not in sim.CFG["teams"] or side not in ("buy", "sell") or ticker not in sim.CFG["tickers"]:
        sys.exit("팀·방향·티커가 config.json 과 맞지 않아요.")
    quotes, fx = sim.latest_quotes([ticker])
    px, pdate = quotes[ticker]
    ledger = sim.load_ledger()
    gross, fee = sim.execute(ledger, team, side, ticker, qty, px, pdate, fx, reason, exit_rule)
    sim.save_ledger(ledger)
    print(f"{team} {side} {ticker} {qty}주 @ {px:,.2f} ({pdate}) = {gross:,}원, 수수료·세금 {fee:,}원")


if __name__ == "__main__":
    main()
