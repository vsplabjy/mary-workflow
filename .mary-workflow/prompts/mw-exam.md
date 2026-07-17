# Mary Workflow ExamPass Profile

Use this prompt with `skills/exam-review/SKILL.md` as the governing content contract.

## Entry

Confirm course, exam identity, exact scope, exam date/remaining days, today's bounded 25-minute block, and review mode. Default to balanced mode; recommend exam mode within three days. Persist assumptions through the normal Mary planning interview before freezing the plan.

If the phase is `FINISHED`, tell the user to run `/mw-cycle` first. If the phase is `PLANNING`, use `/mw-plan` to create 1–3 bounded milestones. If the phase is `PLANNED`, show the exact evidence and wait for `/mw-run` to consume the grant. If execution is active, work only on the current milestone.

## Execution Route

1. Locate and reuse the Course Hub, Lecture notes, slides/handouts, existing review pages, calendar, and Mistake Log.
2. Generate chapter review pages, a whole-exam page, or mock papers according to the requested scope.
3. Label importance, explain formulas and exam use, compare confusing concepts, add self-tests and error checks.
4. Put mistakes in the course Mistake Log, update repeated-error reminders, and add/deduplicate exam calendar events.
5. Review scope, page naming/parentage, source attribution, answers separation, and cram card.

Do not widen the exam scope silently. Do not solve a student's live homework as part of review.

## Acceptance Evidence

The completion action must name affected Notion pages/URLs or local source files, confirm the exact exam scope and mode, report checklist evidence, and give the next single 25-minute action.
