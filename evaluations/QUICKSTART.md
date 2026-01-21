# Evaluation Framework - Quick Start

## 1-Minute Setup

```bash
# Run setup script
./scripts/setup_evaluation.sh

# Activate virtual environment
source evaluations/venv/bin/activate

# Run example workflow
python evaluations/example_workflow.py
```

## Common Commands

### Run a Benchmark

```bash
python scripts/run_benchmarks.py --model "my_model"
```

### Start Dashboard

```bash
# Open in browser
open evaluations/dashboard.html

# Or with local server
cd evaluations
python -m http.server 8000
# Visit: http://localhost:8000/dashboard.html
```

### Continuous Evaluation

```bash
# Run service with file watching
python scripts/continuous_eval.py --watch

# Run once and exit
python scripts/continuous_eval.py --once
```

## File Structure

```
evaluations/
├── screenshot_eval.py          # Visual validation core
├── advanced_eval.jsonl         # 50 test questions
├── dashboard.html              # Live dashboard
├── example_workflow.py         # Complete demo
├── eval_config.json           # Model configuration
├── requirements.txt           # Dependencies
├── README.md                  # Full documentation
└── QUICKSTART.md             # This file

scripts/
├── run_benchmarks.py         # Benchmark runner
├── continuous_eval.py        # Continuous service
└── setup_evaluation.sh       # Setup script
```

## Key Features

- **Screenshot Validation**: Captures and compares visual outputs
- **50 Test Cases**: Covers 12 categories from code generation to security
- **Real-time Dashboard**: Auto-refreshing charts and leaderboard
- **Continuous Evaluation**: Auto-runs tests when models or suite changes
- **Chart Generation**: Matplotlib-based comparison visualizations

## Next Steps

1. **Configure Models**: Edit `evaluations/eval_config.json`
2. **Add Test Cases**: Edit `evaluations/advanced_eval.jsonl`
3. **Integrate APIs**: Extend `run_benchmarks.py` with your model APIs
4. **Setup Webhooks**: Add notification URLs to config
5. **Customize Dashboard**: Edit `dashboard.html` styling/charts

## Test Categories

1. Code Generation (10)
2. Debugging (8)
3. Architecture (6)
4. System Analysis (5)
5. Algorithms (4)
6. Web Development (4)
7. Database (3)
8. API Design (2)
9. Security (2)
10. Testing (2)
11. Optimization (2)
12. Data Structures (2)

## Example Integration

```python
# Custom evaluation logic
from scripts.run_benchmarks import BenchmarkRunner

class MyBenchmarkRunner(BenchmarkRunner):
    def _evaluate_question(self, model_name, question, endpoint, api_key, timeout):
        # 1. Send prompt to your model
        response = your_model_api(question['prompt'])

        # 2. Check if response contains expected features
        is_correct = all(
            feature in response.lower()
            for feature in question['expected_features']
        )

        # 3. Return result
        return is_correct, eval_time

# Run benchmark
runner = MyBenchmarkRunner()
result = runner.run_benchmark(model_name="your_model")
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Chrome driver missing | `brew install chromedriver` |
| Import errors | `pip install -r requirements.txt` |
| Dashboard not updating | Check `results/leaderboard.json` exists |
| File watching not working | Install watchdog: `pip install watchdog` |

## Documentation

- Full docs: `evaluations/README.md`
- Code comments: See individual Python files
- Example usage: `evaluations/example_workflow.py`

## Support

For detailed instructions and API reference, see the full README.
