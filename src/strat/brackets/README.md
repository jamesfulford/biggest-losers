# brackets

Buy at fixed time, then place OCO brackets. Replace brackets at given times. Sell at fixed time.

## Example

Buy at 9:30. Wait for order to settle. Set OCO bracket, 10% take-profit, 25% stop-loss (think: should never happen).

At 10:00am (30m after market open), replace brackets with new set of percentages (take-profit is same, but stop-loss is now tighter at 0.5%)

At 3:59pm (1m before market close), stop brackets. Sell if still holding.

Here's how the brackets are specified:

```python
market_today = today_or_previous_trading_day(today())

brackets = [
    {
        "take_profit_percentage": 0.1,
        "stop_loss_percentage": 0.25,  # unusually low please
        "until": get_market_open_on_day(market_today) + timedelta(minutes=30),
    },
    {
        "take_profit_percentage": 0.1,
        "stop_loss_percentage": 0.005,
        "until": get_market_close_on_day(market_today) - timedelta(minutes=1),
    },
]
```
