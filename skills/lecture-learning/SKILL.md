---
name: lecture-learning
description: "Run the complete course Lecture learning flow: organize a Course Hub, reuse Slide to Lecture notes, create a raw recording transcript child page, correct ASR against slides, and fuse only classroom additions with source markers. Use for requests to study a Lecture or combine slides with lecture transcription."
---

# Lecture Learning

This is the course-level orchestration skill. Load `skills/slide-to-lecture/SKILL.md` for Stage 1 and `skills/roundtrip-screenshot/SKILL.md` only when image cropping or screenshot verification is needed. Do not duplicate the Slide workflow.

## Course Information Architecture

Before editing a Lecture, inspect the Course Hub, existing child pages, syllabus/schedule, and Source Index. Build the knowledge map first, then place pages by dependency, engineering flow, or teaching order.

Course Hub fixed order:

1. Course positioning callout.
2. Overall knowledge map with 3–7 pillars or a dependency flow.
3. Numbered Lecture index with topic and completion standard.
4. Lab / Homework / Project index paired with relevant Lectures.
5. Schedule and deadlines.
6. Review, cheatsheet, and Mistake Log links.
7. Source Index and environment details.
8. Exactly one next 8–25 minute action.

Lecture pages are direct Course Hub children. Raw source pages belong under their owning Lecture or Source Index and must not interrupt the Lecture sequence.

## Three Stages

### Stage 1: Slide foundation

Classify the material and invoke `slide-to-lecture`. Reuse an existing empty Lecture page. Produce the structured slide note and place the complete original PDF at the final `## 📎 原始 Slides` section.

### Stage 2: Raw recording page

Under the Lecture's `📎 原始 Slides` section, immediately after the PDF, create or reuse `<course code> Lecture <N> — 课堂录音转写（raw）`. Keep the pasted transcription raw and traceable. Ask the user to paste the transcript there when it is not supplied.

### Stage 3: Correct and fuse

Read the raw transcript and the slide note together. Slides are ground truth for terminology, names, symbols, and formulas. Correct ASR errors, restore Greek letters/subscripts/units, convert spoken mathematics to KaTeX, and repair broken derivations. Mark unresolved interpretation as `⚠️存疑：...`; never silently guess.

Only add information absent from slides: derivation steps, teacher emphasis, exam traps, examples, analogies, trade-offs, or corrections. Fuse it into the relevant slide section and wrap every addition in a `🎙 课堂补充` callout or details block. Keep raw text unchanged.

Sync useful English terms to English learning. Put exam points and common mistakes in the Lecture summary. Keep one focused learning block at a time and split long recordings by topic.

## Trigger and State Discipline

For `/mw-learn`, treat one Lecture or one bounded topic as one Mary Workflow milestone. The command must preserve the normal plan interview, run authorization, execution lease, review, stop/resume, and cycle rules. Use Notion page IDs/URLs and local source paths as milestone deliverables; do not invent code changes for content work.

If the source page already exists, update it in place. If a duplicate was created, move content back, remove the duplicate through the available Notion operation, and repair Course Hub links.

## Delivery Checklist

- Course Hub map, ordering, parentage, and Source Index are coherent.
- Slide foundation explicitly used the Slide skill.
- Raw transcript page is the Lecture child directly after the original PDF.
- Terminology, Greek letters, formulas, units, and derivations follow slides.
- Every recording-only addition has a `🎙` marker; uncertainty has `⚠️存疑`.
- Summary contains exam points, mistakes, deadlines, and one next action.
