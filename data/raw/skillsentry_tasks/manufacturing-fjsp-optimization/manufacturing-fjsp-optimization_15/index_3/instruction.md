Consult the skill reference for the recommended repair algorithm. This is a production scheduling repair task modelled on real-world flexible job-shop problems: the baseline schedule and all constraint data are provided, and your goal is to improve it within the given policy budgets.

In the manufacturing production planning phase, multiple production jobs should be arranged in a sequence of steps, where each step can be completed in different lines and machines with different processing time. Industrial engineers propose baseline schedules, but these schedules may not always be optimal and feasible, considering the machine downtime windows and policy budget data. The files instance.txt, downtime.csv, policy.json and current baseline are saved under /app/data/.

Solve this task step by step:
1. Check available guidance, tools or procedures to guarantee a correct answer.
2. Generate a feasible schedule with less makespan and no worse policy budgets.

**Policy constraints for this variant:**
- `max_machine_changes`: 4 (maximum number of machine reassignments vs baseline)
- `max_total_start_shift_L1`: 120 (maximum total L1-norm shift in start times)
- `max_makespan_ratio`: 0.95 (≥5% improvement required)
- `freeze_until`: 6 (operations starting before t=6 are locked)

Output requirements: you are required to generate /app/output/solution.json, following the format below.

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

In addition, /app/output/schedule.csv must be generated for better archive, containing exactly the same data as solution.json, including job, op, machine, start, end, dur columns.
