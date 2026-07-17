---
name: slide-to-lecture
description: Convert course slides into structured Notion Lecture notes with preserved English terminology, KaTeX formulas, diagrams, deadlines, and source links. Use for Lecture, Homework, Lab, or Project material before the recording-integration flow.
---

# Slide to Lecture

Use this skill as the foundation for `lecture-learning`; do not create a competing slide-only workflow.

## Classify First

- **Lecture**: build a learnable note with formulas, derivations, diagrams, conclusions, and moderate extensions.
- **Homework**: record the prompt and add an error-check card; do not solve it or provide a final answer.
- **Lab / Project**: preserve requirements, constraints, and a light translation; do not write the student's code or perform the experiment for them.

## Course Placement

Use the existing empty page when the user has already created a page containing a PDF, pasted slides, or a note skeleton. Otherwise create or reuse a direct child of the Course Hub. Keep Lecture, Lab, Homework, Project, Review, Mistake Log, and Source Index as separate groups.

Lecture naming: `<course code> Lecture<N> — <topic>`. Keep numbering consistent within a course. Never use local filenames or upload order as the course outline.

## Lecture Output Order

1. Header callout: topic, textbook/pages, and the 1–3 main learning threads.
2. Numbered sections with formulas in KaTeX, why each derivation step is valid, and the relevant original slide image.
3. A short conclusion/cue callout at the end of each section.
4. Summary, homework/deadlines, and the next 8–25 minute action.
5. `## 📎 原始 Slides` as the final H2, with the complete PDF embedded when a file URL is available.

Do not place formulas in table cells. Preserve meaningful English phrases and add a Chinese gloss at first use. Put new terms into the existing English-learning destination when available.

## Images and Deadlines

When a slide PDF file URL is available, render and inspect the required pages before embedding them. Use `skills/roundtrip-screenshot/SKILL.md` for precise crops. If only parsed text is available, use Mermaid/KaTeX as a temporary fallback and explicitly report which images need the PDF later; never silently omit required figures.

For every explicit deadline, write it in the Course Hub and create a deduplicated calendar event in `Asia/Shanghai`. Include the source, submission platform, and problem range.

## Acceptance

- Type classification and parent/empty-page reuse are correct.
- Every essential diagram is embedded, or has an explicit missing-PDF placeholder.
- Formulas render as KaTeX and derivations explain why.
- Section conclusions, summary, deadlines, and next action exist.
- No Homework/Lab/Project work is completed on the student's behalf.
