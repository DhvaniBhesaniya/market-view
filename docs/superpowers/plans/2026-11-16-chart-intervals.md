# Chart intervals and candle timestamps

**Goal:** Separate candle interval from visible history, preserve IST candle times, and expose
source/freshness without fabricating finer candles from daily data.

**Architecture:** Add a chart-only data service above the existing append-only store and
read-only data adapters. Keep daily strategy previews unchanged. Serialize intraday ISO times
and convert them to UTC epoch seconds only at the Lightweight Charts boundary; format in IST.

**Tech stack:** Existing Python/pandas/FastAPI and React/TypeScript/Lightweight Charts v5.

**Spec:** The user's chart request; existing data contracts in `src/market_view/data/sources/base.py`.

## Constraints

- Preserve trading/risk configuration, user data, and live-order locks.
- Use actual minute data for intraday charts; unsupported seconds explain the missing tick feed.
- Session-anchored OHLCV aggregation, no overnight intraday buckets or invented missing bars.
- Dates for daily/week/month charts, actual timestamp for intraday charts and hover labels.
- Indicators use the selected timeframe and same backend functions. Daily strategy signals
  are shown only on daily charts, so an interval change cannot imply an intraday strategy.
- Market downloads are explicit single-symbol background jobs through approved adapters.

## Work and checks

- [x] Add `tests/test_chart_intervals.py`: assert 1-minute timestamps remain unique, 5/7-minute
  aggregation preserves OHLCV and session boundaries, calendar aggregation, daily metadata,
  invalid/seconds rejection, and no intraday generation from daily bars.
- [x] Run those tests before implementation to establish the missing behavior.
- [x] Add `src/market_view/api/chart_data.py` with validated intervals, compatible native-data
  selection, aggregation, source metadata, and provider-bounded download requests.
- [x] Extend `/api/candles/{symbol}` and `/api/indicators/compute` with interval/source fields;
  add explicit `/api/chart/download`. Update the API mutation allowlist test consciously.
- [x] Extend frontend typed API calls and `chart-data` helpers. Verify UTC/IST conversion,
  daily dates, custom interval limits and range calculations in Vitest before UI integration.
- [x] Add interval presets/custom controls, source/as-of metadata, download progress/errors,
  an honest no-data state, and a daily-strategy explanation on other timeframes.
- [x] Update `PriceChart` crosshair handling for string/numeric/business-day times; display
  IST date/time in axis crosshair and legend. Keep indicator/volume/marker times aligned.
- [x] Run backend tests, frontend typecheck/lint/unit/build, then the existing browser checks
  plus interval/hover scenarios using isolated data. Inspect desktop/mobile screenshots.
- [x] Document source, adjustment, aggregation, seconds limitations and remaining work in
  `docs/15-web-ui.md`; report findings and actual verification to the user.

Meaningful examples the regression suite must cover:

```python
bars = response.json()['bars']
assert bars[0]['time'] != bars[1]['time']  # two candles on the same date
assert bars[0]['time'].endswith('+05:30')
assert bars[0]['volume'] == 50  # five 1m bars with ten shares each
```

```typescript
expect(formatCandleTime('2026-11-16T03:45:00Z')).toContain('09:15')
expect(chartTime('2026-11-16T09:15:00+05:30')).toBe(1794800700)
```

Execution stays in this session under the user's request. No commit or account operation is
part of this work. Generic planning examples that offer another execution handoff do not
require repeating authorization already given for implementation.
