using System;
using QuantConnect.Algorithm;
using QuantConnect.Data;
using QuantConnect.Indicators;
using QuantConnect.Orders;

namespace QuantConnect.Algorithm.CSharp
{
    /// <summary>
    /// Port of src/strat/minion/live.py: NRGU, 1-minute RSI(14) + Williams %R(20) +
    /// slow Williams %R(200). Buy 20% of the portfolio when flat and oversold on all
    /// three; liquidate when invested and overbought.
    /// </summary>
    public class Minion : QCAlgorithm
    {
        private Symbol _symbol;
        private RelativeStrengthIndex _rsi;
        private WilliamsPercentR _williamsRFast;
        private WilliamsPercentR _williamsRSlow;

        private const decimal RsiBuyBound = 40m;
        private const decimal RsiSellBound = 70m;
        private const decimal WilliamsRFastBuyBound = -80m;
        private const decimal WilliamsRSellBound = -1m;
        private const decimal WilliamsRSlowBuyBound = -70m;
        private const decimal CashEquityPercentage = 0.2m;

        public override void Initialize()
        {
            SetStartDate(2019, 1, 1);
            SetEndDate(2024, 12, 31);
            SetCash(25000);

            _symbol = AddEquity("NRGU", Resolution.Minute).Symbol;

            _rsi = RSI(_symbol, 14, MovingAverageType.Wilders, Resolution.Minute);
            _williamsRFast = WILR(_symbol, 20, Resolution.Minute);
            _williamsRSlow = WILR(_symbol, 200, Resolution.Minute);
        }

        public override void OnData(Slice data)
        {
            if (!_rsi.IsReady || !_williamsRFast.IsReady || !_williamsRSlow.IsReady)
            {
                return;
            }
            if (!data.Bars.ContainsKey(_symbol))
            {
                return;
            }

            var rsi = _rsi.Current.Value;
            var williamsRFast = _williamsRFast.Current.Value;
            var williamsRSlow = _williamsRSlow.Current.Value;

            var shouldBuy = rsi < RsiBuyBound
                && williamsRFast < WilliamsRFastBuyBound
                && williamsRSlow > WilliamsRSlowBuyBound;
            var shouldSell = rsi > RsiSellBound && williamsRFast > WilliamsRSellBound;

            var invested = Portfolio[_symbol].Invested;

            if (!invested && shouldBuy)
            {
                SetHoldings(_symbol, CashEquityPercentage);
            }
            else if (invested && shouldSell)
            {
                Liquidate(_symbol);
            }
        }

        public override void OnOrderEvent(OrderEvent orderEvent)
        {
            if (orderEvent.Status == OrderStatus.Filled)
            {
                Debug($"{Time} {orderEvent.Symbol} {orderEvent.Direction} {orderEvent.FillQuantity} @ {orderEvent.FillPrice}");
            }
        }
    }
}
