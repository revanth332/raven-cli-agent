USAGE_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raven AI - Usage Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #f8fafc;
            --bg-card: #ffffff;
            --bg-card-hover: #f1f5f9;
            --accent-primary: #2563eb;
            --accent-emerald: #10b981;
            --accent-purple: #8b5cf6;
            --accent-amber: #f59e0b;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --border: #e2e8f0;
            --border-light: #f1f5f9;
            --table-header-bg: #f8fafc;
            --badge-bg: #eff6ff;
            --badge-text: #2563eb;
            --badge-border: #dbeafe;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            padding: 2.5rem 1.75rem;
            min-height: 100vh;
        }

        .container {
            max-width: 1280px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }

        .logo-icon {
            font-size: 2rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, #eff6ff, #dbeafe);
            border: 1px solid #bfdbfe;
            border-radius: 10px;
        }

        .title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.02em;
        }

        .subtitle {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 0.15rem;
        }

        .refresh-badge {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            color: #16a34a;
            padding: 0.45rem 0.9rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.45rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
        }

        .refresh-badge .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #22c55e;
            display: inline-block;
        }

        /* Stat Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.35rem 1.25rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.03);
            transition: transform 0.18s ease, box-shadow 0.18s ease;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        }

        .stat-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.2;
        }

        .stat-subtext {
            font-size: 0.775rem;
            color: var(--text-muted);
            margin-top: 0.4rem;
        }

        /* Charts Grid */
        .charts-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 1.75rem;
        }

        @media (max-width: 960px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }
        }

        .chart-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.35rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.03);
        }

        .chart-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.15rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .chart-card-header .chart-title {
            margin-bottom: 0;
        }

        .chart-title {
            font-size: 0.975rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .chart-wrapper {
            position: relative;
            height: 280px;
            width: 100%;
        }

        /* Table */
        .table-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.35rem;
            overflow-x: auto;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.03);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }

        th {
            background: var(--table-header-bg);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        td {
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border-light);
            color: var(--text-primary);
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background: #f8fafc;
        }

        .model-tag {
            background: var(--badge-bg);
            color: var(--badge-text);
            border: 1px solid var(--badge-border);
            padding: 0.2rem 0.55rem;
            border-radius: 6px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.8rem;
            font-weight: 500;
        }

        .metric-badge {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-size: 0.775rem;
            font-weight: 600;
        }

        .metric-success {
            background: #f0fdf4;
            color: #16a34a;
            border: 1px solid #bbf7d0;
        }

        .metric-warning {
            background: #fffbeb;
            color: #b45309;
            border: 1px solid #fde68a;
        }

        .metric-danger {
            background: #fef2f2;
            color: #dc2626;
            border: 1px solid #fecaca;
        }

        .filter-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.85rem 1.25rem;
            margin-bottom: 1.75rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
            flex-wrap: wrap;
            gap: 1rem;
        }

        .filter-group {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .filter-label {
            font-size: 0.825rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .filter-select {
            padding: 0.45rem 0.9rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: #ffffff;
            color: var(--text-primary);
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            outline: none;
            transition: border-color 0.15s ease;
        }

        .filter-select:focus {
            border-color: var(--accent-primary);
        }

        .btn-group {
            display: inline-flex;
            border-radius: 8px;
            border: 1px solid var(--border);
            overflow: hidden;
        }

        .btn-toggle {
            padding: 0.4rem 0.85rem;
            background: #ffffff;
            border: none;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .btn-toggle.active {
            background: var(--accent-primary);
            color: #ffffff;
        }

        .btn-group-sm .btn-toggle {
            padding: 0.25rem 0.65rem;
            font-size: 0.75rem;
        }

        .section-header {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 2.25rem 0 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            letter-spacing: -0.01em;
        }

        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            background: var(--bg-card);
            border: 1px dashed var(--border);
            border-radius: 12px;
            color: var(--text-secondary);
        }

        .empty-state h2 {
            font-size: 1.25rem;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <span class="logo-icon">⚡</span>
                <div>
                    <h1 class="title">Raven Usage & Analytics</h1>
                    <p class="subtitle">Daily token consumption, latency telemetry, and model reliability metrics</p>
                </div>
            </div>
            <div class="refresh-badge">
                <span class="dot"></span> Auto-Synced via usage_data.js
            </div>
        </header>

        <div id="dashboard-content">
            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Tokens</div>
                    <div class="stat-value" id="total-tokens">0</div>
                    <div class="stat-subtext" id="token-split">Prompt: 0 | Completion: 0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Requests</div>
                    <div class="stat-value" id="total-requests">0</div>
                    <div class="stat-subtext" id="requests-sub">Across all sessions</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Estimated Cost</div>
                    <div class="stat-value" id="total-cost">$0.00</div>
                    <div class="stat-subtext" id="cost-inr">≈ ₹0.00 INR</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Top Model</div>
                    <div class="stat-value" id="top-model" style="font-size: 1.15rem; word-break: break-all;">-</div>
                    <div class="stat-subtext" id="top-model-sub">0 tokens</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Avg P50 Latency</div>
                    <div class="stat-value" id="avg-p50-latency">-</div>
                    <div class="stat-subtext" id="avg-p50-sub">Across models</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Overall Success Rate</div>
                    <div class="stat-value" id="overall-success-rate">100%</div>
                    <div class="stat-subtext" id="success-rate-sub">0 ok | 0 errors</div>
                </div>
            </div>

            <!-- Controls Toolbar -->
            <div class="filter-bar">
                <div class="filter-group">
                    <span class="filter-label">Filter Model:</span>
                    <select id="model-filter" class="filter-select" onchange="onFilterChange()">
                        <option value="all">All Models</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Latency Unit:</span>
                    <div class="btn-group">
                        <button id="btn-unit-ms" class="btn-toggle active" onclick="setLatencyUnit('ms')">ms</button>
                        <button id="btn-unit-s" class="btn-toggle" onclick="setLatencyUnit('s')">seconds</button>
                    </div>
                </div>
            </div>

            <!-- Section 1: Performance & Latency Analytics -->
            <div class="section-header">⏱️ Model Latency & Speed Analytics</div>
            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-title">📈 Latency Trends Over Time (P50 Median & P95 Tail)</div>
                    <div class="chart-wrapper">
                        <canvas id="latencyTrendsChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <div class="chart-title">⚡ Latency vs. Output Tokens (Speed Analysis)</div>
                    <div class="chart-wrapper">
                        <canvas id="latencyScatterChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Section 2: Reliability & Error Analytics -->
            <div class="section-header">🛡️ Reliability & Error Distribution</div>
            <div class="charts-grid" style="grid-template-columns: 1fr 1fr;">
                <div class="chart-card">
                    <div class="chart-title">📊 Model Reliability Comparison (Normalized 100%)</div>
                    <div class="chart-wrapper">
                        <canvas id="reliabilityChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <div class="chart-title">🚨 Error Category Breakdown</div>
                    <div class="chart-wrapper">
                        <canvas id="errorBreakdownChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Section 3: Consumption & Cost Analytics -->
            <div class="section-header">📊 Token Consumption & Cost</div>
            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-card-header">
                        <div class="chart-title">📊 Daily Token Consumption per Model</div>
                        <div class="btn-group btn-group-sm">
                            <button id="btn-tokens-7d" class="btn-toggle active" onclick="setTokenRange('7d')">7D</button>
                            <button id="btn-tokens-14d" class="btn-toggle" onclick="setTokenRange('14d')">14D</button>
                            <button id="btn-tokens-30d" class="btn-toggle" onclick="setTokenRange('30d')">30D</button>
                            <button id="btn-tokens-all" class="btn-toggle" onclick="setTokenRange('all')">All</button>
                        </div>
                    </div>
                    <div class="chart-wrapper">
                        <canvas id="tokensChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <div class="chart-title">🍩 Model Share (% Tokens)</div>
                    <div class="chart-wrapper">
                        <canvas id="modelShareChart"></canvas>
                    </div>
                </div>
            </div>

            <div class="chart-card" style="margin-bottom: 2rem;">
                <div class="chart-card-header">
                    <div class="chart-title">💰 Daily Cost Trajectory</div>
                    <div class="btn-group btn-group-sm">
                        <button id="btn-cost-usd" class="btn-toggle active" onclick="setCostCurrency('USD')">$ USD</button>
                        <button id="btn-cost-inr" class="btn-toggle" onclick="setCostCurrency('INR')">₹ INR</button>
                    </div>
                </div>
                <div class="chart-wrapper">
                    <canvas id="costTrajectoryChart"></canvas>
                </div>
            </div>

            <!-- Detailed Telemetry Table -->
            <div class="table-card">
                <div class="chart-title">📋 Daily Detailed Telemetry Breakdown</div>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Model</th>
                            <th>Requests</th>
                            <th>Reliability</th>
                            <th>P50 Latency</th>
                            <th>P95 Latency</th>
                            <th>Prompt Tokens</th>
                            <th>Completion Tokens</th>
                            <th>Total Tokens</th>
                            <th>Est. Cost (USD / INR)</th>
                        </tr>
                    </thead>
                    <tbody id="table-body">
                    </tbody>
                </table>
            </div>
        </div>

        <div id="empty-state" class="empty-state" style="display: none;">
            <h2>No Usage Data Recorded Yet</h2>
            <p>Usage metrics will appear here automatically as you interact with Raven.</p>
        </div>
    </div>

    <!-- Dynamic Data injected via usage_data.js -->
    <script src="usage_data.js"></script>

    <script>
        const PALETTE = [
            '#2563eb', '#10b981', '#8b5cf6', '#f59e0b', '#06b6d4',
            '#ec4899', '#f97316', '#6366f1', '#14b8a6', '#84cc16'
        ];

        let latencyUnit = 'ms'; // 'ms' | 's'
        let activeModelFilter = 'all';
        let tokenDateRange = '7d'; // '7d' | '14d' | '30d' | 'all'
        let costCurrency = 'USD'; // 'USD' | 'INR'
        const chartInstances = {};

        function destroyChart(id) {
            if (chartInstances[id]) {
                chartInstances[id].destroy();
                delete chartInstances[id];
            }
        }

        function setLatencyUnit(unit) {
            if (latencyUnit === unit) return;
            latencyUnit = unit;
            document.getElementById('btn-unit-ms').classList.toggle('active', unit === 'ms');
            document.getElementById('btn-unit-s').classList.toggle('active', unit === 's');
            renderDashboard();
        }

        function setTokenRange(range) {
            if (tokenDateRange === range) return;
            tokenDateRange = range;
            ['7d', '14d', '30d', 'all'].forEach(r => {
                const btn = document.getElementById('btn-tokens-' + r);
                if (btn) btn.classList.toggle('active', r === range);
            });
            renderDashboard();
        }

        function setCostCurrency(curr) {
            if (costCurrency === curr) return;
            costCurrency = curr;
            const btnUsd = document.getElementById('btn-cost-usd');
            const btnInr = document.getElementById('btn-cost-inr');
            if (btnUsd) btnUsd.classList.toggle('active', curr === 'USD');
            if (btnInr) btnInr.classList.toggle('active', curr === 'INR');
            renderDashboard();
        }

        function onFilterChange() {
            activeModelFilter = document.getElementById('model-filter').value;
            renderDashboard();
        }

        function classifyError(code) {
            const c = String(code || '').toUpperCase();
            if (c === '429' || c.includes('RATE') || c.includes('QUOTA')) return 'Rate Limit (429)';
            if (c === 'TIMEOUT' || c.includes('TIMED_OUT')) return 'Timeouts (TIMEOUT)';
            if (c === 'CONTEXT_EXCEEDED' || c.includes('CONTEXT') || c === '400') return 'Context Exceeded (400/CONTEXT)';
            if (c === 'AUTH_ERROR' || c === '401' || c === '403' || c.includes('AUTH') || c.includes('PERMISSION')) return 'Client/Auth (401/403)';
            if (c.startsWith('5') || c.includes('SERVER') || c === '500' || c === '503') return 'Server Errors (5xx)';
            return 'Other (' + c + ')';
        }

        function formatDuration(ms, unit) {
            if (!ms || ms <= 0) return '-';
            if (unit === 's') return (ms / 1000).toFixed(2) + ' s';
            return Math.round(ms) + ' ms';
        }

        function renderDashboard() {
            const rawData = window.USAGE_DATA || {};
            const dates = Object.keys(rawData).sort();

            if (dates.length === 0) {
                document.getElementById('dashboard-content').style.display = 'none';
                document.getElementById('empty-state').style.display = 'block';
                return;
            }

            let totalTokens = 0;
            let totalPromptTokens = 0;
            let totalCompletionTokens = 0;
            let totalRequests = 0;
            let totalCost = 0.0;
            let totalSuccess = 0;
            let totalFailures = 0;
            const p50Samples = [];
            const modelTokenCounts = {};
            const allModelsSet = new Set();
            const rows = [];

            // Aggregate error categories
            const errorCategoryCounts = {
                'Rate Limit (429)': 0,
                'Server Errors (5xx)': 0,
                'Timeouts (TIMEOUT)': 0,
                'Context Exceeded (400/CONTEXT)': 0,
                'Client/Auth (401/403)': 0,
                'Other': 0
            };

            dates.forEach(date => {
                const dayData = rawData[date];
                Object.keys(dayData).forEach(model => {
                    allModelsSet.add(model);
                    const m = dayData[model];
                    const pTokens = m.prompt_tokens || 0;
                    const cTokens = m.completion_tokens || 0;
                    const tokens = m.tokens || (pTokens + cTokens);
                    const reqs = m.requests || 0;
                    const cost = m.cost || 0.0;

                    // Reliability metrics
                    const rel = m.reliability || {};
                    const successCount = rel.success_count != null ? rel.success_count : reqs;
                    const failureCount = rel.failure_count || 0;
                    const failureReasons = rel.failure_reasons || {};

                    // Latency metrics
                    const lat = m.latency || {};
                    const p50 = lat.p50_ms || lat.avg_ms || 0;
                    const p95 = lat.p95_ms || 0;

                    totalTokens += tokens;
                    totalPromptTokens += pTokens;
                    totalCompletionTokens += cTokens;
                    totalRequests += reqs;
                    totalCost += cost;
                    totalSuccess += successCount;
                    totalFailures += failureCount;

                    if (p50 > 0) p50Samples.push(p50);
                    modelTokenCounts[model] = (modelTokenCounts[model] || 0) + tokens;

                    // Collect errors for chart
                    if (activeModelFilter === 'all' || activeModelFilter === model) {
                        Object.keys(failureReasons).forEach(reason => {
                            const cat = classifyError(reason);
                            const count = failureReasons[reason] || 0;
                            if (errorCategoryCounts[cat] != null) {
                                errorCategoryCounts[cat] += count;
                            } else {
                                errorCategoryCounts['Other'] += count;
                            }
                        });
                    }

                    rows.push({
                        date,
                        model,
                        requests: reqs,
                        successCount,
                        failureCount,
                        p50,
                        p95,
                        promptTokens: pTokens,
                        completionTokens: cTokens,
                        tokens,
                        cost
                    });
                });
            });

            // Populate Filter dropdown if not already populated
            const selectEl = document.getElementById('model-filter');
            const models = Array.from(allModelsSet).sort();
            if (selectEl && selectEl.options.length <= 1) {
                models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.innerText = m;
                    selectEl.appendChild(opt);
                });
            }

            const modelColorMap = {};
            models.forEach((m, idx) => {
                modelColorMap[m] = PALETTE[idx % PALETTE.length];
            });

            const USD_TO_INR = 86.8;

            // 1. KPI Cards
            document.getElementById('total-tokens').innerText = totalTokens.toLocaleString();
            document.getElementById('token-split').innerText = `Prompt: ${totalPromptTokens.toLocaleString()} | Completion: ${totalCompletionTokens.toLocaleString()}`;
            document.getElementById('total-requests').innerText = totalRequests.toLocaleString();
            document.getElementById('total-cost').innerText = `$${totalCost.toFixed(4)}`;
            const costINR = totalCost * USD_TO_INR;
            document.getElementById('cost-inr').innerText = `≈ ₹${costINR.toFixed(2)} INR (1$ ≈ ₹${USD_TO_INR})`;

            let topModelName = '-';
            let topModelTokens = 0;
            Object.keys(modelTokenCounts).forEach(m => {
                if (modelTokenCounts[m] > topModelTokens) {
                    topModelTokens = modelTokenCounts[m];
                    topModelName = m;
                }
            });
            document.getElementById('top-model').innerText = topModelName;
            document.getElementById('top-model-sub').innerText = `${topModelTokens.toLocaleString()} tokens (${totalTokens > 0 ? ((topModelTokens/totalTokens)*100).toFixed(1) : 0}%)`;

            // Avg P50 Latency
            const avgP50 = p50Samples.length > 0 ? (p50Samples.reduce((a, b) => a + b, 0) / p50Samples.length) : 0;
            document.getElementById('avg-p50-latency').innerText = formatDuration(avgP50, latencyUnit);
            document.getElementById('avg-p50-sub').innerText = `${p50Samples.length} samples evaluated`;

            // Overall Success Rate
            const totalTurnAttempts = totalSuccess + totalFailures;
            const successRate = totalTurnAttempts > 0 ? ((totalSuccess / totalTurnAttempts) * 100) : 100.0;
            const successEl = document.getElementById('overall-success-rate');
            successEl.innerText = `${successRate.toFixed(1)}%`;
            if (successRate >= 99.0) successEl.style.color = '#10b981';
            else if (successRate >= 90.0) successEl.style.color = '#f59e0b';
            else successEl.style.color = '#ef4444';
            document.getElementById('success-rate-sub').innerText = `${totalSuccess.toLocaleString()} ok | ${totalFailures.toLocaleString()} errors`;

            // 2. Populate Table (Reverse Chronological)
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';
            const filteredRows = activeModelFilter === 'all' ? rows : rows.filter(r => r.model === activeModelFilter);
            filteredRows.slice().reverse().forEach(r => {
                const tr = document.createElement('tr');
                const rowINR = r.cost * USD_TO_INR;
                const turnTotal = r.successCount + r.failureCount;
                const rowRate = turnTotal > 0 ? ((r.successCount / turnTotal) * 100).toFixed(0) : 100;
                let relBadgeClass = 'metric-success';
                if (rowRate < 90) relBadgeClass = 'metric-danger';
                else if (rowRate < 99) relBadgeClass = 'metric-warning';

                tr.innerHTML = `
                    <td><strong>${r.date}</strong></td>
                    <td><span class="model-tag">${r.model}</span></td>
                    <td>${r.requests}</td>
                    <td><span class="metric-badge ${relBadgeClass}">${rowRate}% (${r.successCount}/${r.failureCount})</span></td>
                    <td>${formatDuration(r.p50, latencyUnit)}</td>
                    <td>${formatDuration(r.p95, latencyUnit)}</td>
                    <td>${r.promptTokens.toLocaleString()}</td>
                    <td>${r.completionTokens.toLocaleString()}</td>
                    <td><strong>${r.tokens.toLocaleString()}</strong></td>
                    <td><strong>$${r.cost.toFixed(4)}</strong> <span style="color: #64748b; font-size: 0.78rem;">(₹${rowINR.toFixed(2)})</span></td>
                `;
                tbody.appendChild(tr);
            });

            // Filter models for charts if a specific model is selected
            const activeModels = activeModelFilter === 'all' ? models : models.filter(m => m === activeModelFilter);

            // CHART 1: Latency Trends Over Time (P50 & P95)
            destroyChart('latencyTrendsChart');
            const latencyDatasets = [];
            activeModels.forEach(m => {
                const color = modelColorMap[m] || '#2563eb';
                // Solid P50 Line
                latencyDatasets.push({
                    type: 'line',
                    label: `${m} (P50 Median)`,
                    data: dates.map(d => {
                        const rec = rawData[d]?.[m]?.latency;
                        const val = rec ? (rec.p50_ms || rec.avg_ms || 0) : 0;
                        return latencyUnit === 's' ? +(val / 1000).toFixed(2) : Math.round(val);
                    }),
                    borderColor: color,
                    backgroundColor: color,
                    borderWidth: 2.2,
                    tension: 0.35,
                    pointRadius: 3.5,
                    pointHoverRadius: 6
                });
                // Dashed P95 Tail Line
                latencyDatasets.push({
                    type: 'line',
                    label: `${m} (P95 Tail)`,
                    data: dates.map(d => {
                        const rec = rawData[d]?.[m]?.latency;
                        const val = rec ? (rec.p95_ms || rec.avg_ms || 0) : 0;
                        return latencyUnit === 's' ? +(val / 1000).toFixed(2) : Math.round(val);
                    }),
                    borderColor: color,
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    pointRadius: 2.5,
                    tension: 0.35,
                    pointHoverRadius: 5
                });
            });

            chartInstances['latencyTrendsChart'] = new Chart(document.getElementById('latencyTrendsChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: latencyDatasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            title: { display: true, text: latencyUnit === 's' ? 'Duration (seconds)' : 'Duration (ms)', color: '#64748b' },
                            ticks: { color: '#64748b', font: { size: 11 } }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 11 } } },
                        tooltip: { backgroundColor: '#0f172a', padding: 10, cornerRadius: 8 }
                    }
                }
            });

            // CHART 2: Model Reliability Comparison (100% Stacked Bar)
            destroyChart('reliabilityChart');
            const relModels = activeModels;
            const successPercentages = [];
            const failurePercentages = [];

            relModels.forEach(m => {
                let mSuccess = 0;
                let mFail = 0;
                dates.forEach(d => {
                    const rec = rawData[d]?.[m];
                    if (rec) {
                        const rel = rec.reliability || {};
                        mSuccess += (rel.success_count != null ? rel.success_count : (rec.requests || 0));
                        mFail += (rel.failure_count || 0);
                    }
                });
                const total = mSuccess + mFail;
                if (total > 0) {
                    successPercentages.push(+((mSuccess / total) * 100).toFixed(1));
                    failurePercentages.push(+((mFail / total) * 100).toFixed(1));
                } else {
                    successPercentages.push(100);
                    failurePercentages.push(0);
                }
            });

            chartInstances['reliabilityChart'] = new Chart(document.getElementById('reliabilityChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: relModels,
                    datasets: [
                        {
                            label: 'Success Rate (%)',
                            data: successPercentages,
                            backgroundColor: '#10B981',
                            borderRadius: 4,
                            stack: 'rel'
                        },
                        {
                            label: 'Failure Rate (%)',
                            data: failurePercentages,
                            backgroundColor: '#EF4444',
                            borderRadius: 4,
                            stack: 'rel'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    maxBarThickness: 50,
                    scales: {
                        x: { stacked: true, grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                color: '#64748b',
                                font: { size: 11 },
                                callback: val => val + '%'
                            },
                            grid: { color: 'rgba(0, 0, 0, 0.05)' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 12 } } },
                        tooltip: { backgroundColor: '#0f172a', padding: 10, cornerRadius: 8 }
                    }
                }
            });

            // CHART 3: Error Category Breakdown (Doughnut)
            destroyChart('errorBreakdownChart');
            const errLabels = Object.keys(errorCategoryCounts);
            const errData = errLabels.map(k => errorCategoryCounts[k]);
            const totalRecordedErrors = errData.reduce((a, b) => a + b, 0);

            const errChartLabels = totalRecordedErrors > 0 ? errLabels : ['100% Reliable (0 Errors)'];
            const errChartData = totalRecordedErrors > 0 ? errData : [1];
            const errChartColors = totalRecordedErrors > 0 ? [
                '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#64748b'
            ] : ['#10B981'];

            chartInstances['errorBreakdownChart'] = new Chart(document.getElementById('errorBreakdownChart').getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: errChartLabels,
                    datasets: [{
                        data: errChartData,
                        backgroundColor: errChartColors,
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#334155', boxWidth: 10, usePointStyle: true, padding: 12, font: { size: 11 } } },
                        tooltip: { backgroundColor: '#0f172a', padding: 10, cornerRadius: 8 }
                    }
                }
            });

            // CHART 4: Latency vs Output Tokens Scatter Plot
            destroyChart('latencyScatterChart');
            const scatterDatasets = [];
            activeModels.forEach(m => {
                const color = modelColorMap[m] || '#2563eb';
                const points = [];
                dates.forEach(d => {
                    const rec = rawData[d]?.[m];
                    if (rec && rec.latency && rec.latency.points && rec.latency.points.length > 0) {
                        rec.latency.points.forEach(pt => {
                            const yVal = latencyUnit === 's' ? +(pt.duration_ms / 1000).toFixed(2) : pt.duration_ms;
                            points.push({ x: pt.tokens || 0, y: yVal });
                        });
                    } else if (rec && (rec.completion_tokens || rec.tokens)) {
                        // Fallback sample from aggregated record
                        const p50Val = rec.latency ? (rec.latency.p50_ms || rec.latency.avg_ms || 0) : 0;
                        if (p50Val > 0) {
                            const yVal = latencyUnit === 's' ? +(p50Val / 1000).toFixed(2) : p50Val;
                            points.push({ x: rec.completion_tokens || rec.tokens, y: yVal });
                        }
                    }
                });

                scatterDatasets.push({
                    label: m,
                    data: points,
                    backgroundColor: color,
                    borderColor: color,
                    pointRadius: 4,
                    pointHoverRadius: 6
                });
            });

            chartInstances['latencyScatterChart'] = new Chart(document.getElementById('latencyScatterChart').getContext('2d'), {
                type: 'scatter',
                data: { datasets: scatterDatasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            beginAtZero: true,
                            title: { display: true, text: 'Completion Tokens', color: '#64748b' },
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            ticks: { color: '#64748b', font: { size: 11 } }
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: latencyUnit === 's' ? 'Duration (seconds)' : 'Duration (ms)', color: '#64748b' },
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            ticks: { color: '#64748b', font: { size: 11 } }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 11 } } },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            padding: 10,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(ctx) {
                                    return `${ctx.dataset.label}: ${ctx.raw.x} tokens in ${ctx.raw.y} ${latencyUnit}`;
                                }
                            }
                        }
                    }
                }
            });

            // CHART 5: Daily Token Consumption per Model
            destroyChart('tokensChart');

            let tokenDates = dates;
            if (tokenDateRange === '7d') tokenDates = dates.slice(-7);
            else if (tokenDateRange === '14d') tokenDates = dates.slice(-14);
            else if (tokenDateRange === '30d') tokenDates = dates.slice(-30);

            const dailyTotals = tokenDates.map(d => {
                let daySum = 0;
                activeModels.forEach(m => {
                    if (rawData[d] && rawData[d][m]) {
                        const rec = rawData[d][m];
                        daySum += (rec.tokens || ((rec.prompt_tokens || 0) + (rec.completion_tokens || 0)));
                    }
                });
                return daySum;
            });

            // Elevate line 8% above the bars to prevent visual collision
            const ELEVATION_FACTOR = 1.08;
            const elevatedDailyTotals = dailyTotals.map(val => val > 0 ? Math.round(val * ELEVATION_FACTOR) : 0);

            const totalLineDataset = {
                type: 'line',
                label: 'Total Daily Tokens (Trend)',
                data: elevatedDailyTotals,
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.14)',
                borderWidth: 2.5,
                fill: true,
                tension: 0.38,
                pointRadius: tokenDates.length === 1 ? 5 : 3.5,
                pointHoverRadius: 6,
                pointBackgroundColor: '#f59e0b',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                order: 2 // Render line and area fill behind the bars (order: 1)
            };

            const barDatasets = activeModels.map(m => {
                return {
                    type: 'bar',
                    label: m,
                    data: tokenDates.map(d => (rawData[d][m] ? (rawData[d][m].tokens || (rawData[d][m].prompt_tokens + rawData[d][m].completion_tokens)) : 0)),
                    backgroundColor: modelColorMap[m],
                    borderRadius: 4,
                    stack: 'tokens_stack',
                    order: 1 // Drawn in front of the area fill
                };
            });

            chartInstances['tokensChart'] = new Chart(document.getElementById('tokensChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: tokenDates,
                    datasets: [totalLineDataset, ...barDatasets]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    maxBarThickness: 48,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: {
                            stacked: true,
                            offset: false, // Edge-to-edge positioning
                            grid: { display: false, offset: false },
                            ticks: { color: '#64748b', font: { size: 12 } }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            ticks: {
                                color: '#64748b',
                                font: { size: 11 },
                                callback: function(value) {
                                    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                                    if (value >= 1000) return (value / 1000).toFixed(0) + 'K';
                                    return value;
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 12 } } },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            padding: 10,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    if (context.dataset.type === 'line') {
                                        const actualTotal = dailyTotals[context.dataIndex] || 0;
                                        return `Total Tokens: ${actualTotal.toLocaleString()}`;
                                    }
                                    return `${context.dataset.label}: ${context.parsed.y.toLocaleString()}`;
                                }
                            }
                        }
                    }
                }
            });

            // CHART 6: Model Share Doughnut
            destroyChart('modelShareChart');
            chartInstances['modelShareChart'] = new Chart(document.getElementById('modelShareChart').getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: models,
                    datasets: [{
                        data: models.map(m => modelTokenCounts[m] || 0),
                        backgroundColor: models.map(m => modelColorMap[m]),
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#334155', boxWidth: 10, usePointStyle: true, padding: 14, font: { size: 12 } } },
                        tooltip: { backgroundColor: '#0f172a', padding: 10, cornerRadius: 8 }
                    }
                }
            });

            // CHART 7: Daily Cost Trajectory Chart (replaces requestsChart)
            destroyChart('costTrajectoryChart');
            const isINR = (costCurrency === 'INR');
            const currencySymbol = isINR ? '₹' : '$';
            const multiplier = isINR ? USD_TO_INR : 1.0;

            const dailyCosts = dates.map(d => {
                let dayCost = 0.0;
                activeModels.forEach(m => {
                    if (rawData[d] && rawData[d][m]) {
                        dayCost += (rawData[d][m].cost || 0.0);
                    }
                });
                return Number((dayCost * multiplier).toFixed(4));
            });

            chartInstances['costTrajectoryChart'] = new Chart(document.getElementById('costTrajectoryChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: `Daily Total Cost (${currencySymbol})`,
                        data: dailyCosts,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.12)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.35,
                        pointRadius: dates.length === 1 ? 5 : 3.5,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#10b981',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: {
                            offset: false,
                            grid: { display: false, offset: false },
                            ticks: { color: '#64748b', font: { size: 12 } }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            ticks: {
                                color: '#64748b',
                                font: { size: 11 },
                                callback: function(value) {
                                    return currencySymbol + (isINR ? value.toFixed(2) : value.toFixed(3));
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 12 } } },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            padding: 10,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    const val = context.parsed.y;
                                    return `Total Cost: ${currencySymbol}${isINR ? val.toFixed(2) : val.toFixed(4)}`;
                                }
                            }
                        }
                    }
                }
            });
        }

        window.addEventListener('DOMContentLoaded', renderDashboard);
    </script>
</body>
</html>
"""
