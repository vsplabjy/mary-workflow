---
name: lecture-learning
description: "Run the complete local course Lecture learning flow: organize a Course Hub note, reuse Slide to Lecture notes, preserve a raw recording transcript, correct ASR against slides, and fuse only classroom additions with source markers. Use for requests to study a Lecture or combine slides with lecture transcription."
---

# Lecture Learning

This is the course-level orchestration skill. Local files are the default source of truth. Load `skills/slide-to-lecture/SKILL.md` for Stage 1 and `skills/roundtrip-screenshot/SKILL.md` only when image cropping or screenshot verification is needed. Do not duplicate the Slide workflow.

## Course Information Architecture

Inspect the existing Course Hub and sources relevant to the requested Lecture. Reuse its map, hierarchy and index; update only affected links. Build or reorganize the full Course Hub only when requested or absent and necessary for the task.

When creating a Course Hub, use this order:

1. Course positioning callout.
2. Overall knowledge map with 3–7 pillars or a dependency flow.
3. Numbered Lecture index with topic and completion standard.
4. Lab / Homework / Project index paired with relevant Lectures.
5. Schedule and deadlines.
6. Review, cheatsheet, and Mistake Log links.
7. Source Index and environment details.
8. Exactly one next 8–25 minute action.

Lecture notes are direct Course Hub children in the local course tree. Raw source files belong beside their owning Lecture note or under the local Source Index and must not interrupt the Lecture sequence.

If the project has no course/notes tree, use a project-local path such as `notes/<course>/`. Keep `.mary-workflow/` for workflow state and reports only.

## Three Stages

### Stage 1: Slide foundation

Classify the material and invoke `slide-to-lecture`. Reuse an existing empty Lecture note. Produce the structured local slide note and link the complete original PDF at the final `## 📎 原始 Slides` section.

### Stage 2: Raw recording file

Under the Lecture note's `📎 原始 Slides` section, immediately after the PDF link, create or reuse the local file `<course code> Lecture <N> — 课堂录音转写（raw）.md`. Keep the pasted transcription raw and traceable. When a recording transcript is absent, deliver the supported slide note and mark recording integration pending; request the transcript only for the recording-dependent part. Never invent a raw transcript.

### Stage 3: Correct and fuse

Read the raw transcript and the slide note together. Slides are ground truth for terminology, names, symbols, and formulas. Correct ASR errors, restore Greek letters/subscripts/units, convert spoken mathematics to KaTeX, and repair broken derivations. Mark unresolved interpretation as `⚠️存疑：...`; never silently guess.

Only add information absent from slides: derivation steps, teacher emphasis, exam traps, examples, analogies, trade-offs, or corrections. Fuse it into the relevant slide section and wrap every addition in a `🎙 课堂补充` callout or details block. Keep raw text unchanged.

Sync useful English terms to English learning. Put exam points and common mistakes in the Lecture summary. Keep one focused learning block at a time and split long recordings by topic.

## Execution

Use the course route in [shared task policy](../../references/task-policy.md); it owns direct versus formal execution and authorization.

## Delivery Checklist

- Course Hub map, ordering, local parentage, and Source Index are coherent.
- Slide foundation explicitly used the Slide skill.
- When a transcript was provided, its raw file is linked directly after the original PDF; otherwise recording integration is marked pending.
- Terminology, Greek letters, formulas, units, and derivations follow slides.
- Every recording-only addition has a `🎙` marker; uncertainty has `⚠️存疑`.
- Summary contains exam points, mistakes, deadlines, and one next action.
