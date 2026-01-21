# Advanced Evaluation Framework

A comprehensive, production-ready evaluation system with visual validation, automated benchmarking, and real-time dashboards.

## Features

- **Screenshot-Based Evaluation**: Visual validation of model outputs with browser/terminal capture
- **50+ Test Cases**: Multi-modal evaluation suite covering code generation, debugging, architecture, and more
- **Automated Benchmarking**: Run evaluations across multiple models with automated result tracking
- **Real-Time Dashboard**: Live HTML dashboard with charts, leaderboard, and category breakdowns
- **Continuous Evaluation**: Background service that auto-runs evaluations and sends notifications
- **Chart Generation**: Matplotlib-based comparison charts and visualizations

## Installation

### 1. Install Dependencies

```bash
cd evaluations
pip install -r requirements.txt
```

### 2. Install Chrome Driver (for screenshot evaluation)

```bash
# macOS
brew install chromedriver

# Or use webdriver-manager (automatic)
pip install webdriver-manager
```

### 3. Verify Installation

```bash
python screenshot_eval.py  # Should run example evaluation
```

## Quick Start

### Run a Single Benchmark

```bash
python ../scripts/run_benchmarks.py \
    --model "gpt-4" \
    --endpoint "https://api.openai.com/v1" \
    --api-key "your-key" \
    --charts
```

### Start Continuous Evaluation Service

```bash
python ../scripts/continuous_eval.py \
    --config eval_config.json \
    --interval 300 \
    --watch
```

### View Dashboard

```bash
# Open dashboard in browser
open dashboard.html

# Or start local server
python -m http.server 8000
# Then visit: http://localhost:8000/dashboard.html
```

## Architecture

```
evaluations/
├── screenshot_eval.py      # Screenshot capture and comparison
├── advanced_eval.jsonl     # 50 evaluation questions
├── dashboard.html          # Real-time visualization dashboard
├── requirements.txt        # Python dependencies
├── screenshots/            # Captured screenshots
│   └── references/         # Reference screenshots for comparison
├── results/                # Evaluation results (JSON)
│   ├── leaderboard.json   # Model rankings
│   ├── eval_history.json  # Evaluation history
│   └── benchmark_*.json   # Individual results
├── charts/                 # Generated comparison charts
│   ├── accuracy_comparison.png
│   ├── category_comparison.png
│   ├── time_vs_accuracy.png
│   └── leaderboard.png
└── data/                   # Additional evaluation data

scripts/
├── run_benchmarks.py       # Automated benchmark runner
└── continuous_eval.py      # Continuous evaluation service
```

## Usage Guide

### 1. Screenshot Evaluation

Capture and compare visual outputs:

```python
from evaluations.screenshot_eval import ScreenshotEvaluator

evaluator = ScreenshotEvaluator()

# Evaluate HTML output
html_code = """<html>...</html>"""
result = evaluator.evaluate_code_output(
    eval_id="test_001",
    model_name="my_model",
    code=html_code,
    language="html",
    expected_output_type="html",
    reference_screenshot="screenshots/references/test_001_ref.png"
)

print(f"Visual test passed: {result.visual_passed}")
print(f"Similarity score: {result.similarity_score}")
```

### 2. Benchmark Runner

Run comprehensive benchmarks:

```bash
# Basic benchmark
python scripts/run_benchmarks.py --model "claude-3"

# With API endpoint
python scripts/run_benchmarks.py \
    --model "gpt-4-turbo" \
    --endpoint "https://api.openai.com/v1/chat/completions" \
    --api-key "$OPENAI_API_KEY"

# Custom eval suite
python scripts/run_benchmarks.py \
    --model "llama-2" \
    --eval-suite "custom_eval.jsonl"

# Generate comparison charts
python scripts/run_benchmarks.py \
    --model "gemini-pro" \
    --charts

# Compare specific models
python scripts/run_benchmarks.py \
    --model "new_model" \
    --compare-models "gpt-4" "claude-3" "gemini-pro"
```

### 3. Continuous Evaluation

Set up automated evaluation:

**Step 1: Configure models**

Edit `eval_config.json`:

```json
{
  "models": [
    {
      "name": "gpt-4-turbo",
      "endpoint": "https://api.openai.com/v1",
      "api_key": "sk-...",
      "enabled": true,
      "schedule": "on_change"
    },
    {
      "name": "claude-3-opus",
      "endpoint": "https://api.anthropic.com/v1",
      "api_key": "sk-ant-...",
      "enabled": true,
      "schedule": "daily"
    }
  ],
  "notification_settings": {
    "webhook_url": "https://hooks.slack.com/services/...",
    "notify_on_completion": true,
    "notify_on_error": true,
    "notify_on_improvement": true
  }
}
```

**Step 2: Start service**

```bash
# Run continuously with 5-minute checks
python scripts/continuous_eval.py

# Custom check interval (seconds)
python scripts/continuous_eval.py --interval 600

# Enable file watching for immediate updates
python scripts/continuous_eval.py --watch

# Run once and exit
python scripts/continuous_eval.py --once

# With webhook notifications
python scripts/continuous_eval.py --webhook "https://your-webhook-url"
```

### 4. Dashboard

The dashboard auto-refreshes every 30 seconds and displays:

- **Summary Stats**: Total models, tests, average accuracy, top performer
- **Accuracy Chart**: Bar chart comparing model accuracies
- **Category Performance**: Radar chart showing strengths by category
- **Leaderboard**: Ranked table with detailed metrics
- **History Trend**: Line chart showing accuracy over time

**To customize refresh interval**, edit `dashboard.html`:

```javascript
const REFRESH_INTERVAL = 30000; // milliseconds
```

## Evaluation Categories

The evaluation suite covers:

1. **Code Generation** (10 questions)
   - Easy: Basic functions, simple algorithms
   - Medium: React components, API endpoints
   - Hard: Data structures, complex algorithms

2. **Debugging** (8 questions)
   - Identify bugs, fix issues, explain problems
   - Memory leaks, race conditions, security vulnerabilities

3. **Architecture** (6 questions)
   - System design, microservices, scaling
   - Diagrams and documentation

4. **System Analysis** (5 questions)
   - Complexity analysis, performance, security
   - Tradeoffs and best practices

5. **Algorithms** (4 questions)
   - Classic algorithms, optimization
   - Time/space complexity

6. **Web Development** (4 questions)
   - HTML/CSS/JS, responsive design
   - Forms, animations, interactivity

7. **Database** (3 questions)
   - SQL queries, schema design
   - Optimization

8. **API Design** (2 questions)
   - RESTful design, pagination

9. **Security** (2 questions)
   - Authentication, vulnerability prevention

10. **Testing** (2 questions)
    - Unit tests, integration tests

11. **Optimization** (2 questions)
    - Algorithm improvement, query optimization

12. **Data Structures** (2 questions)
    - Advanced structures, thread safety

## Adding New Test Cases

Edit `advanced_eval.jsonl` and add a new line:

```json
{
  "id": "custom_001",
  "category": "code_generation",
  "difficulty": "medium",
  "prompt": "Your test prompt here",
  "expected_features": ["feature1", "feature2"],
  "language": "python",
  "visual_check": false,
  "test_cases": [
    {"input": "test input", "output": "expected output"}
  ]
}
```

**Fields:**
- `id`: Unique identifier
- `category`: One of the supported categories
- `difficulty`: "easy", "medium", or "hard"
- `prompt`: Question text
- `expected_features`: List of features to check
- `language`: Programming language
- `visual_check`: Boolean, whether to capture screenshot
- `output_type`: "html", "terminal", or "console" (if visual_check=true)
- `test_cases`: Optional list of input/output pairs

## Visual Validation

For visual tests, you can generate reference screenshots:

```python
from evaluations.screenshot_eval import ScreenshotEvaluator

evaluator = ScreenshotEvaluator()

test_cases = [
    {
        'id': 'ui_001',
        'code': '<html>...</html>',
        'language': 'html',
        'type': 'html'
    }
]

evaluator.generate_reference_screenshots(test_cases)
```

Reference screenshots are stored in `screenshots/references/` and used for comparison.

## Chart Generation

Charts are automatically generated and saved to `charts/`:

1. **accuracy_comparison.png**: Bar chart of model accuracies
2. **category_comparison.png**: Grouped bars by category
3. **time_vs_accuracy.png**: Scatter plot of speed vs accuracy
4. **leaderboard.png**: Visual leaderboard of top 10 models

Generate charts manually:

```python
from scripts.run_benchmarks import BenchmarkRunner

runner = BenchmarkRunner()
runner.generate_comparison_charts(model_names=["gpt-4", "claude-3"])
```

## Notifications

Set up webhook notifications for:
- Evaluation completion
- Errors during evaluation
- Performance improvements

**Slack webhook example:**

```bash
python scripts/continuous_eval.py \
    --webhook "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Custom webhook payload:**

```json
{
  "text": "Evaluation completed for gpt-4-turbo",
  "timestamp": "2024-01-14T15:30:00",
  "result": {
    "success": true,
    "model": "gpt-4-turbo"
  }
}
```

## Advanced Configuration

### Custom Evaluation Logic

Extend `BenchmarkRunner` to add custom evaluation:

```python
from scripts.run_benchmarks import BenchmarkRunner

class CustomBenchmarkRunner(BenchmarkRunner):
    def _evaluate_question(self, model_name, question, endpoint, api_key, timeout):
        # Your custom evaluation logic
        # 1. Send prompt to model
        # 2. Get response
        # 3. Validate response
        # 4. Return (is_correct, eval_time)
        pass
```

### Integration with Model APIs

Example integration with OpenAI API:

```python
import openai

def evaluate_with_openai(question):
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": question["prompt"]}],
        temperature=0.7
    )

    answer = response.choices[0].message.content

    # Evaluate answer against expected_features
    is_correct = all(
        feature in answer.lower()
        for feature in question["expected_features"]
    )

    return is_correct
```

## Performance Tips

1. **Parallel Evaluation**: Run multiple models in parallel
2. **Caching**: Cache model responses to avoid redundant API calls
3. **Sampling**: For quick tests, sample a subset of questions
4. **Visual Tests**: Disable visual tests with `--no-visual` for faster runs
5. **Chart Generation**: Generate charts less frequently (they're expensive)

## Troubleshooting

### Chrome Driver Issues

```bash
# Update Chrome driver
brew upgrade chromedriver

# Or reinstall
brew reinstall chromedriver

# Allow in System Preferences > Security & Privacy
xattr -d com.apple.quarantine /usr/local/bin/chromedriver
```

### Missing Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Check installation
python -c "import selenium; import matplotlib; import PIL; print('OK')"
```

### Dashboard Not Updating

1. Check that results are being written to `results/`
2. Verify `leaderboard.json` exists
3. Check browser console for JavaScript errors
4. Try force refresh (Cmd+Shift+R or Ctrl+Shift+R)

### File Watching Not Working

```bash
# Install watchdog
pip install watchdog

# Check if it's enabled
python scripts/continuous_eval.py --watch
# Should see: "File watcher enabled for evaluation suite"
```

## API Reference

### ScreenshotEvaluator

```python
evaluator = ScreenshotEvaluator(screenshots_dir="evaluations/screenshots")

# Capture browser screenshot
success, error = evaluator.capture_browser_screenshot(
    html_content="<html>...</html>",
    output_path="output.png",
    wait_time=2.0,
    viewport_size=(1280, 720)
)

# Capture terminal screenshot
success, error = evaluator.capture_terminal_screenshot(
    code="print('hello')",
    language="python",
    output_path="output.png",
    timeout=10.0
)

# Compare screenshots
similarity = evaluator.compare_screenshots(
    "image1.png",
    "image2.png"
)  # Returns 0.0 to 1.0

# Evaluate code output
result = evaluator.evaluate_code_output(
    eval_id="test_001",
    model_name="gpt-4",
    code="<html>...</html>",
    language="html",
    expected_output_type="html",
    reference_screenshot="ref.png",
    metadata={"category": "web_dev"}
)
```

### BenchmarkRunner

```python
runner = BenchmarkRunner(
    eval_suite_path="evaluations/advanced_eval.jsonl",
    results_dir="evaluations/results",
    charts_dir="evaluations/charts"
)

# Run benchmark
result = runner.run_benchmark(
    model_name="gpt-4",
    model_endpoint="https://api.openai.com/v1",
    api_key="sk-...",
    timeout=30.0,
    enable_visual_tests=True
)

# Generate charts
runner.generate_comparison_charts(
    model_names=["gpt-4", "claude-3"]
)
```

### EvaluationService

```python
service = EvaluationService(
    config_file="evaluations/eval_config.json",
    eval_suite="evaluations/advanced_eval.jsonl",
    check_interval=300,
    notification_webhook="https://hooks.slack.com/..."
)

# Run once
service.run_once()

# Run continuously
service.run_forever()

# Manual evaluation
from scripts.continuous_eval import ModelConfig
model = ModelConfig(name="gpt-4", endpoint="https://...")
result = service.run_evaluation(model)
```

## Contributing

To add new features:

1. Add test cases to `advanced_eval.jsonl`
2. Extend evaluation logic in `run_benchmarks.py`
3. Update dashboard charts in `dashboard.html`
4. Add documentation to this README

## License

This evaluation framework is part of the Oracle of Secrets project.

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the code comments for implementation details
- Test with the example evaluations provided
