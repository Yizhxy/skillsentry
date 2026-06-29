"""SkillSentry v2 (basic) — runtime workflow-compliance guard for Claude Code skills.

Module map:
  ir         — rules.json schema + load helpers
  matchers   — pending-tool-call ↔ signature matching
  fsm        — L2 ordering FSM
  state      — per-session state file (FSM progress, cooldown log, observed sigs)
  judge      — L3 LLM-as-judge sidecar (fail-open)
  layers     — L1/L4 implementations + three-tier feedback assembly
"""
