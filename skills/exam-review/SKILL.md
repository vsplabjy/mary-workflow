---
name: exam-review
description: Rebuild local Lecture notes, slides, and handouts into ExamPass chapter and exam review notes with importance labels, formula use, comparisons, self-tests, mock exams, ADHD mistake controls, and course-level placement. Use before midterms, finals, quizzes, or any exam review request.
---

# Exam Review

Use existing local Lecture notes as the primary source; use slides and handouts to fill gaps. Do not mix an exam's review notes with the Lecture index.

## Start Gate

Confirm the course, exam name/type, exact scope, exam date or remaining days, today's single 25-minute block, and mode. Modes are:

- `平衡模式` (default): knowledge, necessary explanation, examples, and self-test.
- `考试模式`: formulas, conclusions, exam points, mistakes, and practice; minimize expansion when `<= 3` days remain.
- `深度模式`: motivations, derivations, analogies, comparisons, and error diagnosis.

If no mode is given, choose balanced and surface the assumption. Cache unrelated questions until the current block is complete.

## Local Placement and Names

Create or reuse a direct local note under the Course Hub. Keep one exam identity in every title:

- Chapter: `<course code> <exam> 复习 — <chapter/module>`
- Whole exam: `<course code> <exam> 总复习`
- Mistakes: `<course code> 错题本`
- Mock exams: `<course code> <exam> 模拟卷 A — 巩固` and `... B — 拔高`

Reuse an existing empty local note containing the relevant PDF/notes. Never create duplicate review notes when a suitable local note already exists.

## Chapter Note

Use this order: why needed → what it is → how to use it → how it is tested → common mistakes.

1. Core problem and relation to neighboring chapters.
2. Knowledge overview table grouped by `🔴必考 / 🟠重点 / 🟡高频 / ⚪了解`.
3. Core concepts. For each: definition, motivation, procedure, KaTeX formula, symbol meanings, use in an exam, and an error reminder.
4. Comparison table for confusing concepts with the exam trap.
5. Formula list with meaning, use, and trap. Keep formulas out of table cells when rendering requires it.
6. Must-memorize conclusions.
7. Error checklist: wording, units, symbols, boundary conditions, signs, omitted steps, and copying/calculation.
8. Self-test: multiple choice, true/false, fill-in, short answer, and calculation/derivation, with answers and explanations.
9. Ten-minute cram card.

Reconstruct rather than copy. Use original Lecture images when a diagram matters; follow the Slide and round-trip skills for extraction.

## Whole Exam Note

Cover only the confirmed scope. Order the knowledge map and must-test ranking by importance, show dependencies between chapters, then include a mock paper and a separate answer/explanation section. Record the exam date in the local Course Hub and deduplicated local schedule in `Asia/Shanghai` when a schedule file exists.

## Mistake Log

Keep one local Mistake Log per course under the Course Hub. Its index has only `精确总结` and `错误总结`; detailed entries contain `❌错在哪`, `✅正确做法`, and `🐈防错提醒`. Use the error labels for direction/order, sign, unit, omitted condition, transcription, boundary, arithmetic, formula/definition, and concept confusion. Review notes link to it and feed repeated error types back into the cram card; do not paste the full log into each review note.

## Mock Exams

Default to two sets: A is consolidation, B is advanced. Source priority is prior course exams, reputable open university exams, then textbook exercises. Rewrite values/wording and label each source. Include total score, duration, closed-book note, points, complete question types, and answers in a separate collapsed section. For mass practice, release one module batch at a time and update the Mistake Log after each batch.

## Mary Workflow Contract

For `/mw-exam`, one chapter, one whole-exam package, or one mock-exam package is a bounded Mary Workflow milestone. Preserve plan interview, explicit assumptions, run grant, lease, review evidence, stop/resume, debug, and cycle archive. A review deliverable is a relative local source note, local schedule record, or local Mistake Log record by default. Do not mark done until local placement, scope, labels, self-test, and evidence are checked.
