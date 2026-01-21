#!/usr/bin/env python3
"""
Example workflow demonstrating the complete evaluation framework.

This script shows how to:
1. Generate reference screenshots
2. Run evaluations with visual validation
3. Generate comparison charts
4. Update the dashboard
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluations.screenshot_eval import ScreenshotEvaluator
from scripts.run_benchmarks import BenchmarkRunner


def generate_example_references():
    """Generate reference screenshots for example test cases."""
    print("\n" + "="*60)
    print("Step 1: Generating Reference Screenshots")
    print("="*60 + "\n")

    evaluator = ScreenshotEvaluator()

    # Example HTML test cases
    test_cases = [
        {
            'id': 'web_example_001',
            'code': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
        }
        .card {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 400px;
        }
        h1 {
            color: #667eea;
            margin: 0 0 20px 0;
            font-size: 2em;
        }
        p {
            color: #666;
            line-height: 1.6;
        }
        .button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 20px;
            transition: transform 0.2s;
        }
        .button:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Welcome</h1>
        <p>This is an example reference screenshot for visual validation testing.</p>
        <button class="button">Get Started</button>
    </div>
</body>
</html>
            ''',
            'language': 'html',
            'type': 'html'
        },
        {
            'id': 'web_example_002',
            'code': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .dashboard {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            color: #999;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>Dashboard Example</h1>
        </div>
        <div class="grid">
            <div class="stat-card">
                <div class="stat-value">1,234</div>
                <div class="stat-label">TOTAL USERS</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">567</div>
                <div class="stat-label">ACTIVE NOW</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">89%</div>
                <div class="stat-label">ACCURACY</div>
            </div>
        </div>
    </div>
</body>
</html>
            ''',
            'language': 'html',
            'type': 'html'
        }
    ]

    evaluator.generate_reference_screenshots(test_cases)
    print(f"\n✓ Generated {len(test_cases)} reference screenshots")


def run_example_evaluation():
    """Run an example evaluation with visual validation."""
    print("\n" + "="*60)
    print("Step 2: Running Example Evaluation")
    print("="*60 + "\n")

    evaluator = ScreenshotEvaluator()

    # Test code to evaluate (slight variation from reference)
    test_html = '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
        }
        .card {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 400px;
        }
        h1 {
            color: #667eea;
            margin: 0 0 20px 0;
            font-size: 2em;
        }
        p {
            color: #666;
            line-height: 1.6;
        }
        .button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Welcome</h1>
        <p>This is an example reference screenshot for visual validation testing.</p>
        <button class="button">Get Started</button>
    </div>
</body>
</html>
    '''

    # Check if reference exists
    ref_path = Path("evaluations/screenshots/references/web_example_001_reference.png")

    result = evaluator.evaluate_code_output(
        eval_id="example_eval_001",
        model_name="example_model",
        code=test_html,
        language="html",
        expected_output_type="html",
        reference_screenshot=str(ref_path) if ref_path.exists() else None,
        metadata={
            "category": "web_development",
            "test_type": "visual_validation"
        }
    )

    print(f"\n✓ Evaluation Results:")
    print(f"  Execution Success: {result.execution_success}")
    print(f"  Visual Test Passed: {result.visual_passed}")
    if result.similarity_score is not None:
        print(f"  Similarity Score: {result.similarity_score:.2%}")
    print(f"  Screenshot: {result.screenshot_path}")


def run_example_benchmark():
    """Run an example benchmark."""
    print("\n" + "="*60)
    print("Step 3: Running Example Benchmark")
    print("="*60 + "\n")

    runner = BenchmarkRunner()

    # Note: This will use placeholder evaluation logic
    # In production, integrate with actual model APIs
    result = runner.run_benchmark(
        model_name="example_model",
        enable_visual_tests=False  # Disable for quick demo
    )

    print(f"\n✓ Benchmark Complete:")
    print(f"  Model: {result.model_name}")
    print(f"  Accuracy: {result.accuracy*100:.2f}%")
    print(f"  Questions: {result.correct_answers}/{result.total_questions}")
    print(f"  Avg Time: {result.average_time_per_question:.2f}s")


def generate_example_charts():
    """Generate example comparison charts."""
    print("\n" + "="*60)
    print("Step 4: Generating Comparison Charts")
    print("="*60 + "\n")

    runner = BenchmarkRunner()

    # This will only work if there are existing results
    results = runner._load_all_results()

    if results:
        runner.generate_comparison_charts()
        print(f"\n✓ Generated charts for {len(results)} models")
        print(f"  Location: evaluations/charts/")
    else:
        print("\n⚠ No results found to generate charts")
        print("  Run benchmarks first to generate results")


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "="*60)
    print("Example Workflow Complete!")
    print("="*60 + "\n")

    print("Next steps:")
    print("\n1. View the dashboard:")
    print("   open evaluations/dashboard.html")
    print("\n2. Configure your models:")
    print("   Edit evaluations/eval_config.json")
    print("\n3. Run a real benchmark:")
    print("   python scripts/run_benchmarks.py --model your_model")
    print("\n4. Start continuous evaluation:")
    print("   python scripts/continuous_eval.py --watch")
    print("\n5. Add more test cases:")
    print("   Edit evaluations/advanced_eval.jsonl")
    print("\nFor full documentation, see evaluations/README.md")
    print("")


def main():
    """Run the complete example workflow."""
    print("\n" + "="*60)
    print("Evaluation Framework Example Workflow")
    print("="*60)

    try:
        # Step 1: Generate references
        generate_example_references()

        # Step 2: Run evaluation
        run_example_evaluation()

        # Step 3: Run benchmark
        run_example_benchmark()

        # Step 4: Generate charts
        generate_example_charts()

        # Print next steps
        print_next_steps()

    except Exception as e:
        print(f"\n✗ Error during workflow: {e}")
        print("\nTroubleshooting:")
        print("1. Install dependencies: pip install -r evaluations/requirements.txt")
        print("2. Check Chrome/ChromeDriver installation")
        print("3. Review error details above")
        sys.exit(1)


if __name__ == "__main__":
    main()
