"""
Use this file to define pytest tests that verify the outputs of the task.
Tests airport planning variants with tasks: ['task13', 'task14']
"""

import json
import os
import pytest
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import PlanValidator

PROBLEM_FILE = "/app/problem.json"
DATA_DIR = "/app"

def validate_plan(domain_file, problem_file, plan_file):
    reader = PDDLReader()
    problem = reader.parse_problem(domain_file, problem_file)
    pred_plan = reader.parse_plan(problem, plan_file)
    with PlanValidator(problem_kind=problem.kind, plan_kind=pred_plan.kind) as validator:
        val = validator.validate(problem, pred_plan)
    return val.status.name in ("VALID", "SUCCESSFUL")

class TestAirportPlanning:
    def test_problem_json_exists(self):
        assert os.path.exists(PROBLEM_FILE), f"problem.json not found at {PROBLEM_FILE}"

    def test_plan_files_exist(self):
        with open(PROBLEM_FILE) as f:
            problems = json.load(f)
        for p in problems:
            plan_path = os.path.join(DATA_DIR, p["plan_output"])
            assert os.path.exists(plan_path), f"Plan file not found: {plan_path}"

    def test_plans_not_empty(self):
        with open(PROBLEM_FILE) as f:
            problems = json.load(f)
        for p in problems:
            plan_path = os.path.join(DATA_DIR, p["plan_output"])
            if os.path.exists(plan_path):
                with open(plan_path) as f:
                    content = f.read().strip()
                assert len(content) > 0, f"Plan file is empty: {plan_path}"

    def test_plans_are_valid(self):
        with open(PROBLEM_FILE) as f:
            problems = json.load(f)
        valid_count = 0
        for p in problems:
            domain_path = os.path.join(DATA_DIR, p["domain"])
            problem_path = os.path.join(DATA_DIR, p["problem"])
            plan_path = os.path.join(DATA_DIR, p["plan_output"])
            if not all(os.path.exists(x) for x in [domain_path, problem_path, plan_path]):
                continue
            try:
                is_valid = validate_plan(domain_path, problem_path, plan_path)
                if is_valid:
                    valid_count += 1
            except Exception as e:
                print(f"Validation error for {p['id']}: {e}")
        assert valid_count > 0, "At least one plan should be valid"
        assert valid_count == len(problems), f"All plans should be valid, got {valid_count}/{len(problems)}"
