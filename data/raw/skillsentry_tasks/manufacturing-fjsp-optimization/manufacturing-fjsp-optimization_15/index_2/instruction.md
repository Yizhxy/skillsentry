Production scheduling repair task modelled on real-world flexible job-shop problems. The baseline schedule and all constraint data are provided; improve it within the given policy budgets. Consult the skill reference for the recommended repair algorithm.

In manufacturing production planning, multiple production jobs should be arranged in a sequence of steps; each step can be completed in different lines and machines with different processing time. Industrial engineers propose baseline schedules, which may not always be optimal and feasible given the machine downtime windows and policy budget data. Generate a feasible schedule with less makespan and no worse policy budgets. Solve step by step. Check available guidance, tools or procedures to guarantee a correct answer. Input files instance.txt, downtime.csv, policy.json and current baseline are under /app/data/.

**Policy constraints for this variant:**
- `max_machine_changes`: 4 (maximum number of machine reassignments vs baseline)
- `max_total_start_shift_L1`: 120 (maximum total L1-norm shift in start times)
- `max_makespan_ratio`: 0.95 (≥5% improvement required)
- `freeze_until`: 6 (operations starting before t=6 are locked)

Generate /app/output/solution.json in the following format.

{
  "status": "",
  "makespan": ,
  "schedule": [
    {
      "job": ,
      "op": ,
      "machine": ,
      "start": ,
      "end": ,
      "dur":
    },
  ]
}

Also generate /app/output/schedule.csv for better archive with the exact same data as solution.json, including job, op, machine, start, end, dur columns.
