---
name: roundtrip-screenshot
description: Render, crop, redact, or capture images and visually re-read every result before delivery. Use for slide/PDF crops, UI screenshots, or answer redaction.
---

# Round-trip Screenshot Check

The invariant is: capture or crop, then read the output back, then use it only after visual verification. An unread image is not delivery evidence.

## PDF Crop

1. Render the target page at high resolution: `pdftoppm -png -r 300 -f N -l N input.pdf output/page`.
2. Read the full-page PNG and identify the complete boundary, including captions, labels, arrows, and legends.
3. Crop slightly large, trim white margins, and add a small white border. Prefer `-trim` over a tight guessed box.
4. Read the cropped image again. Confirm no content is cut, shifted, blurred, or missing before embedding it.

For answer redaction, detect real grid/border coordinates where possible, paint opaque blocks, flatten the output, and zoom/read again to confirm no answer pixels remain.

## UI Screenshot

Run only the requested system tests, list every generated PNG, read every image, describe the visible state, compare it with the action/file name, and report concrete defects. Preserve or remove the screenshot directory only after the report says where it is.

## Stop Conditions

If a crop is incomplete, a redaction leaks, or a UI state is inconsistent, do not embed or claim success. Re-render/re-crop/re-run and repeat the round trip.
