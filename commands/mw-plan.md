---
description: Interview for boundaries, then plan Mary Workflow milestones.
argument-hint: [request]
---

# /mw-plan

Load Mary Workflow's planning phase, run the adaptive interview gate, and create 1 to 7 milestones.

## Instructions

1. From the project root, render planning context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan
   ```

2. Treat the rendered output as active instruction context.
3. Follow persisted interview state: ask only boundary-changing questions, resolve answers, revise when requested, then freeze the exact draft in `PLANNED`. Every default or assumption, including with interview disabled, must be displayed and explicitly confirmed before freezing.
4. End after questions or after displaying the frozen plan. `/mw-run` itself confirms and starts that plan.
5. Do not edit product code, run acceptance commands, invoke `/mw-run`, or emit `start_execution` during planning.
