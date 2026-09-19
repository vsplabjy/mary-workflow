# Tasks

## 1. Integrate and validate the SDD lifecycle

- [ ] 1.1 Implement the bound specification lifecycle and verify parser, runtime integration, regressions and generated surfaces

```mary-task
{
  "id": "milestone-1",
  "deliverables": [
    "scripts/mw_sdd.py",
    "scripts/mary_workflow.py",
    "scripts/mw_workers.py",
    "scripts/mw_bundle.py",
    "scripts/mw_codex.py",
    "tests/test_mw_sdd.py",
    "tests/test_sdd_integration.py",
    "tests/test_cycle_archive.py",
    "README.md",
    "SKILL.md",
    "references/sdd-contract.md",
    "references/state-contract.md",
    "references/subagent-contract.md",
    "skills/plan/SKILL.md",
    "skills/run/SKILL.md",
    "skills/status/SKILL.md",
    "skills/cycle/SKILL.md",
    "references/phases/mw-plan.md",
    "references/phases/mw-ready.md",
    "references/phases/mw-execute.md",
    "references/phases/mw-review.md",
    "references/phases/mw-resume.md",
    "commands/mw-plan.md",
    "commands/mw-run.md",
    "commands/mw-status.md",
    "commands/mw-cycle.md"
  ],
  "acceptance": [
    "python -m unittest discover -s tests -p test_mw_sdd.py",
    "python -m unittest discover -s tests -p test_sdd_integration.py",
    "python -m unittest discover -s tests",
    "python scripts/mw_surfaces.py --check",
    "git diff --check"
  ],
  "estimated_scope": 23,
  "gate": "auto",
  "covers": {
    "spec-driven-planning::Authoritative change tasks::Valid change is bound": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Authoritative change tasks::Scenario coverage is incomplete": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Authoritative change tasks::No behavior changes": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Frozen specification identity::Bound source changes": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Frozen specification identity::Task is accepted": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Explicit instruction authorization::User directly requests execution": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Scenario review evidence::Review omits a scenario": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Recoverable specification archive::Finished change is archived": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Recoverable specification archive::Archive is interrupted or conflicts": [
      "check-1",
      "check-2",
      "check-3"
    ],
    "spec-driven-planning::Recoverable specification archive::Accepted product changes before archive": [
      "check-1",
      "check-2"
    ],
    "spec-driven-planning::Recoverable specification archive::Unfinished cycle is archived": [
      "check-1",
      "check-2",
      "check-3"
    ],
    "spec-driven-planning::Existing workflow compatibility::Existing unbound state is loaded": [
      "check-1",
      "check-2"
    ]
  }
}
```
