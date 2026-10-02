This is a production scheduling repair task based on real-world flexible job-shop problems. The baseline schedule and all constraint data are supplied — your aim is to enhance it within the given policy budgets. Refer to the skill reference for the suggested repair algorithm.

In the manufacturing production planning stage, multiple production jobs should be organized into a sequence of steps. Each step can be carried out on different lines and machines with different processing time. Industrial engineers put forward baseline schedules. However, these schedules may not always be optimal and feasible, given the machine downtime windows and policy budget data. Your task is to produce a feasible schedule with a shorter makespan and no worse policy budgets. Work through this task step by step. Review available guidance, tools or procedures to ensure a correct answer. The files instance.txt, downtime.csv, policy.json and current baseline are stored under /app/data/.

**Policy constraints for this variant:**
- `max_machine_changes`: 4 (maximum number of machine reassignments vs baseline)
- `max_total_start_shift_L1`: 120 (maximum total L1-norm shift in start times)
- `max_makespan_ratio`: 0.95 (≥5% improvement required)
- `freeze_until`: 6 (operations starting before t=6 are locked)

You are required to produce /app/output/solution.json. Please adhere to the following format.

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

You are also required to produce /app/output/schedule.csv for better archiving with the exact same data as solution.json, containing job, op, machine, start, end, dur columns.
