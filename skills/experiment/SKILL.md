---
name: experiment
description: Start, observe, stop, compare or explicitly audit experiments without milestone initialization or pre-launch repository hashes. Use /mw-experiment or when the user has settled the method and asks to run a configuration or experiment immediately.
---

# Mary experiments

Shared rules: [task policy](../../references/task-policy.md).

Read [experiment contract](../../references/experiment-contract.md). Use `scripts/mw_experiment.py` from the installed Mary skill, or an explicitly upgraded project bundle that contains it. This independent runtime does not read milestone state, verify a bundle, or bind SDD. Do not wrap experiments in `run_validation`.

## Start promptly

Reuse the agreed method, command, configuration, inputs, output convention, resource allocation and budget. A request to run is execution authorization; ask only for necessary missing information. If the method is settled, do not research it again or create proposal/design/tasks, a full brief, worker dispatches or review gates. A stopped run stays stopped until a new run is explicitly authorized. An independent experiment does not accept, resume or complete an existing strict milestone.

Check only the named entry/config/input paths, actual known resource conflicts, the stop request and duplicate run. Skip recursive data scans, repository/checkpoint SHA-256, full tests, environment dumps and repeated smoke runs. Read existing evidence once when needed. Changing only seed, LR or step count in a working recipe does not justify another pilot. When an actual implementation change warrants a targeted syntax/shape check, keep it bounded; prefer the first real training step over a separate reload. The preparation budget is 10 seconds for optional checks, not permission to overlook a real conflict.

Resolve argv as data, preserving literal arguments. Example (replace paths and resources with the user's actual settings):

```bash
python /path/to/mary-workflow/scripts/mw_experiment.py run --config configs/train.yaml --resource GPU-actual-uuid --timeout 3600 -- python train.py --config configs/train.yaml
```

Use `--output-dir` only for a new directory, and ensure the training command actually writes there. The runner exports `MARY_RUN_ID` and `MARY_OUTPUT_DIR`; it cannot force arbitrary training code to honor them. It also cannot enforce a timeout on remote jobs submitted by a command. Use the existing scheduler for remote work, with its job ID and native stop operation, rather than pretending a local PID owns that job. Resource claims coordinate this user's Mary experiments on this host; inspect known external ownership before starting a GPU task. The flag alone does not bind CUDA devices.

Report run ID, observed status and log/output locations immediately. The detached supervisor owns the child and exit code; keep the experiment running after the chat ends. Do not mark a live process finished merely to end a workflow turn.

## Observe and use results

- `status <run-id>` / `list`: read small records; no scans, hashes or full log rereads. Inspect log tails or incremental metrics only as needed. Healthy runs need no repeated validation. Preserve persistent USER_STOP.
- `stop <run-id>`: persist the request, terminate the exact recorded process group and preserve logs. Never restart automatically.
- `compare <run-id> ...`: collect finite scalar values from each run's JSON metrics file. Set `--metrics-file` at launch if the application uses another location; otherwise use `<output-dir>/metrics.json`. Compare actual configs, data split, metric definition and compute budget before making a claim. Missing or NaN values are not successful evaluation.
- `audit <run-id> --artifact <file> ...`: explicitly hash selected, exited-run files. This records post-run integrity, not launch-time identity, reproducibility or scientific acceptance. Do not recursively audit by default or rerun training to repair missing metadata.

Program exit, result validity, provenance and scientific acceptance are separate. Keep `assessment_status: unreviewed` until the requested domain review exists. A candidate comparison or formal publication may warrant independent review or controlled reproduction; ordinary trials do not each need a verifier. Humanizer is unnecessary for logs and short status updates.

At the end of an agreed experiment round (success, failure or stop), create and browser-check the HTML presentation required by [report contract](../../references/report-contract.md), then deliver its exact path. Use `.mary-workflow/reports/<timestamp>-<run-or-round-id>/index.html` and update the aggregate index. Reuse saved visual results and metrics; do not rerun training for presentation. For a user-requested in-progress report, label it a timestamped snapshot. Detached execution does not itself author reports; do this at the next authorized completion observation/delivery without changing run or assessment state. A milestone whose repair budget is exhausted is not thereby an experiment: repeating that work needs the user's recorded authorization ([repair contract](../../references/repair-contract.md)).
