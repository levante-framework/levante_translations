#!/usr/bin/env python3
"""
Core-Tasks Validation Script

This script validates that the core-tasks repository still works after Levante translations
deployment by running its Cypress end-to-end tests.

Usage:
    python validate_core_tasks.py [--core-tasks-path PATH] [--dev-server-only] [--headless]
    
Examples:
    python validate_core_tasks.py                           # Run full validation
    python validate_core_tasks.py --core-tasks-path ../my-core-tasks  # Custom path
    python validate_core_tasks.py --dev-server-only         # Only start dev server (no tests)
    python validate_core_tasks.py --headless                # Run tests in headless mode
"""

import sys
import os
import subprocess
import argparse
import time
import signal
from pathlib import Path
from datetime import datetime

# Configuration
DEFAULT_CORE_TASKS_PATH = "../core-tasks"
TASK_LAUNCHER_SUBDIR = "task-launcher"
DEV_SERVER_STARTUP_WAIT = 10  # seconds to wait for dev server to start
CYPRESS_TIMEOUT = 900  # 15 minutes timeout for Cypress tests (some tests can be slow)

def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print(f"{'='*70}")

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n📋 {title}")
    print("-" * 50)

def run_command(cmd: list, description: str, cwd: str = None, timeout: int = None, capture_output: bool = True) -> tuple:
    """
    Run a shell command with proper error handling.
    
    Args:
        cmd: Command to run as a list
        description: Human-readable description for logging
        cwd: Working directory for the command
        timeout: Timeout in seconds
        capture_output: Whether to capture output
        
    Returns:
        (success: bool, result: subprocess.CompletedProcess or None)
    """
    cmd_str = ' '.join(cmd)
    cwd_display = cwd or "current directory"
    
    print(f"🔧 {description}...")
    print(f"   Command: {cmd_str}")
    print(f"   Working directory: {cwd_display}")
    
    try:
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=capture_output, 
            text=True, 
            cwd=cwd,
            timeout=timeout
        )
        
        if capture_output and result.stdout:
            # Show only important output lines
            lines = result.stdout.strip().split('\n')
            important_lines = [line for line in lines[-10:] if line.strip()]  # Last 10 non-empty lines
            for line in important_lines:
                print(f"   📤 {line}")
        
        if capture_output and result.stderr and result.stderr.strip():
            print(f"   ⚠️  Stderr: {result.stderr.strip()}")
        
        print(f"   ✅ {description} completed successfully")
        return True, result
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"   Exit code: {e.returncode}")
        if capture_output:
            if e.stdout:
                print(f"   Stdout: {e.stdout}")
            if e.stderr:
                print(f"   Stderr: {e.stderr}")
        return False, e
    except subprocess.TimeoutExpired as e:
        print(f"⏰ Timeout: {description} (after {timeout}s)")
        return False, e
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False, None

def check_prerequisites(core_tasks_path: Path) -> bool:
    """
    Check if all prerequisites are met for running core-tasks validation.
    
    Args:
        core_tasks_path: Path to the core-tasks repository
        
    Returns:
        True if all prerequisites are met
    """
    print_section("Prerequisites Check")
    
    all_good = True
    
    # Check if core-tasks directory exists
    if not core_tasks_path.exists():
        print(f"❌ Core-tasks directory not found: {core_tasks_path}")
        print("   Please clone the core-tasks repository or provide the correct path")
        all_good = False
    else:
        print(f"✅ Core-tasks directory found: {core_tasks_path}")
    
    # Check if task-launcher subdirectory exists
    task_launcher_path = core_tasks_path / TASK_LAUNCHER_SUBDIR
    if not task_launcher_path.exists():
        print(f"❌ Task-launcher directory not found: {task_launcher_path}")
        all_good = False
    else:
        print(f"✅ Task-launcher directory found: {task_launcher_path}")
    
    # Check if package.json exists
    package_json_path = task_launcher_path / "package.json"
    if not package_json_path.exists():
        print(f"❌ package.json not found: {package_json_path}")
        all_good = False
    else:
        print(f"✅ package.json found: {package_json_path}")
    
    # Check Node.js
    success, _ = run_command(["node", "--version"], "Check Node.js version")
    if not success:
        print("❌ Node.js not found. Please install Node.js")
        all_good = False
    else:
        print("✅ Node.js is available")
    
    # Check npm
    success, _ = run_command(["npm", "--version"], "Check npm version")
    if not success:
        print("❌ npm not found. Please install npm")
        all_good = False
    else:
        print("✅ npm is available")
    
    return all_good

def install_dependencies(task_launcher_path: Path) -> bool:
    """
    Install npm dependencies for the core-tasks project.
    
    Args:
        task_launcher_path: Path to the task-launcher directory
        
    Returns:
        True if installation succeeded
    """
    print_section("Installing Dependencies")
    
    # Check if node_modules already exists
    node_modules_path = task_launcher_path / "node_modules"
    if node_modules_path.exists():
        print("📦 node_modules directory already exists, checking if up to date...")
        
        # Run npm ci for faster, reliable install
        success, _ = run_command(
            ["npm", "ci"], 
            "Install dependencies (clean install)",
            cwd=str(task_launcher_path),
            timeout=120  # 2 minutes timeout
        )
    else:
        print("📦 Installing dependencies for the first time...")
        success, _ = run_command(
            ["npm", "install"], 
            "Install npm dependencies",
            cwd=str(task_launcher_path),
            timeout=180  # 3 minutes timeout
        )
    
    return success

def start_dev_server(task_launcher_path: Path) -> subprocess.Popen:
    """
    Start the development server for core-tasks.
    
    Args:
        task_launcher_path: Path to the task-launcher directory
        
    Returns:
        Popen object for the dev server process, or None if failed
    """
    print_section("Starting Development Server")
    
    print(f"🚀 Starting dev server (this may take a moment)...")
    print(f"   Command: npm run dev:db")
    print(f"   Working directory: {task_launcher_path}")
    
    try:
        # Start the dev server in the background
        process = subprocess.Popen(
            ["npm", "run", "dev:db"],
            cwd=str(task_launcher_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid  # Create new process group for clean termination
        )
        
        print(f"📡 Dev server started with PID: {process.pid}")
        print(f"⏳ Waiting {DEV_SERVER_STARTUP_WAIT} seconds for server to initialize...")
        
        # Wait for server to start up
        time.sleep(DEV_SERVER_STARTUP_WAIT)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Dev server appears to be running")
            return process
        else:
            print("❌ Dev server failed to start")
            stdout, stderr = process.communicate()
            print(f"   Stdout: {stdout}")
            print(f"   Stderr: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start dev server: {e}")
        return None

def run_cypress_tests(task_launcher_path: Path, headless: bool = True, timeout: int = None) -> bool:
    """
    Run Cypress tests for the core-tasks project.
    
    Args:
        task_launcher_path: Path to the task-launcher directory
        headless: Whether to run tests in headless mode
        timeout: Custom timeout in seconds (defaults to CYPRESS_TIMEOUT)
        
    Returns:
        True if tests passed
    """
    print_section("Running Cypress Tests")
    
    if timeout is None:
        timeout = CYPRESS_TIMEOUT
    
    if headless:
        cmd = ["npx", "cypress", "run", "--browser", "chrome", "--headless", "--reporter", "spec"]
        description = f"Run Cypress tests (headless, timeout: {timeout}s)"
    else:
        print("⚠️  Running Cypress in interactive mode. Tests will open browser windows.")
        cmd = ["npx", "cypress", "open"]
        description = "Open Cypress test runner"
    
    print(f"⏱️  Test timeout: {timeout} seconds ({timeout//60} minutes)")
    print(f"📋 Running command: {' '.join(cmd)}")
    
    # For headless mode, run with real-time output to show progress
    if headless:
        success = run_cypress_with_progress(cmd, task_launcher_path, timeout)
    else:
        success, result = run_command(
            cmd,
            description,
            cwd=str(task_launcher_path),
            timeout=timeout,
            capture_output=False  # Don't capture in interactive mode
        )
    
    if success:
        print("🎉 All Cypress tests passed!")
    else:
        print("💥 Some Cypress tests failed. Check the output above for details.")
    
    return success

def run_cypress_with_progress(cmd: list, task_launcher_path: Path, timeout: int) -> bool:
    """
    Run Cypress with real-time progress output.
    
    Args:
        cmd: Command to run
        task_launcher_path: Working directory
        timeout: Timeout in seconds
        
    Returns:
        True if tests passed
    """
    print(f"🔧 Starting Cypress tests with real-time output...")
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(task_launcher_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output in real-time
        import select
        import time
        
        start_time = time.time()
        output_lines = []
        
        while True:
            # Check if process is still running
            if process.poll() is not None:
                # Process finished, read any remaining output
                remaining_output = process.stdout.read()
                if remaining_output:
                    for line in remaining_output.split('\n'):
                        if line.strip():
                            print(f"   📤 {line}")
                            output_lines.append(line)
                break
            
            # Check for timeout
            if time.time() - start_time > timeout:
                print(f"⏰ Timeout reached ({timeout}s), terminating process...")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                return False
            
            # Check for available output
            if select.select([process.stdout], [], [], 1.0)[0]:
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        print(f"   📤 {line}")
                        output_lines.append(line)
            
        # Check exit code
        return_code = process.returncode
        
        if return_code == 0:
            print(f"✅ Cypress tests completed successfully!")
            return True
        else:
            print(f"❌ Cypress tests failed with exit code: {return_code}")
            
            # Show summary of important output
            print("\n📋 Test Summary:")
            important_lines = [line for line in output_lines[-20:] if any(keyword in line.lower() 
                             for keyword in ['failing', 'passing', 'error', 'fail', 'pass', 'spec'])]
            for line in important_lines[-10:]:  # Last 10 important lines
                print(f"   {line}")
            
            return False
            
    except Exception as e:
        print(f"❌ Error running Cypress tests: {e}")
        return False

def stop_dev_server(process: subprocess.Popen):
    """
    Stop the development server process.
    
    Args:
        process: The dev server Popen object
    """
    if process and process.poll() is None:
        print_section("Stopping Development Server")
        print(f"🛑 Stopping dev server (PID: {process.pid})...")
        
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for process to terminate
            try:
                process.wait(timeout=10)
                print("✅ Dev server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("⚠️  Dev server didn't stop gracefully, force killing...")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
                print("✅ Dev server force stopped")
                
        except Exception as e:
            print(f"⚠️  Error stopping dev server: {e}")

def main():
    """Main function to handle command line arguments and orchestrate validation."""
    parser = argparse.ArgumentParser(
        description='Validate core-tasks repository by running Cypress tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python validate_core_tasks.py                           # Run full validation
    python validate_core_tasks.py --core-tasks-path ../my-core-tasks  # Custom path
    python validate_core_tasks.py --dev-server-only         # Only start dev server
    python validate_core_tasks.py --headless                # Run tests in headless mode
        """
    )
    
    parser.add_argument(
        '--core-tasks-path',
        default=DEFAULT_CORE_TASKS_PATH,
        help=f'Path to core-tasks repository (default: {DEFAULT_CORE_TASKS_PATH})'
    )
    
    parser.add_argument(
        '--dev-server-only',
        action='store_true',
        help='Only start the dev server, don\'t run tests (useful for manual testing)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Run Cypress tests in headless mode (default: true)'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run Cypress in interactive mode (opens browser)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=CYPRESS_TIMEOUT,
        help=f'Timeout for Cypress tests in seconds (default: {CYPRESS_TIMEOUT})'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run with shorter timeout (5 minutes) for quick validation'
    )
    
    args = parser.parse_args()
    
    # Resolve path
    core_tasks_path = Path(args.core_tasks_path).resolve()
    task_launcher_path = core_tasks_path / TASK_LAUNCHER_SUBDIR
    
    # Determine run mode
    headless_mode = args.headless and not args.interactive
    
    # Determine timeout
    if args.quick:
        test_timeout = 300  # 5 minutes for quick validation
    else:
        test_timeout = args.timeout
    
    # Print header
    mode = "DEV SERVER ONLY" if args.dev_server_only else ("INTERACTIVE TESTS" if args.interactive else "HEADLESS TESTS")
    title = f"Core-Tasks Validation - {mode}"
    print_header(title)
    
    print(f"🎯 Core-tasks path: {core_tasks_path}")
    print(f"📁 Task-launcher path: {task_launcher_path}")
    print(f"🧪 Mode: {mode}")
    
    # Check prerequisites
    if not check_prerequisites(core_tasks_path):
        print("\n❌ Prerequisites check failed. Please resolve the issues above.")
        return 1
    
    # Install dependencies
    if not install_dependencies(task_launcher_path):
        print("\n❌ Failed to install dependencies.")
        return 1
    
    # Start dev server
    dev_server_process = start_dev_server(task_launcher_path)
    if not dev_server_process:
        print("\n❌ Failed to start development server.")
        return 1
    
    try:
        if args.dev_server_only:
            print_section("Development Server Running")
            print("🌐 Development server is running!")
            print("   You can now manually test the core-tasks application")
            print("   Press Ctrl+C to stop the server")
            
            # Keep server running until interrupted
            try:
                dev_server_process.wait()
            except KeyboardInterrupt:
                print("\n⚠️  Received interrupt signal")
                
        else:
            # Run Cypress tests
            tests_passed = run_cypress_tests(task_launcher_path, headless_mode, test_timeout)
            
            if tests_passed:
                print_section("Validation Summary")
                print("🎉 Core-tasks validation completed successfully!")
                print("✅ All Cypress tests passed")
                print("✅ Core-tasks repository is working correctly")
                return 0
            else:
                print_section("Validation Summary")
                print("💥 Core-tasks validation failed!")
                print("❌ Some Cypress tests failed")
                print("❌ Core-tasks repository may have issues")
                return 1
                
    finally:
        # Always stop the dev server
        stop_dev_server(dev_server_process)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())