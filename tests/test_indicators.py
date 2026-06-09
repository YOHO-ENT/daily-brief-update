from dailybrief.trading.indicators import detect_recent_cross, ema, macd, rsi, sma


def test_sma_and_ema_seed_with_sma():
    values = [1, 2, 3, 4, 5]
    assert sma(values, 3) == [2, 3, 4]
    assert ema(values, 3)[0] == 2


def test_rsi_and_macd_shapes():
    closes = [float(i) for i in range(1, 80)]
    assert rsi(closes, 14)[-1] > 99
    result = macd(closes)
    assert result["macd"]
    assert result["signal"]
    assert len(result["histogram"]) == len(result["signal"])


def test_detect_recent_cross():
    assert detect_recent_cross([1, 2, 3], [2, 2, 2], 3) == {"daysAgo": 0, "direction": "up"}
    assert detect_recent_cross([3, 2, 1], [2, 2, 2], 3) == {"daysAgo": 0, "direction": "down"}
