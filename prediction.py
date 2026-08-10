"""Buy-limit / sell-limit prediction from the last 5 OHLC candles.

Formula overview (see README section for the full derivation):

1. Recency-weighted pivot: each candle's typical price (H+L+2C)/4 is
   averaged with linear weights 1..5 so the newest candle counts most.
2. ATR(5): average true range over the 5 candles measures volatility.
3. Momentum: least-squares slope of the 5 closes, normalized by ATR(5)
   and clamped to [-1, 1], measures trend direction/strength.
4. The predicted next-candle range is the pivot +/- k*ATR, skewed
   wider on the side momentum favors.
5. Buy limit / sell limit sit just inside that predicted range (a
   fraction `beta` in from each edge) so pending orders fill on a
   retracement rather than chasing the extreme.
"""

REQUIRED_KEYS = ("open", "high", "low", "close")


def predict_levels(candles, k=0.5, alpha=0.5, beta=0.15):
    """Predict next-candle buy/sell limit levels from 5 OHLC candles.

    Args:
        candles: list of exactly 5 dicts with 'open','high','low','close',
            ordered oldest -> newest.
        k: volatility multiplier controlling how wide the predicted
            range is relative to ATR(5).
        alpha: momentum sensitivity (0 = symmetric range, 1 = fully
            skewed toward the trend).
        beta: how far inside the predicted range the limit orders sit,
            as a fraction of the range (0 = at the extreme, 0.5 = at
            the pivot).

    Returns:
        dict with pivot, atr, slope, momentum, predicted_high,
        predicted_low, buy_limit, sell_limit.
    """
    if len(candles) != 5:
        raise ValueError("predict_levels requires exactly 5 candles, oldest to newest")
    for c in candles:
        if not all(key in c for key in REQUIRED_KEYS):
            raise ValueError(f"each candle needs {REQUIRED_KEYS}")

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    # 1. Recency-weighted pivot
    weights = [1, 2, 3, 4, 5]
    typical = [(h + l + 2 * c) / 4 for h, l, c in zip(highs, lows, closes)]
    pivot = sum(w * tp for w, tp in zip(weights, typical)) / sum(weights)

    # 2. ATR(5)
    true_ranges = []
    for i, c in enumerate(candles):
        if i == 0:
            tr = c["high"] - c["low"]
        else:
            prev_close = candles[i - 1]["close"]
            tr = max(
                c["high"] - c["low"],
                abs(c["high"] - prev_close),
                abs(c["low"] - prev_close),
            )
        true_ranges.append(tr)
    atr = sum(true_ranges) / len(true_ranges)

    # 3. Momentum: least-squares slope of closes vs. index (1..5)
    n = len(closes)
    idx = list(range(1, n + 1))
    mean_i = sum(idx) / n
    mean_c = sum(closes) / n
    num = sum((i - mean_i) * (c - mean_c) for i, c in zip(idx, closes))
    den = sum((i - mean_i) ** 2 for i in idx)
    slope = num / den if den else 0.0
    momentum = 0.0 if atr == 0 else max(-1.0, min(1.0, slope / atr))

    # 4. Predicted next-candle range, skewed by momentum
    predicted_high = pivot + k * atr * (1 + alpha * max(momentum, 0))
    predicted_low = pivot - k * atr * (1 + alpha * max(-momentum, 0))
    candle_range = max(predicted_high - predicted_low, 1e-9)

    # 5. Limit orders sit inside the predicted range, not at its edge
    buy_limit = predicted_low + beta * candle_range
    sell_limit = predicted_high - beta * candle_range

    return {
        "pivot": pivot,
        "atr": atr,
        "slope": slope,
        "momentum": momentum,
        "predicted_high": predicted_high,
        "predicted_low": predicted_low,
        "buy_limit": buy_limit,
        "sell_limit": sell_limit,
    }
