# Lightweight experiment contract

Experiments are independent of the milestone state machine. They require Linux `/proc` and Python's standard library. They never create a dummy milestone, import `mw_workers`, scan the repository or automatically audit a bundle. Existing strict tasks and older fixed project runtimes retain their lifecycle. Invoke the installed experiment script explicitly for an independent new experiment; do not silently replace a project's runtime.

## Execution and persistence

`run` accepts literal argv after `--`. Shell syntax is not evaluated unless the caller explicitly chooses a shell executable. The project directory, known resource allocation and cost budget must match the user's authorization. A configured resource is a same-user, same-host cooperative claim, not hardware scheduling or detection of other users. Use the assigned physical GPU UUID consistently across projects. GPU selection belongs in the actual command/environment. Timeout applies to the local process group only. The command must remain in the foreground; daemonized services and submitted jobs need their native service/job supervisor. Completion refers to the foreground child exit, not proof that detached external work ended.

Each run lives in `.mary-workflow/experiments/<run-id>/` and has `run.json`, stdout/stderr, supervisor diagnostics and an optional small config snapshot. The default output directory is new and private. Explicit output directories must also be new to avoid replacing older runs. The launcher adds the usual exact ignore rules, without scanning or initializing the project. One exclusive run ID prevents duplicate startup. A retry uses a new ID; old records and failures remain.

A short lock serializes launch and stop. USER_STOP is persistent and checked under that lock immediately before child creation, then every 0.1 seconds. The detached supervisor records process PID, Linux boot ID/start ticks, actual exit code and elapsed time. Status reads only the record and `/proc` identity. Loss of the supervisor yields `unknown`, never a fabricated success. Stop can reconcile a surviving exact child; a resource claim with a surviving orphan blocks a new claimant. No automatic recovery/restart is performed. The caller must use a reliable native job service for machines that clean up session processes or for remote/distributed jobs.

Lifecycle: starting -> running -> completed / failed / stopped. Unknown is an observation when the supervisor disappears; it does not discard the original record. Completed means exit code 0 only. Assessment remains unreviewed; provenance is partial because neither the full working tree nor data dependencies were audited. Killing arbitrary recorded PIDs without matching identity is forbidden.

## Startup cost and provenance

Startup reads at most a 1 MiB named config and bounded Git HEAD metadata (1 second timeout). Larger config content is not read; record its size/path and the missing snapshot. Git HEAD is a reference, not proof of the dirty working tree. No preflight checkpoint/dataset hashing, full package export, recursive discovery or automatic pilot. Metrics reads are opt-in through compare, bounded to 1 MiB, and accept only finite numeric values. The config snapshot retains original bytes; it is not necessarily a resolved composition, so the agent must preserve actual overrides in argv.

Record `launch_prepare_ms`, `process_spawn_ms` and `process_elapsed_ms`; measure end-to-end CLI launch separately in benchmarks, including the bounded startup handshake. Distinguish first progress latency from process creation. Initial targets are warm launch p95 <=2 seconds and optional preparation <=10 seconds, excluding model imports/loading/compilation. These are engineering targets, not measured GPU performance.

Audit only individually selected files from exited runs, streaming SHA-256 once per explicit request. Detect ordinary size/mtime/inode changes during reading. Audit records remain separate and do not promote provenance or scientific claims. A later hash of current inputs cannot establish launch-time identity. Missing provenance is reported; controlled reproduction requires the user's applicable resource authorization, never an automatic training rerun.

## Task-sized process

Use direct single-agent work for small authorized changes (`skills/quick/SKILL.md`), this experiment lifecycle for settled-method trials, and the strict milestone/SDD lifecycle for explicitly chosen acceptance and cross-cutting changes. Do not bypass an already active bound change or a stopped project run by relabeling its work. Reaching a milestone's repair-budget limit does not convert that work into an "experiment": launching a run that repeats the exhausted milestone's work needs the user's recorded authorization per [repair-contract.md](repair-contract.md). Reuse valid evidence, independent review at meaningful boundaries, and current context. Unknown dependencies limit a claim; they need not prevent exploratory execution.

## End-of-round presentation

The main agent delivers a static HTML report for each ended experiment round, including failed or stopped rounds, following [report-contract.md](report-contract.md). Use actual run records and saved results; link the package from `.mary-workflow/reports/index.html` and give its exact path to the user. Keep `assessment_status`, provenance and scientific claims unchanged. A user-requested live report identifies its snapshot time and unfinished work. The supervisor records execution only; report creation happens when the agent observes and delivers the result, not through an invented post-chat reporting service. Never delay launch or rerun training to fill report sections.

## Design references

The 2026-10-19 design discussion selected these ideas; upstream versions may evolve:

- [Superpowers inline execution](https://github.com/obra/superpowers/blob/main/skills/executing-plans/SKILL.md): reuse one implementation context and concentrate review.
- [OpenSpec actions and optional verification](https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md): actions and dependencies rather than extra phase ceremonies.
- [GSD quick path](https://github.com/gsd-build/get-shit-done/blob/main/docs/USER-GUIDE.md): research and extra verification can be selected rather than repeated.
- [autoresearch](https://github.com/karpathy/autoresearch/blob/master/program.md): bounded trials and concise metrics. Mary does not copy its automatic Git resets or indefinite execution.
- [Deep Agents](https://docs.langchain.com/oss/python/deepagents/subagents): delegation for context isolation, avoiding overhead on simple tasks.
- [Spec Kit](https://github.com/github/spec-kit#choose-your-process) and [BMAD](https://github.com/bmad-code-org/BMAD-METHOD#why-bmad): independent entry points and task-sized planning.
- [Hydra output directories](https://hydra.cc/docs/tutorials/basic/running_your_app/working_directory/) and [MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/): run-oriented config/metric/artifact records, without adding either dependency.
