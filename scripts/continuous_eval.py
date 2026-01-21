#!/usr/bin/env python3
"""
Continuous evaluation service for automated model testing.

This service watches for new models, automatically runs evaluations,
sends notifications, and updates the dashboard.
"""

import os
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import hashlib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("Warning: watchdog not available. Install with: pip install watchdog")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests not available. Install with: pip install requests")


class ModelConfig:
    """Configuration for a model to evaluate."""

    def __init__(
        self,
        name: str,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: bool = True,
        schedule: Optional[str] = None
    ):
        self.name = name
        self.endpoint = endpoint
        self.api_key = api_key
        self.enabled = enabled
        self.schedule = schedule  # e.g., "daily", "hourly", "on_change"


class EvaluationHistory:
    """Tracks evaluation history to avoid redundant runs."""

    def __init__(self, history_file: str = "evaluations/results/eval_history.json"):
        self.history_file = Path(history_file)
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """Load evaluation history from file."""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_history(self):
        """Save evaluation history to file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def should_evaluate(
        self,
        model_name: str,
        eval_suite_hash: str,
        min_interval_hours: float = 1.0
    ) -> bool:
        """Check if model should be evaluated.

        Args:
            model_name: Name of the model
            eval_suite_hash: Hash of the evaluation suite
            min_interval_hours: Minimum hours between evaluations

        Returns:
            True if evaluation should run
        """
        key = f"{model_name}:{eval_suite_hash}"

        if key not in self.history:
            return True

        last_eval = datetime.fromisoformat(self.history[key]['timestamp'])
        time_since = datetime.now() - last_eval
        min_interval = timedelta(hours=min_interval_hours)

        return time_since >= min_interval

    def record_evaluation(
        self,
        model_name: str,
        eval_suite_hash: str,
        result_file: str
    ):
        """Record that an evaluation was performed.

        Args:
            model_name: Name of the model
            eval_suite_hash: Hash of the evaluation suite
            result_file: Path to result file
        """
        key = f"{model_name}:{eval_suite_hash}"
        self.history[key] = {
            'timestamp': datetime.now().isoformat(),
            'result_file': str(result_file)
        }
        self._save_history()


class EvaluationService:
    """Continuous evaluation service."""

    def __init__(
        self,
        config_file: str = "evaluations/eval_config.json",
        eval_suite: str = "evaluations/advanced_eval.jsonl",
        check_interval: int = 300,  # 5 minutes
        notification_webhook: Optional[str] = None
    ):
        """Initialize the evaluation service.

        Args:
            config_file: Path to model configuration file
            eval_suite: Path to evaluation suite
            check_interval: Time between checks in seconds
            notification_webhook: Webhook URL for notifications
        """
        self.config_file = Path(config_file)
        self.eval_suite = Path(eval_suite)
        self.check_interval = check_interval
        self.notification_webhook = notification_webhook

        self.history = EvaluationHistory()
        self.models = self._load_models()
        self.eval_suite_hash = self._hash_file(self.eval_suite)

        print(f"Continuous Evaluation Service Initialized")
        print(f"Config: {self.config_file}")
        print(f"Eval Suite: {self.eval_suite}")
        print(f"Models: {len(self.models)}")

    def _load_models(self) -> List[ModelConfig]:
        """Load model configurations."""
        if not self.config_file.exists():
            print(f"Config file not found: {self.config_file}")
            print("Creating default config...")
            self._create_default_config()

        with open(self.config_file, 'r') as f:
            config_data = json.load(f)

        models = []
        for model_data in config_data.get('models', []):
            models.append(ModelConfig(**model_data))

        return [m for m in models if m.enabled]

    def _create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            "models": [
                {
                    "name": "example_model_1",
                    "endpoint": None,
                    "api_key": None,
                    "enabled": False,
                    "schedule": "on_change"
                }
            ],
            "notification_settings": {
                "webhook_url": None,
                "notify_on_completion": True,
                "notify_on_error": True,
                "notify_on_improvement": True
            }
        }

        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)

        print(f"Created default config at: {self.config_file}")

    def _hash_file(self, file_path: Path) -> str:
        """Compute hash of file contents."""
        if not file_path.exists():
            return ""

        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def run_evaluation(self, model: ModelConfig) -> Optional[Dict]:
        """Run evaluation for a model.

        Args:
            model: Model configuration

        Returns:
            Evaluation result dictionary or None if failed
        """
        print(f"\n{'='*60}")
        print(f"Starting evaluation: {model.name}")
        print(f"Time: {datetime.now().isoformat()}")
        print(f"{'='*60}\n")

        try:
            # Build command
            cmd = [
                sys.executable,
                'scripts/run_benchmarks.py',
                '--model', model.name,
                '--eval-suite', str(self.eval_suite)
            ]

            if model.endpoint:
                cmd.extend(['--endpoint', model.endpoint])

            if model.api_key:
                cmd.extend(['--api-key', model.api_key])

            # Run benchmark
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )

            if result.returncode == 0:
                print(f"Evaluation completed successfully for {model.name}")

                # Record in history
                self.history.record_evaluation(
                    model.name,
                    self.eval_suite_hash,
                    f"results/benchmark_{model.name}_latest.json"
                )

                return {'success': True, 'model': model.name}
            else:
                print(f"Evaluation failed for {model.name}")
                print(f"Error: {result.stderr}")
                return {'success': False, 'model': model.name, 'error': result.stderr}

        except Exception as e:
            print(f"Exception during evaluation: {e}")
            return {'success': False, 'model': model.name, 'error': str(e)}

    def send_notification(self, message: str, result: Optional[Dict] = None):
        """Send notification via webhook.

        Args:
            message: Notification message
            result: Optional evaluation result data
        """
        if not self.notification_webhook or not REQUESTS_AVAILABLE:
            return

        try:
            payload = {
                'text': message,
                'timestamp': datetime.now().isoformat(),
                'result': result
            }

            requests.post(self.notification_webhook, json=payload, timeout=10)
            print(f"Notification sent: {message}")

        except Exception as e:
            print(f"Failed to send notification: {e}")

    def check_and_run_evaluations(self):
        """Check if evaluations should run and execute them."""
        print(f"\n[{datetime.now().isoformat()}] Checking for evaluations to run...")

        # Check if eval suite has changed
        current_hash = self._hash_file(self.eval_suite)
        suite_changed = current_hash != self.eval_suite_hash

        if suite_changed:
            print("Evaluation suite has changed - will re-evaluate all models")
            self.eval_suite_hash = current_hash

        for model in self.models:
            should_run = False

            if model.schedule == "on_change" and suite_changed:
                should_run = True
            elif self.history.should_evaluate(model.name, self.eval_suite_hash):
                should_run = True

            if should_run:
                result = self.run_evaluation(model)

                if result and result['success']:
                    self.send_notification(
                        f"Evaluation completed for {model.name}",
                        result
                    )
                elif result:
                    self.send_notification(
                        f"Evaluation failed for {model.name}: {result.get('error', 'Unknown error')}",
                        result
                    )

    def run_forever(self):
        """Run the service continuously."""
        print("\n" + "="*60)
        print("Continuous Evaluation Service Running")
        print(f"Check Interval: {self.check_interval}s")
        print(f"Press Ctrl+C to stop")
        print("="*60 + "\n")

        try:
            while True:
                self.check_and_run_evaluations()
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\nShutting down evaluation service...")
            self.send_notification("Evaluation service stopped")

    def run_once(self):
        """Run evaluations once and exit."""
        self.check_and_run_evaluations()


class EvalSuiteWatcher(FileSystemEventHandler):
    """Watches evaluation suite for changes."""

    def __init__(self, service: EvaluationService):
        self.service = service
        super().__init__()

    def on_modified(self, event):
        if event.src_path.endswith('advanced_eval.jsonl'):
            print(f"\nEvaluation suite modified: {event.src_path}")
            self.service.check_and_run_evaluations()


def setup_file_watcher(service: EvaluationService) -> Optional[Observer]:
    """Setup file system watcher for evaluation suite.

    Args:
        service: Evaluation service instance

    Returns:
        Observer instance or None if watchdog not available
    """
    if not WATCHDOG_AVAILABLE:
        print("File watching not available (install watchdog)")
        return None

    event_handler = EvalSuiteWatcher(service)
    observer = Observer()
    observer.schedule(
        event_handler,
        str(service.eval_suite.parent),
        recursive=False
    )
    observer.start()

    print("File watcher enabled for evaluation suite")
    return observer


def main():
    """Command-line interface for continuous evaluation service."""
    parser = argparse.ArgumentParser(
        description="Continuous evaluation service for models"
    )
    parser.add_argument(
        '--config',
        type=str,
        default='evaluations/eval_config.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--eval-suite',
        type=str,
        default='evaluations/advanced_eval.jsonl',
        help='Path to evaluation suite'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Check interval in seconds (default: 300)'
    )
    parser.add_argument(
        '--webhook',
        type=str,
        help='Webhook URL for notifications'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (no continuous monitoring)'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Enable file watching for immediate updates'
    )

    args = parser.parse_args()

    # Initialize service
    service = EvaluationService(
        config_file=args.config,
        eval_suite=args.eval_suite,
        check_interval=args.interval,
        notification_webhook=args.webhook
    )

    # Setup file watcher if requested
    observer = None
    if args.watch and not args.once:
        observer = setup_file_watcher(service)

    try:
        # Run service
        if args.once:
            service.run_once()
        else:
            service.run_forever()

    finally:
        if observer:
            observer.stop()
            observer.join()


if __name__ == "__main__":
    main()
