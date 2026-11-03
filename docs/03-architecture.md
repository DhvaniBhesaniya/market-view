# 03 — Architecture

## 1. Big picture

```
                     ┌───────────────────────────────────────────────┐
                     │           AI RESEARCH LAYER (advisory)        │
                     │  regime model · signal ranker · news/sentiment│
                     │  LLM research assistant · journal analyst     │
                     └───────────────┬───────────────────────────────┘
                                     │ scores / context / hypotheses (never orders)
                                     ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Groww API    │──▶│ DATA LAYER   │──▶│ INDICATORS / │──▶│ STRATEGY     │
│ yfinance/NSE │   │ download,    │   │ FEATURES     │   │ ENGINE       │
│ news, macro  │   │ normalize,   │   └──────────────┘   │ emits Signal │
└──────────────┘   │ store        │                      └──────┬───────┘
                   └──────┬───────┘                             │
                          │                                     ▼
                   ┌──────▼───────┐                      ┌──────────────┐
                   │ BACKTEST +   │                      │ RISK ENGINE  │◀── kill switch
                   │ VALIDATION   │                      │ approve /    │
                   └──────────────┘                      │ resize/reject│
                                                         └──────┬───────┘
                                                                ▼
                                                         ┌──────────────┐
                                                         │ EXECUTION    │
                                                         │ order FSM,   │
                                                         │ reconcile    │
                                                         └──────┬───────┘
                                                                ▼
                                                 ┌──────────────────────────┐
                                                 │ Broker interface         │
                                                 │  PaperBroker | GrowwBroker│
                                                 └──────────────┬───────────┘
                                                                ▼
                                                         ┌──────────────┐
                                                         │ JOURNAL +    │──▶ AI journal analysis
                                                         │ PORTFOLIO    │    → new hypotheses
                                                         └──────────────┘
```

**The key property:** the *same* strategy code and risk engine run in backtest, paper and live modes. Only the data source and the `Broker` implementation change.

| Mode | Data source | Broker | Clock |
|---|---|---|---|
| Backtest | Stored history | `SimBroker` (inside the backtester) | Simulated |
| Replay | Recorded live ticks/candles | `PaperBroker` | Simulated, real-day replay |
| Paper | Live Groww WebSocket | `PaperBroker` | Real |
| Live | Live Groww WebSocket | `GrowwBroker` | Real |

## 2. Modules (modular monolith, `src/market_view/`)

| Module | Responsibility | Depends on |
|---|---|---|
| `data` | Download history (Groww/yfinance/bhavcopy), live feed client, normalization to `Candle`, storage, corporate actions, NSE calendar | — |
| `indicators` | Pure functions: EMA, RSI, ATR, VWAP, ADX, Bollinger, volume ratio … | `data` models |
| `strategies` | `Strategy` base class plus implementations; **pure**, no I/O | `indicators` |
| `backtest` | Event-driven engine, Indian cost model, slippage model, metrics, reports | `strategies`, `risk` |
| `validation` | Walk-forward, Monte Carlo, parameter sensitivity, benchmark comparison | `backtest` |
| `risk` | Pre-trade checks, position sizing, portfolio limits, drawdown breaker, kill switch | models only |
| `broker` | `Broker` ABC, `PaperBroker`, `GrowwBroker` | `data` |
| `execution` | Order state machine, retries, idempotency, reconciliation, broker-side stop placement | `broker`, `risk` |
| `portfolio` | Positions, cash, P&L, exposure | — |
| `journal` | Persist every signal/order/fill/trade with context; MAE/MFE; tax P&L export | `portfolio` |
| `market_context` | Regime classification, macro series, FII/DII, news ingestion, sentiment | `data` |
| `ai` | LLM client, prompts, research assistant, journal analyst, ML models (train/predict) | `journal`, `market_context` |
| `api` | FastAPI endpoints for the UI | all (read-mostly) |
| `ops` | Scheduler, health checks, notifications (Telegram), metrics | all |

**Dependency rule:** `strategies` never import `broker` or `execution`, and `ai` never imports `execution` or `broker`. A test enforces this (for example with `import-linter`).

## 3. Core data contracts

```python
class Candle(BaseModel):
    symbol: str; exchange: Literal["NSE","BSE"]; interval: str   # "1d","1h","15m"
    ts: datetime          # bar OPEN time, tz=Asia/Kolkata
    open: float; high: float; low: float; close: float; volume: int
    oi: int | None = None

class Signal(BaseModel):
    strategy_id: str      # "trend_v1"
    symbol: str
    side: Literal["BUY","SELL"]
    entry: Decimal; stop: Decimal; target: Decimal | None
    confidence: float     # rule score or ML probability
    reasons: list[str]    # ["20EMA>50EMA", "vol>1.5x"]
    context: dict         # regime, sentiment, indicator snapshot
    created_at: datetime  # bar CLOSE time it was computed on

class RiskDecision(BaseModel):
    approved: bool; qty: int; reasons: list[str]   # why rejected/resized

class Order(BaseModel):
    client_order_id: str  # our idempotency key
    broker_order_id: str | None
    symbol: str; side: str; qty: int; type: Literal["MARKET","LIMIT","SL","SL-M"]
    price: Decimal | None; trigger: Decimal | None; product: Literal["CNC","MIS"]
    status: OrderStatus   # see FSM below
```

### Strategy interface

```python
class Strategy(ABC):
    id: str; version: int; params: dict
    timeframe: str; universe: list[str]
    @abstractmethod
    def on_bar(self, history: pd.DataFrame, ctx: MarketContext) -> list[Signal]: ...
    @abstractmethod
    def exit_rules(self, position: Position, history: pd.DataFrame) -> ExitDecision | None: ...
```

### Broker interface

```python
class Broker(ABC):
    def place_order(self, order: Order) -> str: ...
    def modify_order(self, broker_order_id: str, **changes) -> None: ...
    def cancel_order(self, broker_order_id: str) -> None: ...
    def order_status(self, broker_order_id: str) -> OrderStatus: ...
    def positions(self) -> list[Position]: ...
    def holdings(self) -> list[Holding]: ...
    def funds(self) -> Funds: ...
    def place_stop(self, position: Position, stop: Decimal, target: Decimal | None) -> str: ...  # GTT/OCO
```

## 4. Order state machine (execution)

```
 NEW ──risk ok──▶ SUBMITTING ──ack──▶ OPEN ──fill──▶ COMPLETE ──▶ place broker-side stop
  │                  │                 │  └─partial─▶ PARTIAL ──fill──▶ COMPLETE
  └─risk reject─▶ REJECTED_RISK        │                └─timeout─▶ CANCEL_REQUESTED
                     └─error/timeout─▶ UNKNOWN ──reconcile──▶ (real state)
                                       └─reject──▶ REJECTED_BROKER
```

Rules:
- Never assume success. `UNKNOWN` triggers reconciliation against the broker's order book before *any* retry, to prevent duplicate orders.
- `client_order_id` is generated once and reused on retry (idempotency).
- At startup and every N minutes, **reconcile**: broker positions vs our positions. Any mismatch → alert and halt new entries.

## 5. Storage

### Phase 1–3: DuckDB + Parquet
```
data/
├── raw/<source>/<interval>/<symbol>/<yyyymm>.parquet     # append-only, as downloaded
├── clean/<interval>/<symbol>.parquet                     # adjusted, validated
└── market_view.duckdb                                    # views over parquet + backtest results
```

### Phase 4+: PostgreSQL + TimescaleDB (Docker)

| Table | Purpose |
|---|---|
| `instruments` | Symbol master (Groww symbol, ISIN, lot size, tick size, sector, index membership *with dates*) |
| `candles` (hypertable) | OHLCV by symbol/interval/ts |
| `corporate_actions` | Splits, bonus, dividends |
| `index_membership` | Historical NIFTY constituents (fights survivorship bias) |
| `strategies`, `strategy_versions` | Code ref (git SHA), params |
| `backtest_runs`, `backtest_trades` | Every experiment, never overwritten |
| `signals` | All signals, including rejected ones and the rejection reason |
| `orders`, `fills`, `positions`, `trades` | Execution truth |
| `trade_journal` | Trade + context snapshot + MAE/MFE + post-mortem notes + AI analysis |
| `market_context_daily` | Regime, VIX, FII/DII, USD/INR, crude, breadth… |
| `news`, `news_sentiment` | Raw articles + LLM/FinBERT scores |
| `models`, `model_predictions` | ML versions and outputs (for drift monitoring) |
| `system_events` | Kill-switch triggers, disconnects, errors |

## 6. Deployment (Phase 5+)

```
Local laptop (Windows)                    Static-IP VPS (Linux, Mumbai region)
──────────────────────                    ────────────────────────────────────
research, notebooks, backtests            docker compose:
UI in browser  ─────── HTTPS/VPN ───────▶   app (scheduler + engine + API)
                                             postgres/timescale
                                             grafana (later)
                                          static IPv4 whitelisted at Groww
```

- VPS in an Indian region (AWS Mumbai `ap-south-1` / DigitalOcean Bangalore) for latency and IP stability.
- Only the VPS can place orders (static IP). The laptop never holds live order credentials.
- Telegram bot for notifications, plus one command: `/killswitch`.

## 7. Observability (minimal → full)

- **Phase 4:** structured JSON logs and a `/health` endpoint showing broker, feed, DB, last tick age, open positions, daily P&L and risk state.
- **Phase 6:** Prometheus metrics + Grafana dashboard (feed lag, order latency, slippage, P&L, model drift). Use the `monitoring-expert` skill.
