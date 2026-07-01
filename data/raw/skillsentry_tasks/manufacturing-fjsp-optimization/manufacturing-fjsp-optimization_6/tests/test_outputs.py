import os, json, csv
from typing import Any, List, Dict, Tuple
from collections import defaultdict

OUT_DIR = "/app/output"
DATA_DIR = "/app/data"

INSTANCE_PATH = f"{DATA_DIR}/instance.txt"
DOWNTIME_PATH = f"{DATA_DIR}/downtime.csv"
POLICY_PATH   = f"{DATA_DIR}/policy.json"
OLD_METRICS   = f"{DATA_DIR}/baseline_metrics.json"
OLD_SOLUTION  = f"{DATA_DIR}/baseline_solution.json"

SOLUTION_JSON = f"{OUT_DIR}/solution.json"
SCHEDULE_CSV  = f"{OUT_DIR}/schedule.csv"

MAX_MACHINE_CHANGES = 4
MAX_SHIFT_L1 = 120
MAX_MAKESPAN_RATIO = 1.1
FREEZE_UNTIL = 6

def load_json(p):
    with open(p) as f: return json.load(f)

def as_int(x):
    if isinstance(x, int): return x
    return int(round(float(str(x).strip())))

def overlap(a, b, c, d): return a < d and c < b

def parse_instance(path):
    tokens = []
    with open(path) as f:
        for l in f:
            if l.strip() and not l.lstrip().startswith("#"):
                tokens.extend(l.split())
    it = iter(tokens); J, M = int(next(it)), int(next(it))
    jobs = []
    for _ in range(J):
        n_ops = int(next(it)); ops = []
        for _ in range(n_ops):
            k = int(next(it)); opts = []
            for _ in range(k):
                m = int(next(it)); d = int(next(it)); opts.append((m, d))
            ops.append(opts)
        jobs.append(ops)
    return J, M, jobs

def load_downtime():
    downtime = defaultdict(list)
    with open(DOWNTIME_PATH) as f:
        for row in csv.DictReader(f):
            m = int(row["machine"]); s = int(row["start"]); e = int(row["end"])
            downtime[m].append((s, e))
    return downtime

class TestManufacturingVariant:
    def test_output_files_exist(self):
        assert os.path.exists(SOLUTION_JSON), f"solution.json not found"
        assert os.path.exists(SCHEDULE_CSV), f"schedule.csv not found"

    def test_solution_structure(self):
        sol = load_json(SOLUTION_JSON)
        assert "status" in sol and "makespan" in sol and "schedule" in sol

    def test_schedule_feasibility(self):
        J, M, jobs = parse_instance(INSTANCE_PATH)
        downtime = load_downtime()
        sol = load_json(SOLUTION_JSON)
        sch = sol["schedule"]
        
        ops_done = [[False]*len(ops) for ops in jobs]
        machine_slots = defaultdict(list)
        
        for entry in sch:
            j, o, m = as_int(entry["job"]), as_int(entry["op"]), as_int(entry["machine"])
            s, e, d = as_int(entry["start"]), as_int(entry["end"]), as_int(entry["dur"])
            
            assert 0 <= j < J; assert 0 <= o < len(jobs[j]); assert 0 <= m < M
            valid_machines = [opt[0] for opt in jobs[j][o]]
            assert m in valid_machines, f"Machine {m} not valid for job {j} op {o}"
            expected_dur = next(dur for mm, dur in jobs[j][o] if mm == m)
            assert d == expected_dur, f"Duration mismatch j={j} o={o}: expected {expected_dur}, got {d}"
            assert e == s + d, f"end != start + dur"
            
            for ds, de in downtime.get(m, []):
                assert not overlap(s, e, ds, de), f"Op overlaps downtime [{ds},{de}) on machine {m}"
            
            for (os2, oe2) in machine_slots[m]:
                assert not overlap(s, e, os2, oe2), f"Machine {m} conflict: [{s},{e}) vs [{os2},{oe2})"
            machine_slots[m].append((s, e))
            ops_done[j][o] = True
        
        for j in range(J):
            for o in range(len(jobs[j])):
                assert ops_done[j][o], f"Missing job {j} op {o}"

    def test_precedence_constraints(self):
        J, M, jobs = parse_instance(INSTANCE_PATH)
        sol = load_json(SOLUTION_JSON)
        op_end = {}
        for entry in sol["schedule"]:
            j, o = as_int(entry["job"]), as_int(entry["op"])
            op_end[(j, o)] = as_int(entry["end"])
        for j in range(J):
            for o in range(1, len(jobs[j])):
                assert op_end.get((j,o-1),0) <= op_end.get((j,o), float("inf")) - (as_int(next(e["dur"] for e in sol["schedule"] if as_int(e["job"])==j and as_int(e["op"])==o))),                     f"Precedence violated: job {j} op {o-1} must finish before op {o} starts"

    def test_makespan_beats_baseline(self):
        old = load_json(OLD_METRICS)
        sol = load_json(SOLUTION_JSON)
        baseline = as_int(old["baseline"]["makespan"])
        new_ms = as_int(sol["makespan"])
        assert new_ms < baseline, f"makespan {new_ms} must be < baseline {baseline}"
        assert new_ms <= baseline * 1.1, f"makespan ratio {new_ms/baseline:.3f} exceeds limit 1.1"

    def test_downtime_violations_zero(self):
        sol = load_json(SOLUTION_JSON)
        old = load_json(OLD_METRICS)
        max_violations = as_int(old["thresholds"]["max_downtime_violations"])
        actual = sol.get("downtime_violations", 0)
        assert as_int(actual) <= max_violations

    def test_policy_budget_compliance(self):
        old_sol = load_json(OLD_SOLUTION)
        new_sol = load_json(SOLUTION_JSON)
        old_sch = {(as_int(e["job"]), as_int(e["op"])): e for e in old_sol["schedule"]}
        mc, ss = 0, 0
        frozen_ops = {(as_int(e["job"]), as_int(e["op"])) for e in old_sol["schedule"] if as_int(e["start"]) < 6}
        
        for e in new_sol["schedule"]:
            k = (as_int(e["job"]), as_int(e["op"]))
            if k in old_sch:
                if as_int(e["machine"]) != as_int(old_sch[k]["machine"]): mc += 1
                if k in frozen_ops:
                    assert as_int(e["machine"]) == as_int(old_sch[k]["machine"]), f"Frozen op {k} machine changed"
                    assert as_int(e["start"]) == as_int(old_sch[k]["start"]), f"Frozen op {k} start changed"
                ss += abs(as_int(e["start"]) - as_int(old_sch[k]["start"]))
        
        assert mc <= 4, f"machine changes {mc} exceeds limit 4"
        assert ss <= 120, f"total start shift {ss} exceeds limit 120"

    def test_machine_utilization_file(self):
        """Verify machine_utilization.json was generated."""
        path = os.path.join(OUT_DIR, "machine_utilization.json")
        assert os.path.exists(path), f"machine_utilization.json not found at {path}"
        with open(path) as f:
            data = json.load(f)
        assert "machine_utilization" in data
        for machine, util in data["machine_utilization"].items():
            assert 0.0 <= float(util) <= 1.0, f"Utilization for {machine} must be in [0,1], got {util}"

