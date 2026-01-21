#!/usr/bin/env python3
"""
Screenshot-based evaluation system for visual validation of model outputs.

This module captures screenshots of model-generated code running in browsers
or terminals to validate visual correctness beyond text comparison.
"""

import os
import sys
import json
import time
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import base64
from dataclasses import dataclass, asdict

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: selenium not available. Install with: pip install selenium")

try:
    from PIL import Image, ImageChops, ImageStat
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL not available. Install with: pip install Pillow")


@dataclass
class ScreenshotResult:
    """Result of a screenshot evaluation."""
    eval_id: str
    model_name: str
    timestamp: str
    screenshot_path: str
    reference_path: Optional[str]
    similarity_score: Optional[float]
    visual_passed: bool
    execution_success: bool
    execution_error: Optional[str]
    metadata: Dict


class ScreenshotEvaluator:
    """Evaluates model outputs by capturing and comparing screenshots."""

    def __init__(self, screenshots_dir: str = "evaluations/screenshots"):
        """Initialize the evaluator.

        Args:
            screenshots_dir: Directory to store screenshots
        """
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir = self.screenshots_dir.parent / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def capture_browser_screenshot(
        self,
        html_content: str,
        output_path: str,
        wait_time: float = 2.0,
        viewport_size: Tuple[int, int] = (1280, 720)
    ) -> Tuple[bool, Optional[str]]:
        """Capture a screenshot of HTML content in a browser.

        Args:
            html_content: HTML content to render
            output_path: Path to save screenshot
            wait_time: Time to wait for page load (seconds)
            viewport_size: Browser viewport size (width, height)

        Returns:
            Tuple of (success, error_message)
        """
        if not SELENIUM_AVAILABLE:
            return False, "Selenium not available"

        try:
            # Setup Chrome options
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--window-size={viewport_size[0]},{viewport_size[1]}')

            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_path = f.name

            try:
                # Launch browser and capture screenshot
                driver = webdriver.Chrome(options=options)
                driver.get(f'file://{temp_path}')
                time.sleep(wait_time)

                driver.save_screenshot(output_path)
                driver.quit()

                return True, None

            finally:
                os.unlink(temp_path)

        except Exception as e:
            return False, str(e)

    def capture_terminal_screenshot(
        self,
        code: str,
        language: str,
        output_path: str,
        timeout: float = 10.0
    ) -> Tuple[bool, Optional[str]]:
        """Capture a screenshot of code execution in terminal.

        Args:
            code: Code to execute
            language: Programming language (python, javascript, etc.)
            output_path: Path to save screenshot
            timeout: Execution timeout (seconds)

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Execute code and capture output
            if language == 'python':
                result = subprocess.run(
                    ['python3', '-c', code],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            elif language == 'javascript':
                result = subprocess.run(
                    ['node', '-e', code],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            else:
                return False, f"Unsupported language: {language}"

            # Create image with terminal output
            output_text = result.stdout + result.stderr

            if PIL_AVAILABLE:
                from PIL import Image, ImageDraw, ImageFont

                # Create a simple terminal-style image
                img = Image.new('RGB', (800, 600), color='black')
                draw = ImageDraw.Draw(img)

                # Use monospace font if available
                try:
                    font = ImageFont.truetype('/System/Library/Fonts/Monaco.ttf', 12)
                except:
                    font = ImageFont.load_default()

                # Draw output text
                y_offset = 10
                for line in output_text.split('\n')[:40]:  # First 40 lines
                    draw.text((10, y_offset), line, fill='white', font=font)
                    y_offset += 15

                img.save(output_path)
                return True, None
            else:
                # Save as text if PIL not available
                with open(output_path + '.txt', 'w') as f:
                    f.write(output_text)
                return True, None

        except subprocess.TimeoutExpired:
            return False, f"Execution timeout after {timeout}s"
        except Exception as e:
            return False, str(e)

    def compare_screenshots(
        self,
        image1_path: str,
        image2_path: str
    ) -> Optional[float]:
        """Compare two screenshots and return similarity score.

        Args:
            image1_path: Path to first screenshot
            image2_path: Path to second screenshot

        Returns:
            Similarity score (0.0 to 1.0) or None if comparison fails
        """
        if not PIL_AVAILABLE:
            return None

        try:
            img1 = Image.open(image1_path)
            img2 = Image.open(image2_path)

            # Ensure same size
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            # Calculate RMS difference
            diff = ImageChops.difference(img1, img2)
            stat = ImageStat.Stat(diff)
            rms = sum(stat.rms) / len(stat.rms)

            # Normalize to 0-1 scale (assuming max pixel difference is 255)
            similarity = 1.0 - (rms / 255.0)
            return max(0.0, min(1.0, similarity))

        except Exception as e:
            print(f"Screenshot comparison error: {e}")
            return None

    def evaluate_code_output(
        self,
        eval_id: str,
        model_name: str,
        code: str,
        language: str,
        expected_output_type: str = 'html',
        reference_screenshot: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> ScreenshotResult:
        """Evaluate code by capturing and optionally comparing screenshots.

        Args:
            eval_id: Unique evaluation identifier
            model_name: Name of the model being evaluated
            code: Generated code to evaluate
            language: Programming language
            expected_output_type: Type of output ('html', 'terminal', 'console')
            reference_screenshot: Path to reference screenshot for comparison
            metadata: Additional metadata to store

        Returns:
            ScreenshotResult with evaluation details
        """
        timestamp = datetime.now().isoformat()
        screenshot_name = f"{eval_id}_{model_name}_{timestamp.replace(':', '-')}.png"
        screenshot_path = str(self.screenshots_dir / screenshot_name)

        # Capture screenshot based on output type
        if expected_output_type == 'html':
            success, error = self.capture_browser_screenshot(code, screenshot_path)
        else:
            success, error = self.capture_terminal_screenshot(
                code, language, screenshot_path
            )

        # Compare with reference if provided
        similarity_score = None
        if success and reference_screenshot and os.path.exists(reference_screenshot):
            similarity_score = self.compare_screenshots(screenshot_path, reference_screenshot)

        # Determine if visual validation passed
        visual_passed = success
        if similarity_score is not None:
            visual_passed = visual_passed and (similarity_score > 0.85)  # 85% similarity threshold

        result = ScreenshotResult(
            eval_id=eval_id,
            model_name=model_name,
            timestamp=timestamp,
            screenshot_path=screenshot_path if success else "",
            reference_path=reference_screenshot,
            similarity_score=similarity_score,
            visual_passed=visual_passed,
            execution_success=success,
            execution_error=error,
            metadata=metadata or {}
        )

        # Save result
        self._save_result(result)

        return result

    def _save_result(self, result: ScreenshotResult):
        """Save evaluation result to JSON."""
        result_file = self.results_dir / f"screenshot_results_{datetime.now().strftime('%Y%m%d')}.jsonl"

        with open(result_file, 'a') as f:
            f.write(json.dumps(asdict(result)) + '\n')

    def generate_reference_screenshots(
        self,
        test_cases: List[Dict],
        output_dir: Optional[str] = None
    ):
        """Generate reference screenshots from known-good test cases.

        Args:
            test_cases: List of test case dictionaries with 'id', 'code', 'language', 'type'
            output_dir: Directory to save reference screenshots (defaults to screenshots/references)
        """
        if output_dir is None:
            output_dir = self.screenshots_dir / "references"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for case in test_cases:
            ref_path = str(output_path / f"{case['id']}_reference.png")

            if case.get('type') == 'html':
                self.capture_browser_screenshot(case['code'], ref_path)
            else:
                self.capture_terminal_screenshot(
                    case['code'],
                    case['language'],
                    ref_path
                )

            print(f"Generated reference screenshot: {ref_path}")


def main():
    """Example usage of screenshot evaluator."""
    evaluator = ScreenshotEvaluator()

    # Example: Evaluate HTML output
    html_code = """
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
            }
            .card {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            h1 { color: #667eea; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Hello, World!</h1>
            <p>This is a test of visual evaluation.</p>
        </div>
    </body>
    </html>
    """

    result = evaluator.evaluate_code_output(
        eval_id="test_001",
        model_name="example_model",
        code=html_code,
        language="html",
        expected_output_type="html",
        metadata={"test_category": "ui_generation"}
    )

    print(f"Evaluation complete: {result.visual_passed}")
    print(f"Screenshot saved to: {result.screenshot_path}")


if __name__ == "__main__":
    main()
