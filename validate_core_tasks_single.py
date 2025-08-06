#!/usr/bin/env python3
"""
Single Test Validation Script

Run individual Cypress tests to validate specific core-tasks functionality
without waiting for the entire test suite.

Usage:
    python validate_core_tasks_single.py [test_name] [--core-tasks-path PATH]
    
Examples:
    python validate_core_tasks_single.py home                    # Run only home.cy.js
    python validate_core_tasks_single.py hearts_and_flowers     # Run hearts_and_flowers.cy.js
    python validate_core_tasks_single.py --list                 # List available tests
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Configuration
DEFAULT_CORE_TASKS_PATH = "../core-tasks"
TASK_LAUNCHER_SUBDIR = "task-launcher"

def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def list_available_tests(task_launcher_path: Path) -> list:
    """
    List available Cypress test files.
    
    Args:
        task_launcher_path: Path to task-launcher directory
        
    Returns:
        List of test file names (without .cy.js extension)
    """
    cypress_dir = task_launcher_path / "cypress" / "e2e"
    if not cypress_dir.exists():
        return []
    
    test_files = list(cypress_dir.glob("*.cy.js"))
    return [f.stem for f in test_files]

def run_single_test(task_launcher_path: Path, test_name: str) -> bool:
    """
    Run a single Cypress test.
    
    Args:
        task_launcher_path: Path to task-launcher directory
        test_name: Name of test (without .cy.js)
        
    Returns:
        True if test passed
    """
    test_file = f"{test_name}.cy.js"
    cmd = [
        "npx", "cypress", "run", 
        "--spec", f"cypress/e2e/{test_file}",
        "--browser", "chrome", 
        "--headless",
        "--reporter", "spec"
    ]
    
    print(f"🔧 Running single test: {test_file}")
    print(f"📋 Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(task_launcher_path),
            check=True,
            text=True
        )
        print(f"✅ Test {test_name} passed!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Test {test_name} failed!")
        print(f"   Exit code: {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Cypress not found. Make sure dependencies are installed.")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Run individual Cypress tests for core-tasks validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python validate_core_tasks_single.py home                   # Run home test
    python validate_core_tasks_single.py hearts_and_flowers    # Run hearts & flowers
    python validate_core_tasks_single.py --list                # List available tests
        """
    )
    
    parser.add_argument(
        'test_name',
        nargs='?',
        help='Name of the test to run (without .cy.js extension)'
    )
    
    parser.add_argument(
        '--core-tasks-path',
        default=DEFAULT_CORE_TASKS_PATH,
        help=f'Path to core-tasks repository (default: {DEFAULT_CORE_TASKS_PATH})'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available tests'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    core_tasks_path = Path(args.core_tasks_path).resolve()
    task_launcher_path = core_tasks_path / TASK_LAUNCHER_SUBDIR
    
    # Check if paths exist
    if not task_launcher_path.exists():
        print(f"❌ Task-launcher directory not found: {task_launcher_path}")
        return 1
    
    # List tests
    available_tests = list_available_tests(task_launcher_path)
    
    if args.list or not args.test_name:
        print_header("Available Cypress Tests")
        if available_tests:
            print("📋 Available tests:")
            for test in sorted(available_tests):
                print(f"   • {test}")
            print(f"\n💡 Run a specific test with:")
            print(f"   python validate_core_tasks_single.py <test_name>")
        else:
            print("❌ No Cypress tests found")
        return 0
    
    # Validate test name
    test_name = args.test_name
    if test_name not in available_tests:
        print(f"❌ Test '{test_name}' not found")
        print(f"📋 Available tests: {', '.join(available_tests)}")
        return 1
    
    # Run the test
    print_header(f"Running Test: {test_name}")
    
    # Check if dev server is running (basic check)
    print("🔍 Checking if dev server is running...")
    try:
        import requests
        response = requests.get("http://localhost:3000", timeout=2)
        print("✅ Dev server appears to be running")
    except:
        print("⚠️  Dev server may not be running. Start it with:")
        print(f"   cd {task_launcher_path} && npm run dev:db")
        print("   Then run this script again")
        return 1
    
    # Run the single test
    success = run_single_test(task_launcher_path, test_name)
    
    if success:
        print(f"\n🎉 Test '{test_name}' completed successfully!")
        print("✅ Core-tasks functionality validated for this component")
        return 0
    else:
        print(f"\n💥 Test '{test_name}' failed!")
        print("❌ There may be issues with this core-tasks component")
        return 1

if __name__ == "__main__":
    sys.exit(main())