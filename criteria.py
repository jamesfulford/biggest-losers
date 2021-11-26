def is_warrant(ticker):
    return (ticker.upper().endswith("W") or ".WS" in ticker.upper())
