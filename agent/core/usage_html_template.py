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
                    <p class="subtitle">Daily token consumption, request frequency, and cost breakdown</p>
                </div>
            </div>
            <div class="refresh-badge">
                <span class="dot"></span> Auto-Synced via usage_data.js
            </div>
        </header>

        <div id="dashboard-content">
            <!-- Stats -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Tokens</div>
                    <div class="stat-value" id="total-tokens">0</div>
                    <div class="stat-subtext" id="token-split">Prompt: 0 | Completion: 0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Requests</div>
                    <div class="stat-value" id="total-requests">0</div>
                    <div class="stat-subtext">Across all sessions</div>
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
            </div>

            <!-- Charts -->
            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-title">📊 Daily Token Consumption per Model</div>
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

            <div class="chart-card" style="margin-bottom: 1.75rem;">
                <div class="chart-title">📈 Daily Request Volume</div>
                <div class="chart-wrapper">
                    <canvas id="requestsChart"></canvas>
                </div>
            </div>

            <!-- Table -->
            <div class="table-card">
                <div class="chart-title">📋 Daily Detailed Breakdown</div>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Model</th>
                            <th>Requests</th>
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
            const modelTokenCounts = {};
            const allModelsSet = new Set();

            const rows = [];

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

                    totalTokens += tokens;
                    totalPromptTokens += pTokens;
                    totalCompletionTokens += cTokens;
                    totalRequests += reqs;
                    totalCost += cost;

                    modelTokenCounts[model] = (modelTokenCounts[model] || 0) + tokens;

                    rows.push({
                        date,
                        model,
                        requests: reqs,
                        promptTokens: pTokens,
                        completionTokens: cTokens,
                        tokens,
                        cost
                    });
                });
            });

            const USD_TO_INR = 86.8;

            // Summary stats
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

            // Populate Table (reverse chronological)
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';
            rows.reverse().forEach(r => {
                const tr = document.createElement('tr');
                const rowINR = r.cost * USD_TO_INR;
                tr.innerHTML = `
                    <td><strong>${r.date}</strong></td>
                    <td><span class="model-tag">${r.model}</span></td>
                    <td>${r.requests}</td>
                    <td>${r.promptTokens.toLocaleString()}</td>
                    <td>${r.completionTokens.toLocaleString()}</td>
                    <td><strong>${r.tokens.toLocaleString()}</strong></td>
                    <td><strong>$${r.cost.toFixed(4)}</strong> <span style="color: #64748b; font-size: 0.78rem;">(₹${rowINR.toFixed(2)})</span></td>
                `;
                tbody.appendChild(tr);
            });

            const models = Array.from(allModelsSet);
            const modelColorMap = {};
            models.forEach((m, idx) => {
                modelColorMap[m] = PALETTE[idx % PALETTE.length];
            });

            // 1. Mixed Stacked Bar & Smooth Area Curve: Daily Tokens
            const dailyTotals = dates.map(d => {
                let daySum = 0;
                models.forEach(m => {
                    if (rawData[d] && rawData[d][m]) {
                        const rec = rawData[d][m];
                        daySum += (rec.tokens || ((rec.prompt_tokens || 0) + (rec.completion_tokens || 0)));
                    }
                });
                return daySum;
            });

            const totalLineDataset = {
                type: 'line',
                label: 'Total Daily Tokens (Trend)',
                data: dailyTotals,
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.16)',
                borderWidth: 2.5,
                fill: true,
                tension: 0.38,
                pointRadius: dates.length === 1 ? 5 : 3.5,
                pointHoverRadius: 6,
                pointBackgroundColor: '#f59e0b',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                order: 0
            };

            const barDatasets = models.map(m => {
                return {
                    type: 'bar',
                    label: m,
                    data: dates.map(d => (rawData[d][m] ? (rawData[d][m].tokens || (rawData[d][m].prompt_tokens + rawData[d][m].completion_tokens)) : 0)),
                    backgroundColor: modelColorMap[m],
                    borderRadius: 4,
                    stack: 'tokens_stack',
                    order: 1
                };
            });

            new Chart(document.getElementById('tokensChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: dates,
                    datasets: [totalLineDataset, ...barDatasets]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    maxBarThickness: 48,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            stacked: true,
                            grid: { display: false },
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
                        legend: {
                            labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 12 } }
                        },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            titleColor: '#ffffff',
                            bodyColor: '#cbd5e1',
                            padding: 10,
                            cornerRadius: 8
                        }
                    }
                }
            });

            // 2. Model Share Doughnut
            new Chart(document.getElementById('modelShareChart').getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: models,
                    datasets: [{
                        data: models.map(m => modelTokenCounts[m]),
                        backgroundColor: models.map(m => modelColorMap[m]),
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: '#334155', boxWidth: 10, usePointStyle: true, padding: 14, font: { size: 12 } }
                        },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            titleColor: '#ffffff',
                            bodyColor: '#cbd5e1',
                            padding: 10,
                            cornerRadius: 8
                        }
                    }
                }
            });

            // 3. Requests Bar Chart
            const requestDatasets = models.map(m => {
                return {
                    label: m,
                    data: dates.map(d => (rawData[d][m] ? rawData[d][m].requests || 0 : 0)),
                    backgroundColor: modelColorMap[m],
                    borderRadius: 4
                };
            });

            new Chart(document.getElementById('requestsChart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: dates,
                    datasets: requestDatasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    maxBarThickness: 48,
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: '#64748b', font: { size: 12 } }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            ticks: { color: '#64748b', stepSize: 1, font: { size: 11 } }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#334155', boxWidth: 10, usePointStyle: true, font: { size: 12 } }
                        },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            titleColor: '#ffffff',
                            bodyColor: '#cbd5e1',
                            padding: 10,
                            cornerRadius: 8
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
