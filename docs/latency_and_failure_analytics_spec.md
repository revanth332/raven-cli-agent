# Specification: Model Latency & Failure Analytics Dashboard Enhancement

## 1. Overview & Objectives

This specification defines the architectural additions and visual components required to monitor, record, and visualize **request latency (response duration and time-to-first-token)** and **request failure rates / error codes** across different LLM models within Raven's usage tracking subsystem (`/usage`).

### Key Objectives
1. **Turn-Level Metric Collection:** Accurately capture execution duration (ms), time-to-first-token (TTFT), completion status (`success` vs `error`), and HTTP/API error codes in `agent/core/llm.py`.
2. **Aggregated Storage Schema:** Extend `UsageTracker` and `~/.raven/usage_history.json` / `usage_data.js` to store daily latency percentiles ($P_{50}$, $P_{95}$, avg) and error classifications per model with full backward compatibility.
3. **Interactive Visual Dashboards:** Expand the HTML usage report (`usage_report.html`) with specialized Chart.js visualizations:
   - **P50 / P95 Latency Over Time (Multi-Line Chart)**
   - **Model Reliability & Error Rate (100% Stacked Bar Chart)**
   - **Error Category Breakdown (Grouped Stacked Bar / Doughnut)**
   - **Latency vs. Completion Tokens (Scatter Plot / Throughput curve)**
4. **Resilience & Fault Tolerance:** Ensure tracking records both successful streaming turns and failed/interrupted calls without interrupting agent flow.

---

## 2. Architecture & Data Flow

```mermaid
graph TD
    A[LLM Call Initiated] -->|Start Timer| B[OpenRouterChatSession.stream]
    B -->|First Chunk Received| C[Record TTFT]
    B -->|Stream Complete| D[Calculate Total Duration]
    B -->|Exception / API Error| E[Capture Error Code & Duration]
    
    D -->|turn stats| F[UsageTracker.record_turn]
    E -->|error stats| F
    
    F -->|aggregate P50/P95 & error counts| G[MemoryStore / daily_usage]
    G -->|persist| H[usage_history.json]
    G -->|export JS object| I[usage_data.js]
    
    J[/usage Command] --> K[Launch Browser Dashboard]
    K --> L[usage_report.html]
    L -->|renders latency & failure charts| I
```

---

## 3. Data Schema Specifications

### 3.1. Turn Recording Interface (`UsageTracker.record_turn`)

Update `UsageTracker.record_turn` signature to accept latency and failure telemetry:

```python
def record_turn(
    self,
    prompt_tokens: int,
    completion_tokens: int,
    model_name: str,
    duration_ms: float = 0.0,
    ttft_ms: Optional[float] = None,
    status: str = "success",       # "success" | "error"
    error_code: Optional[str] = None  # "429", "500", "503", "TIMEOUT", "CONTEXT_EXCEEDED", "AUTH_ERROR"
) -> Dict[str, Any]:
```

### 3.2. Daily Storage Schema (`~/.raven/usage_history.json`)

The aggregated daily JSON structure preserves existing token/cost fields while introducing the `latency` and `reliability` structures:

```json
{
  "2025-05-10": {
    "google/gemini-2.5-flash-lite": {
      "prompt_tokens": 12400,
      "completion_tokens": 3200,
      "tokens": 15600,
      "requests": 25,
      "cost": 0.00175,
      "latency": {
        "samples_ms": [620, 710, 850, 1200, 640],
        "avg_ms": 780.4,
        "p50_ms": 710.0,
        "p95_ms": 1180.0,
        "avg_ttft_ms": 240.5
      },
      "reliability": {
        "success_count": 24,
        "failure_count": 1,
        "failure_reasons": {
          "429": 1
        }
      }
    }
  }
}
```

*Note on sample retention:* To keep file sizes compact, `samples_ms` retains a maximum rolling buffer of the last 100 raw turn latencies per model per day, used to calculate exact percentiles on export.

---

## 4. Visualizations & Chart Specifications

### Chart 1: Latency Trends Over Time ($P_{50}$ & $P_{95}$)
- **Chart Type:** Multi-Line Chart (`type: 'line'`).
- **X-Axis:** Date (`YYYY-MM-DD`).
- **Y-Axis:** Response Time (seconds or ms).
- **Datasets:** For each model, two lines (Solid line for Median $P_{50}$, Dashed translucent line for $P_{95}$ tail latency).
- **Value:** Instantly reveals provider degradation, throttling, or slow inference spikes.

### Chart 2: Model Reliability Comparison (Normalized Success vs. Failure)
- **Chart Type:** 100% Stacked Horizontal or Vertical Bar (`type: 'bar'`, `scales: { x: { stacked: true, max: 100 } }`).
- **X-Axis / Category:** Models.
- **Y-Axis:** Percentage (0% - 100%).
- **Datasets:**
  - Success Rate (%) in Emerald (`#10B981`)
  - Failure Rate (%) in Rose/Crimson (`#EF4444`)
- **Value:** Prevents raw volume bias; clearly shows if a low-traffic model has unacceptable failure rates.

### Chart 3: Error Category Breakdown
- **Chart Type:** Grouped Stacked Bar or Donut Chart (`type: 'doughnut'` or `type: 'bar'`).
- **Categories:** Rate Limit (`429`), Server Errors (`5xx`), Timeouts (`TIMEOUT`), Context Exceeded (`400/CONTEXT`), Client/Auth (`401/403`).
- **Value:** Highlights root causes (e.g. need for exponential backoff on 429 vs context window compaction).

### Chart 4: Latency vs. Output Token Count (Scatter & Speed Analysis)
- **Chart Type:** Scatter Plot (`type: 'scatter'`).
- **X-Axis:** Completion Tokens.
- **Y-Axis:** Duration in Seconds.
- **Datasets:** Points grouped by Model color.
- **Value:** The linear slope indicates generation speed (tokens/sec). Points drifting far above the trend line reveal network stalls or reasoning delays.

---

## 5. Implementation Plan

### Step 1: Instrument LLM Session (`agent/core/llm.py`)
- Wrap `OpenRouterChatSession.stream()` with a precise monotonic timer (`time.perf_counter()`).
- Capture `ttft_ms` upon yielding the very first content or reasoning chunk.
- In `except Exception as e`:
  - Identify error code (e.g., inspect `e.status_code`, `openai.RateLimitError`, `openai.APIConnectionError`).
  - Calculate elapsed time until failure.
  - Call `usage_tracker.record_turn(..., status="error", error_code=...)`.
  - Re-raise exception so agent error handling remains intact.

### Step 2: Extend `UsageTracker` (`agent/core/usage_tracker.py`)
- Update `record_turn()` to calculate running averages, $P_{50}$ / $P_{95}$ percentiles (via `statistics.quantiles` or sorted numpy-free index calculation).
- Increment `success_count`, `failure_count`, and `failure_reasons[error_code]`.
- Update `load_history()` to handle legacy records missing the `latency` or `reliability` keys gracefully.

### Step 3: Upgrade Dashboard Template (`agent/core/usage_html_template.py`)
- Add 2 summary metric KPI cards to the top row:
  - **Avg P50 Latency (Across Models)**
  - **Overall Success Rate (%)**
- Add a new visual row:
  - **Latency Over Time ($P_{50} / P_{95}$)**
  - **Model Reliability & Error Distribution**
- Include an interactive filter to toggle between models or switch latency units (seconds vs ms).

### Step 4: Unit & Integration Testing
- Add `tests/test_latency_and_failure_analytics.py`:
  - Verify error recording on mocked API exceptions.
  - Verify percentile calculations ($P_{50}$, $P_{95}$) with known sample sets.
  - Verify dashboard rendering handles missing/zero error days without crashing.

---

## 6. Backward Compatibility & Edge Cases

1. **Legacy Historical Data:** Existing `usage_history.json` entries without `latency` or `reliability` keys must default to `latency: { avg_ms: 0, p50_ms: 0, p95_ms: 0 }` and `reliability: { success_count: requests, failure_count: 0 }`.
2. **Zero-Token Errors:** API failures happening before streaming produces 0 prompt/completion tokens. The tracker must record `requests: 1, prompt_tokens: 0, completion_tokens: 0, status: "error"` without breaking cost calculations.
3. **No External Chart Plugins:** All charts will use vanilla Chart.js 4.x features natively supported in standard browser distributions.
