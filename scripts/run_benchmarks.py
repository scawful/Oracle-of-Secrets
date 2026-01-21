#!/usr/bin/env python3
"""
Automated benchmark runner for model evaluation.

This script runs evaluation suites across multiple models, captures results,
generates comparison charts, and maintains a leaderboard.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Install with: pip install matplotlib")

try:
    from evaluations.screenshot_eval import ScreenshotEvaluator
    SCREENSHOT_EVAL_AVAILABLE = True
except ImportError:
    SCREENSHOT_EVAL_AVAILABLE = False


@dataclass
class BenchmarkResult:
    """Result from a complete benchmark run."""
    model_name: str
    timestamp: str
    total_questions: int
    correct_answers: int
    accuracy: float
    category_scores: Dict[str, Dict[str, float]]
    average_time_per_question: float
    visual_tests_passed: int
    visual_tests_total: int
    metadata: Dict[str, Any]


class BenchmarkRunner:
    """Orchestrates benchmark execution across models and evaluation suites."""

    def __init__(
        self,
        eval_suite_path: str = "evaluations/advanced_eval.jsonl",
        results_dir: str = "evaluations/results",
        charts_dir: str = "evaluations/charts"
    ):
        """Initialize the benchmark runner.

        Args:
            eval_suite_path: Path to evaluation suite JSONL file
            results_dir: Directory to store results
            charts_dir: Directory to store generated charts
        """
        self.eval_suite_path = Path(eval_suite_path)
        self.results_dir = Path(results_dir)
        self.charts_dir = Path(charts_dir)

        # Create directories
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)

        # Initialize screenshot evaluator if available
        self.screenshot_eval = None
        if SCREENSHOT_EVAL_AVAILABLE:
            self.screenshot_eval = ScreenshotEvaluator()

        # Load evaluation suite
        self.eval_questions = self._load_eval_suite()

    def _load_eval_suite(self) -> List[Dict]:
        """Load evaluation questions from JSONL file."""
        questions = []
        if not self.eval_suite_path.exists():
            print(f"Warning: Eval suite not found at {self.eval_suite_path}")
            return questions

        with open(self.eval_suite_path, 'r') as f:
            for line in f:
                if line.strip():
                    questions.append(json.loads(line))

        print(f"Loaded {len(questions)} evaluation questions")
        return questions

    def run_benchmark(
        self,
        model_name: str,
        model_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        enable_visual_tests: bool = True
    ) -> BenchmarkResult:
        """Run complete benchmark suite for a model.

        Args:
            model_name: Name/identifier of the model
            model_endpoint: API endpoint (if using API-based model)
            api_key: API key for authentication
            timeout: Timeout per question in seconds
            enable_visual_tests: Whether to run visual validation tests

        Returns:
            BenchmarkResult with complete evaluation metrics
        """
        print(f"\n{'='*60}")
        print(f"Running benchmark for: {model_name}")
        print(f"{'='*60}\n")

        start_time = time.time()
        correct_count = 0
        visual_passed = 0
        visual_total = 0
        category_results = {}

        for i, question in enumerate(self.eval_questions, 1):
            print(f"Question {i}/{len(self.eval_questions)}: {question['id']}")

            # Run evaluation for this question
            is_correct, eval_time = self._evaluate_question(
                model_name,
                question,
                model_endpoint,
                api_key,
                timeout
            )

            if is_correct:
                correct_count += 1

            # Track category performance
            category = question['category']
            if category not in category_results:
                category_results[category] = {'correct': 0, 'total': 0}

            category_results[category]['total'] += 1
            if is_correct:
                category_results[category]['correct'] += 1

            # Visual validation if applicable
            if enable_visual_tests and question.get('visual_check'):
                visual_total += 1
                # Note: Visual validation would require actual model output
                # This is a placeholder for the integration
                print(f"  [Visual test - would validate here]")

        # Calculate metrics
        total_time = time.time() - start_time
        accuracy = correct_count / len(self.eval_questions) if self.eval_questions else 0
        avg_time = total_time / len(self.eval_questions) if self.eval_questions else 0

        # Calculate category scores
        category_scores = {}
        for category, results in category_results.items():
            category_scores[category] = {
                'accuracy': results['correct'] / results['total'] if results['total'] > 0 else 0,
                'correct': results['correct'],
                'total': results['total']
            }

        result = BenchmarkResult(
            model_name=model_name,
            timestamp=datetime.now().isoformat(),
            total_questions=len(self.eval_questions),
            correct_answers=correct_count,
            accuracy=accuracy,
            category_scores=category_scores,
            average_time_per_question=avg_time,
            visual_tests_passed=visual_passed,
            visual_tests_total=visual_total,
            metadata={
                'eval_suite': str(self.eval_suite_path),
                'total_time': total_time,
                'endpoint': model_endpoint or 'local'
            }
        )

        # Save results
        self._save_result(result)

        print(f"\n{'='*60}")
        print(f"Benchmark Complete!")
        print(f"Accuracy: {accuracy*100:.2f}% ({correct_count}/{len(self.eval_questions)})")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Avg Time/Question: {avg_time:.2f}s")
        print(f"{'='*60}\n")

        return result

    def _evaluate_question(
        self,
        model_name: str,
        question: Dict,
        endpoint: Optional[str],
        api_key: Optional[str],
        timeout: float
    ) -> tuple[bool, float]:
        """Evaluate a single question.

        Args:
            model_name: Name of the model
            question: Question dictionary
            endpoint: API endpoint
            api_key: API key
            timeout: Timeout in seconds

        Returns:
            Tuple of (is_correct, evaluation_time)
        """
        start = time.time()

        # TODO: Integrate with actual model inference
        # For now, this is a placeholder that would need to:
        # 1. Send prompt to model
        # 2. Get response
        # 3. Evaluate response against expected features
        # 4. Return whether it passed

        # Placeholder: randomly mark some as correct for demonstration
        import random
        is_correct = random.random() > 0.3  # 70% success rate for demo

        eval_time = time.time() - start
        return is_correct, eval_time

    def _save_result(self, result: BenchmarkResult):
        """Save benchmark result to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = self.results_dir / f"benchmark_{result.model_name}_{timestamp}.json"

        with open(result_file, 'w') as f:
            json.dump(asdict(result), f, indent=2)

        # Also append to leaderboard
        self._update_leaderboard(result)

        print(f"Results saved to: {result_file}")

    def _update_leaderboard(self, result: BenchmarkResult):
        """Update the leaderboard with new results."""
        leaderboard_file = self.results_dir / "leaderboard.json"

        # Load existing leaderboard
        leaderboard = []
        if leaderboard_file.exists():
            with open(leaderboard_file, 'r') as f:
                leaderboard = json.load(f)

        # Add new result
        leaderboard.append({
            'model_name': result.model_name,
            'timestamp': result.timestamp,
            'accuracy': result.accuracy,
            'total_questions': result.total_questions,
            'correct_answers': result.correct_answers,
            'avg_time': result.average_time_per_question,
            'visual_tests_passed': result.visual_tests_passed,
            'visual_tests_total': result.visual_tests_total
        })

        # Sort by accuracy (descending)
        leaderboard.sort(key=lambda x: x['accuracy'], reverse=True)

        # Save updated leaderboard
        with open(leaderboard_file, 'w') as f:
            json.dump(leaderboard, f, indent=2)

    def generate_comparison_charts(self, model_names: Optional[List[str]] = None):
        """Generate comparison charts from benchmark results.

        Args:
            model_names: List of model names to compare (None = all models)
        """
        if not MATPLOTLIB_AVAILABLE:
            print("matplotlib not available - skipping chart generation")
            return

        print("\nGenerating comparison charts...")

        # Load all results
        results = self._load_all_results()

        if not results:
            print("No results found to chart")
            return

        # Filter by model names if specified
        if model_names:
            results = [r for r in results if r['model_name'] in model_names]

        # Generate different chart types
        self._create_accuracy_bar_chart(results)
        self._create_category_comparison(results)
        self._create_time_vs_accuracy_scatter(results)
        self._create_leaderboard_chart(results)

        print(f"Charts saved to: {self.charts_dir}")

    def _load_all_results(self) -> List[Dict]:
        """Load all benchmark results."""
        results = []
        for result_file in self.results_dir.glob("benchmark_*.json"):
            with open(result_file, 'r') as f:
                results.append(json.load(f))
        return results

    def _create_accuracy_bar_chart(self, results: List[Dict]):
        """Create bar chart comparing model accuracies."""
        plt.figure(figsize=(12, 6))

        models = [r['model_name'] for r in results]
        accuracies = [r['accuracy'] * 100 for r in results]

        plt.bar(models, accuracies, color='#667eea')
        plt.xlabel('Model')
        plt.ylabel('Accuracy (%)')
        plt.title('Model Accuracy Comparison')
        plt.ylim(0, 100)
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()

        plt.savefig(self.charts_dir / 'accuracy_comparison.png', dpi=300)
        plt.close()

    def _create_category_comparison(self, results: List[Dict]):
        """Create grouped bar chart comparing performance by category."""
        # Get all categories
        all_categories = set()
        for result in results:
            all_categories.update(result['category_scores'].keys())

        if not all_categories:
            return

        categories = sorted(all_categories)

        plt.figure(figsize=(14, 7))

        x = range(len(categories))
        width = 0.8 / len(results) if results else 0.8

        for i, result in enumerate(results):
            scores = [
                result['category_scores'].get(cat, {}).get('accuracy', 0) * 100
                for cat in categories
            ]
            offset = (i - len(results)/2) * width
            plt.bar([xi + offset for xi in x], scores, width, label=result['model_name'])

        plt.xlabel('Category')
        plt.ylabel('Accuracy (%)')
        plt.title('Performance by Category')
        plt.xticks(x, categories, rotation=45, ha='right')
        plt.legend()
        plt.ylim(0, 100)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()

        plt.savefig(self.charts_dir / 'category_comparison.png', dpi=300)
        plt.close()

    def _create_time_vs_accuracy_scatter(self, results: List[Dict]):
        """Create scatter plot of time vs accuracy."""
        plt.figure(figsize=(10, 6))

        times = [r['average_time_per_question'] for r in results]
        accuracies = [r['accuracy'] * 100 for r in results]
        labels = [r['model_name'] for r in results]

        plt.scatter(times, accuracies, s=100, alpha=0.6, c='#667eea')

        for i, label in enumerate(labels):
            plt.annotate(label, (times[i], accuracies[i]),
                        xytext=(5, 5), textcoords='offset points')

        plt.xlabel('Average Time per Question (s)')
        plt.ylabel('Accuracy (%)')
        plt.title('Time vs Accuracy Trade-off')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        plt.savefig(self.charts_dir / 'time_vs_accuracy.png', dpi=300)
        plt.close()

    def _create_leaderboard_chart(self, results: List[Dict]):
        """Create visual leaderboard chart."""
        # Sort by accuracy
        sorted_results = sorted(results, key=lambda x: x['accuracy'], reverse=True)
        top_10 = sorted_results[:10]

        plt.figure(figsize=(12, 8))

        models = [r['model_name'] for r in top_10]
        accuracies = [r['accuracy'] * 100 for r in top_10]

        colors = plt.cm.viridis(range(len(top_10)))

        bars = plt.barh(models, accuracies, color=colors)

        plt.xlabel('Accuracy (%)')
        plt.title('Top 10 Models - Leaderboard')
        plt.xlim(0, 100)
        plt.gca().invert_yaxis()

        # Add value labels
        for i, bar in enumerate(bars):
            width = bar.get_width()
            plt.text(width + 1, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}%',
                    ha='left', va='center')

        plt.tight_layout()
        plt.savefig(self.charts_dir / 'leaderboard.png', dpi=300)
        plt.close()


def main():
    """Command-line interface for benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run automated benchmarks for model evaluation"
    )
    parser.add_argument(
        '--model',
        type=str,
        required=True,
        help='Model name/identifier'
    )
    parser.add_argument(
        '--endpoint',
        type=str,
        help='API endpoint URL'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='API key for authentication'
    )
    parser.add_argument(
        '--eval-suite',
        type=str,
        default='evaluations/advanced_eval.jsonl',
        help='Path to evaluation suite JSONL file'
    )
    parser.add_argument(
        '--no-visual',
        action='store_true',
        help='Disable visual validation tests'
    )
    parser.add_argument(
        '--charts',
        action='store_true',
        help='Generate comparison charts after benchmark'
    )
    parser.add_argument(
        '--compare-models',
        nargs='+',
        help='Generate charts comparing specific models'
    )

    args = parser.parse_args()

    # Initialize runner
    runner = BenchmarkRunner(eval_suite_path=args.eval_suite)

    # Run benchmark
    if not args.compare_models:
        result = runner.run_benchmark(
            model_name=args.model,
            model_endpoint=args.endpoint,
            api_key=args.api_key,
            enable_visual_tests=not args.no_visual
        )

    # Generate charts
    if args.charts or args.compare_models:
        runner.generate_comparison_charts(model_names=args.compare_models)


if __name__ == "__main__":
    main()
