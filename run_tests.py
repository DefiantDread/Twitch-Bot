# run_tests.py
import pytest
import sys

if __name__ == "__main__":
    args = [
        "-v",                # Verbose output
        "--asyncio-mode=auto",  # Handle async tests
        "tests",            # Test directory
        "--cov=.",          # Coverage report
        "--cov-report=term-missing"  # Show lines missing coverage
    ]
    result = pytest.main(args)
    sys.exit(result)