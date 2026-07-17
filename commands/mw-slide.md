---
description: Run the Mary Workflow direct Slide to Lecture preparation flow.
argument-hint: [course/material and source context]
---

# /mw-slide

Use the direct slide preparation profile before `/mw-learn` when the user only has slides.

1. Require `/mw-init` state and render `mw-slide` with `mw_codex.py`.
2. Load `skills/slide-to-lecture/SKILL.md` and classify the material.
3. Follow the shared Mary planning, execution, review, stop/resume, and cycle gates for one bounded material set.
4. When complete, leave the Lecture page ready for `/mw-learn` Stage 2 and report missing PDFs/images explicitly.
