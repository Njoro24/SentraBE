#!/usr/bin/env python
"""
Master Test Runner - Sentra Full System Test Suite
Runs all 4 layers in sequence and generates final report
"""

import subprocess
import sys
import time
from datetime import datetime


def run_pytest(test_file, layer_name):
    """Run pytest on a test file and capture results"""
    
    print(f"\n{'='*80}")
    print(f"Running {layer_name}...")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    
    duration = time.time() - start_time
    
    # Parse output for test counts
    output = result.stdout + result.stderr
    
    # Extract test counts
    passed = output.count(" PASSED")
    failed = output.count(" FAILED")
    skipped = output.count(" SKIPPED")
    total = passed + failed + skipped
    
    return {
        "layer": layer_name,
        "file": test_file,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "duration": duration,
        "return_code": result.returncode,
        "output": output
    }


def main():
    """Run all test layers"""
    
    print("\n" + "="*80)
    print("SENTRA — Full System Test Suite")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Define test layers
    layers = [
        ("SentraBE/tests/integration/test_layer4_e2e.py", "Layer 4: End-to-End Pipeline"),
        ("SentraBE/tests/integration/test_layer3_stress.py", "Layer 3: Stress & Chaos"),
        ("SentraBE/tests/integration/test_layer2_integration.py", "Layer 2: Cross-Phase Integration"),
        ("SentraBE/tests/integration/test_layer1_components.py", "Layer 1: Component Tests"),
    ]
    
    results = []
    total_failures = 0
    
    # Run each layer
    for test_file, layer_name in layers:
        result = run_pytest(test_file, layer_name)
        results.append(result)
        
        if result["return_code"] != 0:
            total_failures += result["failed"]
        
        # Print layer summary
        print(f"\n{layer_name} Summary:")
        print(f"  Tests: {result['total']}")
        print(f"  Passed: {result['passed']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Skipped: {result['skipped']}")
        print(f"  Duration: {result['duration']:.2f}s")
    
    # Print final report
    print("\n" + "="*80)
    print("FINAL TEST REPORT")
    print("="*80)
    print(f"{'Layer':<40} {'Tests':<10} {'Passed':<10} {'Failed':<10} {'Skipped':<10} {'Duration':<12}")
    print("-"*80)
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    total_duration = 0
    
    for result in results:
        print(f"{result['layer']:<40} {result['total']:<10} {result['passed']:<10} "
              f"{result['failed']:<10} {result['skipped']:<10} {result['duration']:>10.2f}s")
        
        total_tests += result['total']
        total_passed += result['passed']
        total_failed += result['failed']
        total_skipped += result['skipped']
        total_duration += result['duration']
    
    print("-"*80)
    print(f"{'TOTAL':<40} {total_tests:<10} {total_passed:<10} {total_failed:<10} "
          f"{total_skipped:<10} {total_duration:>10.2f}s")
    print("="*80)
    
    # Overall verdict
    print("\n" + "="*80)
    if total_failed == 0:
        print("ALL SYSTEMS GO")
        exit_code = 0
    else:
        print(f"FAILURES DETECTED — {total_failed} test(s) failed")
        print("See table above for details")
        exit_code = 1
    print("="*80 + "\n")
    
    # Print completion time
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Duration: {total_duration:.2f}s\n")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
