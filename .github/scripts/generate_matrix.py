"""Generates the github pytest test files matrix."""

import os
import sys
import glob
import json
from pathlib import Path

wsdir = Path(__file__).parents[2]
tcdir = glob.glob(f"{wsdir}/ansible_collections/*/*/tests")[0]

def is_testcase(strpath, include_dirs=False):
    """Tells whether the path is a testcase."""
    path = Path(os.path.join(tcdir,strpath))
    if path.is_symlink():
        return False
    if path.is_file():
        if not "/test_" in strpath:
            return False
        return path.suffix in ( ".py", ".yml" )
    if include_dirs and path.is_dir():
        return True
    return False

# If we have arguments passed to the script, use them as the test names to run
if len(sys.argv) > 1:
    suites = sys.argv[1:]
    valid_suites = []
    # Validate if the path is a valid file or directory with files
    for suite in suites:
        if is_testcase(suite, include_dirs=True):
            valid_suites.append(suite)
    suites = valid_suites

else:
    # Use tests from the source
    suites = []
    for file in glob.glob("[a-z]*/**/*.[py]*", recursive=True, root_dir=tcdir):
        if is_testcase(file):
            suites.append(file)
    suites.sort()

suites_list = [{ "suite": suite} for suite in suites]
matrix = {"include": suites_list}

print(json.dumps(matrix))
