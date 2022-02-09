from datetime import datetime
import quantstats
from src.broker.alpaca import _get_alpaca
import pandas as pd


# TODO: support TD Ameritrade
# to do this for TD, best we could do is take the order history,
# calculate gains/losses from those sales,
# and with any overnight positions calculate
# estimate each position's value at close each day.
r = _get_alpaca("/v2/account/portfolio/history")


# scroll to start of non-blank days
change_starts_index = 0
for i in range(len(r["profit_loss_pct"])):
    v = r["profit_loss_pct"][i]
    if v != 0:
        change_starts_index = i
        break

rois = r["profit_loss_pct"][change_starts_index:]
dates = [pd.to_datetime(datetime.fromtimestamp(ts).date())
         for ts in r["timestamp"][change_starts_index:]]

s = pd.Series(rois, dates)
print(s)

quantstats.reports.basic(s)
