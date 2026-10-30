"""Checks of the order-execution engine on hand-made bars.

  python pipeline/test_engine.py

A bar is (bid open, high, low, close, ask open, high, low, close).
"""
from backtest import COMMISSION, run_bar, run_hours


def bar(o, h, l, c, spread=0.0):
    return (o, h, l, c, o + spread, h + spread, l + spread, c + spread)


def long_stop(price=1.10, stop=1.09, target=1.12):
    return dict(kind="stop", dir=1, price=price, stop=stop, target=target, risk=price - stop, signal_t=0, atr=0.01)


def short_stop(price=1.10, stop=1.11, target=1.08):
    return dict(kind="stop", dir=-1, price=price, stop=stop, target=target, risk=stop - price, signal_t=0, atr=0.01)


def main():
    # stop entry not reached: order expires
    assert run_bar(bar(1.095, 1.0995, 1.093, 1.097), long_stop(), None, None) == (None, None, None, False)
    # filled during the bar at the order price, nothing else touched
    pos, px, why, amb = run_bar(bar(1.095, 1.105, 1.093, 1.103), long_stop(), None, None)
    assert pos["entry"] == 1.10 and px is None and not amb
    # buy stops trigger on the ask: bid high 1.0995 + 0.6 pip spread reaches 1.10
    pos, *_ = run_bar(bar(1.095, 1.0995, 1.093, 1.097, spread=0.00006 * 10), long_stop(), None, None)
    assert pos is not None and pos["entry"] == 1.10
    # gap open above the stop entry: filled at the open, then the target in the same bar is unambiguous
    pos, px, why, amb = run_bar(bar(1.105, 1.125, 1.104, 1.12), long_stop(), None, None)
    assert pos["entry"] == 1.105 and (px, why, amb) == (1.12, "target", False)
    # entry and stop in one bar: unknown order -> ambiguous; worse way = stop, better way = still open
    b = bar(1.095, 1.101, 1.085, 1.09)
    assert run_bar(b, long_stop(), None, None)[3] is True
    assert run_bar(b, long_stop(), None, "cons")[1:3] == (1.09, "stop")
    assert run_bar(b, long_stop(), None, "opt")[1:3] == (None, None)
    # entry then target in one bar (no stop): the entry must come first, so it is a clean win
    assert run_bar(bar(1.095, 1.121, 1.094, 1.12), long_stop(), None, None)[1:4] == (1.12, "target", False)
    # held position: gap through the stop fills at the open, not at the stop
    held = dict(long_stop(), entry=1.10, settled="daily")
    assert run_bar(bar(1.08, 1.085, 1.075, 1.08), None, held, None)[1:3] == (1.08, "stop")
    # held position: stop and target in one bar -> ambiguous
    assert run_bar(bar(1.10, 1.125, 1.085, 1.10), None, held, "cons")[1:3] == (1.09, "stop")
    assert run_bar(bar(1.10, 1.125, 1.085, 1.10), None, held, "opt")[1:3] == (1.12, "target")
    # short: sell stop on the bid, stop-loss on the ask (a spread spike can stop it out)
    pos, px, why, _ = run_bar(bar(1.105, 1.106, 1.098, 1.10), short_stop(), None, None)
    assert pos["entry"] == 1.10 and px is None
    held_s = dict(short_stop(), entry=1.10, settled="daily")
    assert run_bar(bar(1.10, 1.1095, 1.099, 1.10, spread=0.001), None, held_s, None)[1:3] == (1.11, "stop")
    # buy limit: the stop after the fill in the same bar is unambiguous (price passes the limit first)
    lim = dict(kind="limit", dir=1, price=1.10, stop=1.094, target=1.112, risk=0.006, signal_t=0, atr=0.01)
    assert run_bar(bar(1.105, 1.106, 1.09, 1.092), lim, None, None)[1:4] == (1.094, "stop", False)
    # buy limit: target touched in the fill bar is ambiguous (the high may have come first)
    assert run_bar(bar(1.105, 1.113, 1.099, 1.11), lim, None, None)[3] is True
    assert run_bar(bar(1.105, 1.113, 1.099, 1.11), lim, None, "cons")[1:3] == (None, None)
    # next-open entry: risk and target are set from the actual fill
    nxt = dict(kind="open", dir=1, price=None, stop=1.09, target=None, risk=None, signal_t=0, atr=0.01)
    pos, *_ = run_bar(bar(1.10, 1.105, 1.095, 1.10), nxt, None, None)
    assert abs(pos["risk"] - 0.01) < 1e-12 and abs(pos["target"] - 1.12) < 1e-12
    # next-open entry that opens beyond the stop is not taken
    assert run_bar(bar(1.085, 1.09, 1.08, 1.085), nxt, None, None)[0] is None
    # hour-by-hour replay settles the order: entry first, then the stop
    hours = [bar(1.095, 1.101, 1.094, 1.10), bar(1.10, 1.10, 1.085, 1.087)]
    assert run_hours(hours, long_stop(), None, "cons")[1:3] == (1.09, "stop")
    # ...or the stop level first (before the fill), then the entry, and the trade survives the day
    hours = [bar(1.095, 1.096, 1.085, 1.0905), bar(1.0905, 1.101, 1.0905, 1.10)]
    pos, px, why, amb = run_hours(hours, long_stop(), None, "cons")
    assert pos["entry"] == 1.10 and px is None and not amb
    assert COMMISSION == 0.000035
    print("all engine checks passed")


if __name__ == "__main__":
    main()
