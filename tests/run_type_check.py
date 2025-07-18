#!/usr/bin/env python3
"""
Script to run type checking with mypy
"""
import subprocess
import sys


def run_mypy():
    """Run mypy type checking"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "mypy", "src/"
        ], capture_output=True, text=True)
        
        print("MyPy Type Check Results:")
        print("=" * 50)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ MyPy type checking passed!")
        else:
            print("❌ MyPy type checking failed!")
            
        return result.returncode
    except Exception as e:
        print(f"Error running mypy: {e}")
        return 1


if __name__ == "__main__":
    exit_code = run_mypy()
    sys.exit(exit_code)
