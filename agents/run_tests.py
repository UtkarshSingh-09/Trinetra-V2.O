#!/usr/bin/env python3
import os
import sys
import json
import re
import subprocess
import time
from datetime import datetime

# Path setups
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_DIR = os.path.join(ROOT_DIR, "agents", "risk-agent", "models")
STATUS_PATH = os.path.join(STATUS_DIR, "test_status.json")
REPORT_PATH = os.path.join(STATUS_DIR, "test_report.json")

def update_status(status, progress, new_log=None, error=None):
    os.makedirs(STATUS_DIR, exist_ok=True)
    
    logs = []
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                logs = data.get("logs", [])
        except:
            pass
            
    if new_log:
        print(new_log)
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {new_log}")
        
    status_data = {
        "status": status,
        "progress": progress,
        "logs": logs,
        "error": error,
        "updated_at": datetime.now().isoformat()
    }
    
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)

def run_test_suite():
    update_status("RUNNING", 0, "Initializing automated testing framework...")
    
    # We clear the previous report if exists
    if os.path.exists(REPORT_PATH):
        try:
            os.remove(REPORT_PATH)
        except:
            pass

    # Command to run pytest (v represents verbose which shows test names and status)
    cmd = [sys.executable, "-m", "pytest", "agents/tests/", "-v", "--tb=short"]
    
    update_status("RUNNING", 10, "Executing: " + " ".join(cmd))
    
    # Run pytest process
    start_time = time.time()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=ROOT_DIR
    )

    test_results = []
    current_failures_section = False
    failure_blocks = []
    current_fail_block = []
    
    total_tests_estimate = 12
    completed_tests = 0

    # Stream output line-by-line
    for line in proc.stdout:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # Log console output
        update_status("RUNNING", min(90, 10 + int((completed_tests / total_tests_estimate) * 80)), line_stripped)
        
        # Check if line corresponds to a test execution line
        # Example format: agents/tests/test_compliance.py::test_compliance_all_files_uploaded PASSED [  8%]
        if "::" in line_stripped and ("PASSED" in line_stripped or "FAILED" in line_stripped):
            completed_tests += 1
            match = re.search(r'agents/tests/(\w+\.py)::(\w+)\s+(PASSED|FAILED)', line_stripped)
            if match:
                module = match.group(1)
                test_name = match.group(2)
                status = match.group(3)
                test_results.append({
                    "name": test_name,
                    "module": module,
                    "status": status,
                    "duration": 0.0,  # updated at end
                    "error": ""
                })

        # Track failure trace logs
        if line_stripped.startswith("=== FAILURES ==="):
            current_failures_section = True
            continue
            
        if line_stripped.startswith("=== short test summary info ==="):
            current_failures_section = False
            if current_fail_block:
                failure_blocks.append(current_fail_block)
            continue
            
        if current_failures_section:
            if line_stripped.startswith("___ test_") or line_stripped.startswith("___ Test"):
                if current_fail_block:
                    failure_blocks.append(current_fail_block)
                    current_fail_block = []
            current_fail_block.append(line_stripped)

    # Collect final failure blocks
    if current_fail_block:
        failure_blocks.append(current_fail_block)

    proc.wait()
    duration = time.time() - start_time
    
    # Associate failure logs with the failed tests
    failed_tests = [t for t in test_results if t["status"] == "FAILED"]
    for i, failed_test in enumerate(failed_tests):
        # Match by index if possible, otherwise merge blocks
        if i < len(failure_blocks):
            failed_test["error"] = "\n".join(failure_blocks[i])
        else:
            failed_test["error"] = "Test failed. See console logs for details."

    total = len(test_results)
    passed = sum(1 for t in test_results if t["status"] == "PASSED")
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 100.0

    # Distribute total duration among tests for simple estimates
    if total > 0:
        avg_dur = duration / total
        for t in test_results:
            t["duration"] = round(avg_dur, 3)

    report = {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": round(success_rate, 1),
            "duration_seconds": round(duration, 3)
        },
        "tests": test_results,
        "run_at": datetime.now().isoformat()
    }

    # Save test report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    status_str = "COMPLETED" if failed == 0 else "FAILED"
    log_msg = f"Testing complete. Passed: {passed}/{total}. Success Rate: {success_rate:.1f}%"
    update_status(status_str, 100, log_msg)

if __name__ == "__main__":
    run_test_suite()
