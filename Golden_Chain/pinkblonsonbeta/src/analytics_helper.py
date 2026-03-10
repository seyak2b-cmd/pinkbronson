
import os
import json
import webbrowser
from datetime import datetime, timedelta

class AnalyticsHelper:
    def __init__(self, project_root):
        self.project_root = project_root
        self.data_dir = os.path.join(project_root, 'data')
        self.output_dir = os.path.join(project_root, 'output')
        self.log_file = os.path.join(self.data_dir, 'usage_log.json')
        self.report_file = os.path.join(self.output_dir, 'analytics_report.html')

    def generate_and_open_report(self):
        """Generate HTML report and open it."""
        try:
            # 1. Load Data
            data = []
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 2. Process Data
            if not data:
                return False, "No data found."

            # Calculate daily totals
            daily_stats = {} # "YYYY-MM-DD": {total: 0, prompt: 0, candidate: 0}
            model_stats = {} # "model_name": total_tokens
            
            total_cost_est = 0.0
            # Rough pricing (Gemini 1.5 Flash) - adjust as needed
            # Input: $0.075 / 1M tokens
            # Output: $0.30 / 1M tokens
            PRICE_IN_MILLION = 0.075
            PRICE_OUT_MILLION = 0.30
            
            for entry in data:
                ts_str = entry.get('timestamp', '')[:10] # YYYY-MM-DD
                model = entry.get('model', 'unknown')
                p_tok = entry.get('prompt_tokens', 0)
                c_tok = entry.get('candidate_tokens', 0)
                total = p_tok + c_tok
                
                # Daily
                if ts_str not in daily_stats:
                    daily_stats[ts_str] = {'total': 0, 'prompt': 0, 'candidate': 0}
                daily_stats[ts_str]['total'] += total
                daily_stats[ts_str]['prompt'] += p_tok
                daily_stats[ts_str]['candidate'] += c_tok
                
                # Model
                if model not in model_stats:
                    model_stats[model] = 0
                model_stats[model] += total
                
                # Cost
                cost = (p_tok / 1_000_000 * PRICE_IN_MILLION) + (c_tok / 1_000_000 * PRICE_OUT_MILLION)
                total_cost_est += cost

            # Sort dates
            sorted_dates = sorted(daily_stats.keys())
            daily_totals = [daily_stats[d]['total'] for d in sorted_dates]
            
            # Prepare JSON for JS
            js_dates = json.dumps(sorted_dates)
            js_daily_totals = json.dumps(daily_totals)
            js_models = json.dumps(list(model_stats.keys()))
            js_model_values = json.dumps(list(model_stats.values()))
            
            # 3. Generate HTML
            html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aquaread Analytics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }}
        .container {{ max_width: 1000px; margin: 0 auto; }}
        .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        h1 {{ color: #1a1b26; }}
        h2 {{ color: #414868; font-size: 1.2rem; }}
        .stat-box {{ display: inline-block; padding: 15px; background: #e0e7ff; border-radius: 8px; margin-right: 15px; }}
        .stat-value {{ font-size: 1.5rem; font-weight: bold; color: #3730a3; }}
        .stat-label {{ color: #6b7280; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📊 API Usage Analytics</h1>
            <div class="stat-box">
                <div class="stat-value">{sum(daily_totals):,}</div>
                <div class="stat-label">Total Tokens</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">${total_cost_est:.4f}</div>
                <div class="stat-label">Est. Cost (USD)</div>
            </div>
             <div class="stat-box" style="background: #ffecd1;">
                <div class="stat-value">{len(data)}</div>
                <div class="stat-label">Total Requests</div>
            </div>
        </div>

        <div class="card">
            <h2>📅 Daily Usage (Tokens)</h2>
            <canvas id="dailyChart"></canvas>
        </div>

        <div class="card">
            <h2>🤖 Usage by Model</h2>
            <div style="height: 300px; width: 300px; margin: 0 auto;">
                <canvas id="modelChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        // Daily Chart
        new Chart(document.getElementById('dailyChart'), {{
            type: 'bar',
            data: {{
                labels: {js_dates},
                datasets: [{{
                    label: 'Total Tokens',
                    data: {js_daily_totals},
                    backgroundColor: '#7aa2f7',
                    borderRadius: 5
                }}]
            }},
            options: {{ responsive: true }}
        }});

        // Model Chart
        new Chart(document.getElementById('modelChart'), {{
            type: 'doughnut',
            data: {{
                labels: {js_models},
                datasets: [{{
                    data: {js_model_values},
                    backgroundColor: ['#7aa2f7', '#bb9af7', '#9ece6a', '#f7768e', '#e0af68']
                }}]
            }}
        }});
    </script>
</body>
</html>
            """
            
            with open(self.report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            # 4. Open Browser
            webbrowser.open(f'file:///{self.report_file}')
            return True, "Report opened."
            
        except Exception as e:
            return False, str(e)
