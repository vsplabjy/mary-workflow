# Host capability contract

Read [task-policy.md](task-policy.md) for shared role and host-setting rules. Capability discovery uses actual tool schemas; an installed CLI alone does not establish tool availability or authorization.

## Capability discovery and fallback

The main agent inspects actual tool schemas and records available, unavailable, or unknown capabilities. `scripts/mw_host.py capabilities` defaults to unknown; pass `--json` with booleans only for verified host capabilities. The helper does not query providers, read host configuration, or install tools.

| Capability | When present | Fallback |
| --- | --- | --- |
| workers | Choose scoped delegation where it merits the cost; single-agent remains available | `single_agent` with the same formal evidence checks and disclosed lack of independent-agent review, unless independent review is required; then report the unmet requirement |
| worker_resume | Continue the actual prior worker attempt when valid | New attempt with persisted context and residual-change inspection |
| worker_interrupt | Notify/intercept the actual worker when stopping | Stop dispatch and acceptance locally; report inability to verify remote process termination |
| readonly_enforcement | Apply host permissions to exploration/review | Describe scope as an instruction, not enforced isolation; arbitrary shell still permits writes |
| isolated_workspaces | Isolate conflicting resource/file work when useful | Serialize coupled tasks; preserve user changes |
| structured_questions | Ask concise options for material uncertainties | Plain text with real answers and the same authorization semantics |
| progress_list | Mirror persisted phase/task progress | Plain-language progress updates |
| native_memory | Use relevant host knowledge as a retrieval aid | Project brief, evidence, and records suffice |
| native_goal | Reflect an explicitly requested goal | Persisted workflow remains complete without it |
| hooks | Optional read-only lifecycle reminders | Core state checks occur in the normal command flow |

Example capability projection, without changing state:

```bash
python scripts/mw_host.py capabilities --json '{"workers":true,"worker_interrupt":true,"hooks":false}'
```

Unknown is not false. Discover the exposed tools before selecting a compatible route. The main agent records the selected execution mode using the runtime contract; do not invent a second agent identity to evade the independent-review check. Worker identity validates protocol consistency, not cryptographic proof of a distinct model invocation.

## Optional Codex hooks

Codex currently supports lifecycle `hooks.json` adjacent to active configuration, including a trusted project `.codex/hooks.json`, inline hooks, and plugin bundles. Hook definitions need the host's trust review; changed definitions may need renewed trust. Commands receive JSON with `cwd` and `hook_event_name`; this adapter also accepts the camel-case alias. Verify the installed host's support before registration. These details were checked against [official OpenAI hooks documentation](https://learn.chatgpt.com/docs/hooks) on 2026-09-17.

`mw_host.py hook-config --project /absolute/project` prints three short-timeout hook definitions using the project's pinned `.mary-workflow/runtime/scripts/mw_host.py`. It does not create or change `.codex/hooks.json`, trust records, plugins, global settings, or shell files. Existing user hooks must be preserved if the user later authorizes registration. A project upgrade must include the handler in its pinned bundle before the generated definition can run.

| Event | Adapter output |
| --- | --- |
| SessionStart | Current phase, task/run identity, and legal actions as advisory context |
| PreCompact | Reminder to persist material findings and unfinished task evidence |
| Stop | Reminder about remaining task records, without restarting work |

The handler reads a bounded state/task projection and always returns `continue: true`. Missing, incompatible, malformed, or oversized input/state fails open. It does not create files, inspect transcripts or credentials, grant authorization, change state, or run acceptance. It cannot know whether unpersisted working memory exists. The printed command uses `-B` to prevent Python bytecode writes and a three-second host timeout. Hook paths are absolute so running from a project subdirectory is supported.

Hook configuration and handler behavior are locally tested. Trust registration and lifecycle delivery require a real supported host session; printing configuration does not prove a hook is active. Use the same no-hooks workflow when unavailable. The main agent must interrupt real host workers: the local stopped-state barrier does not remotely terminate them.

## Task-sized execution

Worker availability is a capability, not a mandate to delegate. Select single-agent execution for bounded or tightly coupled work; use workers for useful parallelism, context isolation and independent review. Settled-method experiments use the independent experiment runtime, without milestone initialization or bundle/SDD audits. The local supervisor currently requires Linux; use a native scheduler for remote jobs.
