# Mary Workflow Development Log

本日志按 git 提交顺序记录 Mary Workflow 的开发过程。时间使用仓库提交时间，时区为 `+08:00`。

## 2026-05-18 14:30:57 +08:00

Commit: `cc636e8` - `Initial Mary workflow skill`

完成内容：

- 创建 `mary-workflow` Codex skill 项目骨架。
- 编写 `SKILL.md`，定义 `/mw-init`、`/mw-start`、`/mw-next`、`/mw-resume`、`/mw-status`、`/mw-stop` 的最小行为。
- 新增 `scripts/mary_workflow.py`，实现初始 `.mary-workflow/` 创建、状态读写、prompt 顺序推进、状态展示和停止。
- 新增 `references/state-contract.md`，描述 `.mary-workflow/state.yaml` 的初始字段。
- 新增 `agents/openai.yaml`，提供 Codex UI 元数据。

验证：

- 运行 skill 验证，结果为 `Skill is valid!`。
- 做过 `init -> start -> complete-current -> status -> stop` 的冒烟测试。
- 将 `~/.codex/skills/mary-workflow` 软链接到本地开发目录。

## 2026-05-18 15:58:33 +08:00

Commit: `5e36d67` - `Add core Mary workflow phases`

完成内容：

- 新增三个核心阶段 prompt：
  - `.mary-workflow/prompts/mw-plan.md`
  - `.mary-workflow/prompts/mw-execute.md`
  - `.mary-workflow/prompts/mw-review.md`
- 将 workflow 从简单 prompt 顺序推进扩展为三阶段状态机：
  - `PLANNING`
  - `EXECUTING`
  - `REVIEWING`
  - `FINISHED`
- 扩展 `scripts/mary_workflow.py`：
  - `plan --task ...`
  - `next-task`
  - `done-task --id ...`
  - `set-phase ...`
- 更新 `SKILL.md` 和 `references/state-contract.md`，同步三阶段模型和任务队列字段。

验证：

- Python 语法检查通过。
- 运行 skill 验证，结果为 `Skill is valid!`。
- 冒烟测试覆盖 `init -> start -> plan -> next-task -> done-task x3 -> set-phase FINISHED`。

## 2026-05-18 19:28:09 +08:00

Commit: `013c599` - `Add bilingual phase prompt notes`

完成内容：

- 将三个阶段 prompt 改成双语结构：
  - 英文 `Agent Protocol` 作为 AI 执行协议。
  - 中文 `中文说明` 作为人类阅读说明。
- 在 `SKILL.md` 中明确约定：
  - prompt 可以双语。
  - 机器字段、命令、文件名、task id、phase value 保持英文。
  - 用户可见说明可以使用中文。

验证：

- 运行 skill 验证，结果为 `Skill is valid!`。
- 冒烟测试确认 `/mw-init` 能把双语 prompt 正常种到新项目。

## 2026-05-19 18:53:30 +08:00

Commit: `5c7c2f3` - `Strengthen phase prompt guardrails`

完成内容：

- 在三个 prompt 中加入强控制规则：
  - `Phase Gate`：执行前必须读取 `state.yaml` 并确认当前阶段匹配。
  - `Structured Output`：要求输出结构化 JSON。
  - 禁止手改 `state.yaml`。
- 在 `mw-execute.md` 中加入 `Context Isolation`：
  - 只查看和修改当前任务相关文件。
  - 禁止无关大重构、全项目格式化、重命名无关符号。
- 在 `references/state-contract.md` 中明确 `REVIEWING` 是唯一审查阶段值，不使用 `REVIEW`。

验证：

- 运行 skill 验证，结果为 `Skill is valid!`。
- 冒烟测试确认新项目初始化后，三个 prompt 都包含 `Phase Gate`、`Structured Output` 和 `Context Isolation`。

## 2026-05-19 19:08:54 +08:00

Commit: `6244ccd` - `Add state action protocol`

完成内容：

- 在 `scripts/mary_workflow.py` 中新增状态协议层：
  - `update_state(root, phase=None, task_list=None)`
  - `apply_action(root, payload)`
  - `normalize_tasks(...)`
  - `mark_task_done(...)`
- 新增 `apply-action` CLI 子命令。
- 支持从以下输入中解析 AI action：
  - 纯 JSON。
  - Markdown fenced JSON。
  - 前后带说明文字的嵌入式 JSON object。
- 支持 action：
  - `update_state`
  - `mark_task_done`
  - `set_phase`
- 保持旧命令 `plan`、`done-task`、`set-phase` 的兼容实现。

验证：

- Python 语法检查通过。
- 运行 skill 验证，结果为 `Skill is valid!`。
- 测试 `update_state` action 能写入中文任务并切换到 `EXECUTING`。
- 测试 `mark_task_done` action 能标记任务完成。
- 测试最后一个任务完成后自动进入 `REVIEWING`。
- 测试 fenced JSON 模型输出可被解析。
- 测试空任务列表会正确失败。
- 测试旧的 `plan` / `done-task` CLI 仍兼容。

## 2026-05-19 19:34:07 +08:00

Commit: `c140137` - `Add action protocol to phase prompts`

完成内容：

- 将三个阶段 prompt 的控制语义统一为 action envelope：
  - `{"action":"update_state","data":{...}}`
  - `{"action":"mark_task_done","data":{...}}`
  - `{"action":"set_phase","data":{...}}`
- 在每个 prompt 中新增 `Workflow Protocol` 区。
- 要求状态更新统一通过：

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '...'
  ```

- 更新 `SKILL.md` 和 `references/state-contract.md`：
  - 状态更新只走 `apply-action`。
  - prompt 输出必须是 action JSON envelope。
  - 文档中移除旧的 `plan --task`、`done-task`、`set-phase` 作为 prompt 主路径。

验证：

- 运行 skill 验证，结果为 `Skill is valid!`。
- 冒烟测试确认新项目 `/mw-init` 能种下带 `Workflow Protocol` 的 prompt。
- 端到端 action 流转测试通过：
  - `PLANNING -> EXECUTING -> REVIEWING -> FINISHED`
- 检查 prompt/docs，确认不再残留旧状态更新路径。

## State after Commit `c140137`

- 当前分支：`main`
- 当时 HEAD：`c140137`
- 当前工作区：clean
- 远端同步状态：本地 `main` 与 `origin/main` 一致

下一步建议：

- 继续第三步：配置 `.codex-plugin/plugin.json` 和 slash command 接入。
- 在接入插件前，先确认 Codex plugin schema 支持哪些命令定义和上下文注入方式。

## 2026-05-19 19:46:30 +08:00

Third step: Codex plugin bridge.

完成内容：

- 新增 `.codex-plugin/plugin.json`，使用当前本地 Codex plugin manifest 支持的字段。
- 新增 `scripts/mw_codex.py`，作为 Codex alias bridge。
- 支持 `/mw-plan`、`/mw-run`、`/mw-review`、`/mw-next`、`/mw-status`。
- 在 `SKILL.md` 和 `references/state-contract.md` 中记录 alias 行为。
- 明确当前 manifest schema 不定义原生 slash-command routing；slash alias 由 skill 说明和 `scripts/mw_codex.py` 共同处理。

验证：

- `plugin.json` 通过 `python -m json.tool` 校验。
- 确认 manifest 未使用未验证支持的 `commands`、`slashCommands`、`systemMessage` 字段。
- `scripts/mw_codex.py` Python 语法检查通过。
- 运行 skill 验证，结果为 `Skill is valid!`。
- 冒烟测试覆盖 `/mw-plan`、`/mw-run`、`/mw-review`、`/mw-next`、`/mw-status` 的 prompt/context 解析。

## 2026-05-19 20:00:56 +08:00

Fourth step: self-healing debug loop.

完成内容：

- 新增 `DEBUGGING` phase。
- 新增 `.mary-workflow/prompts/mw-debug.md`。
- 在 `state.yaml` 中支持 `last_error` 区块，用于记录失败命令、stderr、return code 和时间。
- 在 `scripts/mary_workflow.py` 中新增：
  - `record_error(...)`
  - `enqueue_fix_task(...)`
  - `record-error` CLI
  - `record_error` action
  - `enqueue_fix_task` action
- `enqueue_fix_task` 会把修复任务插到第一个 pending 任务前面，然后回到 `EXECUTING`。
- 更新 `scripts/mw_codex.py`，支持 `/mw-debug`，并让 `/mw-next` 在 `DEBUGGING` 阶段加载 `mw-debug.md`。
- 更新 `SKILL.md` 和 `references/state-contract.md`，记录 debug phase、debug alias 和 debug actions。

验证：

- `scripts/mary_workflow.py` 和 `scripts/mw_codex.py` Python 语法检查通过。
- `plugin.json` JSON 校验通过。
- 运行 skill 验证，结果为 `Skill is valid!`。
- 冒烟测试确认：
  - 失败命令可以通过 `record-error` 进入 `DEBUGGING`。
  - `/mw-next` 在 `DEBUGGING` 阶段加载 `mw-debug.md`。
  - `enqueue_fix_task` 会创建修复任务。
  - 修复任务会优先于原 pending 任务执行。
  - workflow 会从 `DEBUGGING` 回到 `EXECUTING`。

## 2026-05-19 22:17:04 +08:00

Native slash command registration.

完成内容：

- 新增 Codex 插件原生命令目录 `commands/`。
- 新增 10 个命令文件：
  - `/mw-init`
  - `/mw-start`
  - `/mw-plan`
  - `/mw-run`
  - `/mw-review`
  - `/mw-debug`
  - `/mw-next`
  - `/mw-resume`
  - `/mw-status`
  - `/mw-stop`
- 将主命令风格统一为短横线形式，例如 `/mw-init`，匹配 Codex 命令文件名 `commands/mw-init.md`。
- 更新 `SKILL.md`，明确 native command Markdown 文件负责 UI slash entry，`scripts/mw_codex.py` 负责加载 phase prompt 和 state context。
- 更新 `references/state-contract.md`，记录 `commands/` 目录和 bridge 行为。
- 更新 `scripts/mw_codex.py`，支持 `/mw-resume`，并让 `FINISHED` 阶段返回只读状态上下文。
- 更新脚本和 prompt 中的初始化提示，从 `/mw:init` 改为 `/mw-init`。

验证：

- `.codex-plugin/plugin.json` JSON 校验通过。
- `~/.agents/plugins/marketplace.json` JSON 校验通过。
- `scripts/mary_workflow.py` 和 `scripts/mw_codex.py` Python 语法检查通过。
- 运行 skill 验证，结果为 `Skill is valid!`。
- 确认 10 个 `commands/mw-*.md` 文件存在且 frontmatter 可读。
- 确认 `~/plugins/mary-workflow` 本地插件软链接能暴露 `commands/mw-init.md`。
- 冒烟测试通过：
  - `/mw-init` 对应的 init 能初始化 4 个核心 prompt。
  - `/mw-start` 能进入 `PLANNING`。
  - `/mw-plan` 能加载 `mw-plan.md` 和当前 state。
  - `/mw-run` 能加载 `mw-execute.md` 和当前 task。
  - `/mw-review` 能加载 `mw-review.md`。
  - `/mw-next`、`/mw-resume`、`/mw-status` 在 `FINISHED` 阶段返回只读状态上下文。
  - 未初始化项目调用 phase bridge 时，会提示先运行 `/mw-init`。

## 2026-05-19 22:35:35 +08:00

Hypo-style sub-skill command surface.

完成内容：

- 参考 Hypo-Workflow 的 `skills/<command>/SKILL.md` 实现方式，为 Mary Workflow 新增 10 个命令子技能：
  - `skills/init/SKILL.md`
  - `skills/start/SKILL.md`
  - `skills/plan/SKILL.md`
  - `skills/run/SKILL.md`
  - `skills/review/SKILL.md`
  - `skills/debug/SKILL.md`
  - `skills/next/SKILL.md`
  - `skills/resume/SKILL.md`
  - `skills/status/SKILL.md`
  - `skills/stop/SKILL.md`
- 将 `.codex-plugin/plugin.json` 的 `skills` 从 `./` 改为 `./skills/`，让 Codex UI 像 Hypo 一样发现多个命令级技能。
- 保留根 `SKILL.md` 作为总说明和手动触发兜底。
- 保留 `commands/mw-*.md`，兼容支持 file-based command loading 的客户端。
- 更新 `SKILL.md` 和 `references/state-contract.md`，明确 autocomplete 主要靠子 skill metadata，而不是 `commands/*.md`。

验证：

- `.codex-plugin/plugin.json` JSON 校验通过。
- 全部 10 个 `skills/*/SKILL.md` 文件存在，并包含 `name` 和 `description` frontmatter。
- 运行 skill 验证，结果为 `Skill is valid!`。
- 使用 `codex debug prompt-input '/mw-init'` 和 `codex debug prompt-input '/mw'` 确认 Mary 子技能进入可用 skills 列表：
  - `mary-workflow:init`
  - `mary-workflow:start`
  - `mary-workflow:plan`
  - `mary-workflow:run`
  - `mary-workflow:review`
  - `mary-workflow:debug`
  - `mary-workflow:next`
  - `mary-workflow:resume`
  - `mary-workflow:status`
  - `mary-workflow:stop`

## 2026-07-05

v1.1 milestone workflow refactor.

完成内容：

- 将用户命令面从 10 条收敛为 6 条：
  - `/mw-init`
  - `/mw-plan`
  - `/mw-run`
  - `/mw-status`
  - `/mw-stop`
  - `/mw-debug`
- 裁撤 `/mw-start`、`/mw-next`、`/mw-resume` 和独立 `/mw-review` 的 command/sub-skill 注册。
- 将状态模型升级为 `version: 2` milestone schema：
  - `deliverables`
  - `acceptance`
  - `estimated_scope`
  - `gate`
- 新增 `init --reset`，旧 v1 state 不迁移，需 reset。
- 在 runtime 层强制 phase/action 白名单：
  - `PLANNING`: `update_state`
  - `EXECUTING`: `mark_task_done` / `record_error`
  - `REVIEWING`: `set_phase` / `record_error`
  - `DEBUGGING`: `enqueue_fix_task`
- 删除旧 CLI 后门：
  - `start`
  - `plan --task`
  - `next-task`
  - `done-task`
  - `set-phase`
  - `record-error`
  - `complete-current`
- `apply-action` 先记录 action 名，再执行具体状态变更。
- 拒收非法信封时写入 `log.md`，增加 `rejected_actions` 统计，并返回当前 phase 合法动作。
- `set_phase()` 统一记录 phase transition 日志。
- `mark_task_done` 自动进入 `REVIEWING` 时写入独立日志：
  - `phase EXECUTING -> REVIEWING (auto: all tasks done)`
- `/mw-run` 改为当前 phase 渲染入口，吸收 next/resume/review 行为。
- `mw_codex.py` 在 milestone 边界从 `state.yaml` 渲染干净上下文包。
- 新增 `.mary-workflow/reports/<milestone-id>.md` 验收报告落盘。
- 四个 phase prompt 同步加入统一 Language Policy。
- review prompt 明确禁止 `update_state`，只允许 `set_phase` / `record_error`。
- `references/state-contract.md` 重写为 v2 milestone contract。

验证：

- `python -m py_compile scripts/mary_workflow.py scripts/mw_codex.py` 通过。
- `.codex-plugin/plugin.json` JSON 校验通过。
- 临时目录冒烟测试通过：
  - `init`
  - `update_state` milestone plan
  - 非法 `update_state` 在 `EXECUTING` 被拒
  - `mark_task_done` 自动进入 `REVIEWING`
  - review `set_phase EXECUTING` 可打回当前 milestone
  - 再次完成后 `set_phase FINISHED`
  - 日志可区分 `update_state` 与 `set_phase`

## 2026-07-09

v2.1 cycle-aware planning refactor.

完成内容：

- 将状态契约统一为 `version: 2.1`，新增 `cycle` 字段，并拒载早期 state。
- `/mw-init` 产出 `.mary-workflow/project-brief.md`，并在 `state.yaml` 的 `project` 段记录 brief 路径和输出语言。
- `init` 默认中文，`config.yaml` 新增 `output.language`，命令层 `status` / `stop` / `apply-action` 摘要按配置输出。
- 新增 `update_project` 信封，允许在 `PLANNING` 中合法修正项目结构、技术栈、测试方式和语言配置。
- `/mw-plan` 引入自适应多轮 interview 机制，`config.yaml` 新增 `plan.interview`、`plan.interview.max_rounds` 和每轮问题范围。
- `update_state` 在 interview 开启时强制要求 `clarifications`，缺失即拒收。
- 2026-07-09 追加增强：interview 改为自适应多轮递进，默认 1 轮、上限 3 轮；小任务可 0 轮默认假设确认，大任务可 2 到 3 轮深挖；后续轮次必须锚定上一轮答案中的不确定点。
- 新增 `/mw-cycle`、`commands/mw-cycle.md` 和 `skills/cycle/SKILL.md`，将当前 cycle 的 state/log/reports 归档到 `.mary-workflow/cycles/<cycle>/`，清空活动 milestones/reports/log，并开启下一 cycle。
- 报告路径 cycle 化为 `.mary-workflow/reports/<cycle>/<milestone-id>.md`。
- `project-brief.md` 作为跨 cycle 长期记忆保留，milestones、reports、log、lease 和 clarifications 作为 cycle 内短期记忆滚动归档。
- `.codex-plugin/plugin.json`、`SKILL.md` 与 `references/state-contract.md` 同步 v2.1 命令面和状态契约。

验证：

- `python -m py_compile scripts/mary_workflow.py scripts/mw_codex.py` 通过。
- `.codex-plugin/plugin.json` JSON 校验通过。
- `git diff --check` 通过。
- 临时目录冒烟测试通过：
  - `init` 生成 v2.1 state、`config.yaml` 和 `project-brief.md`。
  - `update_project` 可修正语言、技术栈和测试命令。
  - 缺失 `clarifications` 的 `update_state` 在 `plan.interview: on` 时被拒收。
  - 新 config 生成 `plan.interview.max_rounds: 3` 和 `plan.interview.questions_per_round: "3-5"`，`mw-plan` 上下文可渲染多轮 interview 配置。
  - 合法 `update_state` 进入 `EXECUTING`，`mark_task_done` 自动进入 `REVIEWING`。
  - review `set_phase FINISHED` 完成当前 cycle。
  - `/mw-cycle` 将 C0 的 state/log/reports 归档到 `.mary-workflow/cycles/C0/`，活动 state 切到 C1。

## 2026-07-10

Plan/run authorization boundary fix.

问题证据：

- VideoGS 的一次 `/mw-plan` 将自行推断的 `Round 0` defaults 当作问答纪要，直接提交 `update_state`。
- 旧 `update_state` 强制执行 `PLANNING -> EXECUTING`，没有“计划完成、等待用户运行”的状态。
- 模型继续加载自动循环后完成初始 4 个 milestone，并由 Debug 循环追加 3 个修复 milestone，最终越权跑到 `FINISHED 7/7`。

完成内容：

- 新增 `PLANNED` 阶段，成功定稿只执行 `PLANNING -> PLANNED`。
- 新增 `start_execution` 信封，且只在 `PLANNED` 合法；`/mw-run` 渲染时签发一次性 token，信封必须同时携带 token 和 `authorized_by: /mw-run`。
- 新增 `mw-ready.md`，作为 `/mw-run` 的独立授权关卡。
- `state.yaml` 新增 interview 状态、当前/最大轮次、持久化轮次记录、draft milestones 和最终计划确认字段。
- 新增 `update_interview`，支持 `open` / `resolve` / `propose` / `revise` 四种 plan 交互。
- 每轮问题先落盘再展示；没有用户答案时保持 `awaiting_answers`，禁止把沉默解释为默认同意。
- 1 到 2 milestone 的 0 轮方案必须确认 defaults；3 到 4 milestone 至少 1 个已回答轮次；5+ milestone 至少 2 个已回答轮次。
- 最终 `update_state` 要求显式确认文本、完整 clarifications，并与已展示 draft 完全一致。
- `/mw-plan` 在提问、展示/修订草案和进入 `PLANNED` 后强制结束当前回复，不得运行验收、编辑产品文件或调用 `start_execution`。
- 已初始化的 v2.1 项目再次运行 `/mw-init` 时覆盖刷新核心 prompts，但不重写 `state.yaml`，确保拿到新增 `mw-ready.md` 和硬停止规则。
- `apply_action` 使用深拷贝执行动作，拒收信封不会意外持久化半完成状态。
- plugin manifest 版本统一为 `2.1.0`。

验证：

- `python -m unittest discover -s tests -v`：11/11 通过。
- 直接 `update_state` 跳过 interview 被拒。
- 未明确确认的最终计划被拒。
- `PLANNED` 中的 `mark_task_done` 被白名单拒绝。
- `/mw-run` 前保持 `started_at` 为空；合法 `start_execution` 后才进入 `EXECUTING`。
- 5+ milestones 仅一轮回答时被拒。

### v2.1 nonce and run-lease hardening

本节覆盖并取代上面的同日临时授权设计。

- 状态契约统一为 `version: 2.1`，早期 state 明确拒载，旧项目必须 `/mw-init --reset`。
- `update_state` 只冻结计划并进入 `PLANNED`；它拒绝 `confirmed` / `confirmation` 字段，agent 不能自行声明用户已确认。
- 用户调用 `/mw-run` 本身承担最终确认：渲染器签发绑定 cycle 与 plan digest 的短期单次 grant，`start_execution` 消费后原子完成确认、lease 领取和 `PLANNED -> EXECUTING`。
- 原始 token 仅出现在当次 `/mw-run` 渲染；`state.yaml`、status 和日志只保存 SHA-256 digest、指纹、用途和过期时间。
- 重复渲染会轮换 grant；伪造、重放、过期、错误用途、plan/cycle 变化均拒收。
- execution lease 改为 run 级：只由 `start_execution` 初次领取，在 EXECUTING/REVIEWING/DEBUGGING 间保持同一 run id，FINISHED/replan/cycle 时释放或清空。
- `/mw-stop` 暂停 lease 并清除未消费 grant；再次 `/mw-run` 签发 purpose=resume 的单次 grant，`resume_execution` 保持原 phase 和 run id 续跑。
- 新增 `mw-resume.md`；`mw-ready.md` 改为只读取 `/mw-run` 专用授权区块，不再从 state 读取明文 token。
- `PLANNED` 下可通过 `reopen_plan` 回到 PLANNING 修订，修订会使旧 grant 失效。
- 删除默认值逃生口：所有 defaults/assumptions 必须先落盘、完整展示并等待用户显式确认；`interview: off` 也不例外，`resolve`/`revise` 禁止后置注入 defaults。
- `/mw-run` 的 PLANNED 关卡新增 `Final Plan Confirmation Evidence`，以只读 JSON 原样展示全部问题、记录回答、defaults、clarifications 和 frozen milestones，再允许消费 token。
- plugin manifest 使用 SemVer `2.1.0`，命令、skills、状态契约与 phase prompt 统一标记为 v2.1。

验证：

- `python -m unittest discover -s tests -v`：25/25 通过。
- `python -m py_compile scripts/mary_workflow.py scripts/mw_codex.py` 通过。
- `.codex-plugin/plugin.json` JSON 校验与 `git diff --check` 通过。
- 覆盖 nonce 明文不落盘、grant 轮换/重放拒绝、原子启动、stop/resume、debug/review lease 保持、FINISHED/replan/cycle 释放，以及早期/缺失 version 拒载。
- 剩余信任边界：仓库运行时证明的是“调用者持有 `/mw-run` 渲染 grant”；若要密码学证明由人类而非具备直接进程权限的 agent 发起，必须由 Codex 宿主 slash dispatcher 作为可信签发方。

### v2.1 full-depth init understanding

- 删除 `files[:40]` 与 80 文件上限；机器探测遍历全仓文本文件，只排除版本控制、工作流、依赖/构建/缓存目录、符号链接和二进制。
- 新增完整 inventory 与 SHA-256 fingerprints，分别作为文件账本覆盖 authority 和 cycle 增量比较基线。
- 新增 `mw-init.md` 三遍读取协议：全量盘点、入口/配置/核心/测试精读、基于模块证据的全局综合；大仓库使用分层综合但不允许抽样。
- 新增 `submit_brief` 信封和机器校验：项目定位、架构全景、全量文件账本、非空不确定性、build/test/run 执行证据、三遍分析证据全部必填。
- brief 未完成时 PLANNING 只接受 `submit_brief` / `update_project`，机器阻止提前进入 interview 或 milestone 规划。
- `project-brief.md` 升级为五层完整档案，带 brief version、更新时间和 cycle 戳；提交后 CLI 全文输出，`/mw-plan` 加载全文和文件账本。
- `/mw-cycle` 比较 fingerprints；有新增/修改/删除时进入 `refresh_required` 并暂停归档，增量重读和 `mode=cycle_refresh` 成功后才归档，同时保存 brief 快照。
- 回归覆盖 105 文件无截断、二进制/依赖排除、账本漏项拒收、brief plan gate、五层全文、CLI 全文展示和 cycle 两阶段刷新。

### v2.1 init scan hardening

- `read_state` 对已有 `state.yaml` 使用懒默认值，不再在 status、信封、报告等普通状态读取中扫描和哈希项目树；只有显式 init/cycle/brief 操作执行探测。
- SHA-256 改为 1 MiB 分块流式更新，移除 `Path.read_bytes()` 的整文件内存分配。
- `config.yaml` 新增 `init.ignore` glob 列表，并合并项目根目录 `.maryignore`；默认排除常见 data、checkpoint、output、result、run、log 和 artifact 目录。
- 二进制快速排除补齐 `.pt`、`.pth`、`.ckpt`、`.npy`、`.npz`、`.ply`、`.safetensors`、ONNX/HDF5/Parquet 等 ML 常用格式。
- `/mw-init` 只在 `PLANNING`、`PLANNED`、`FINISHED` 检测简报漂移；执行、审查、调试阶段只刷新 prompt 并记录跳过，已有 `refresh_required` 也不会覆盖活动 phase 的合法动作。
- 回归增加懒读取不调用探测、流式哈希不调用 `read_bytes`、config/.maryignore/ML 文件排除，以及 EXECUTING 中 rerun init 后继续完成 milestone。

## 2026-07-17

v2.2 P0 shared runtime foundation.

Baseline commit: `83ea160` - `P0 finished`

完成内容：

- 新增 `scripts/mw_runtime.py`，集中提供无 workflow phase 知识的公共原语：
  - 直接、Markdown fenced 和说明文字内嵌三种 JSON payload 解析。
  - 顶层 JSON object 与 `action`/`data` 信封形状校验。
  - 同目录临时文件、`O_EXCL`、file `fsync`、`os.replace` 的原子文本写入。
  - 目标文件权限位保持，以及失败后的临时文件清理。
  - Markdown 日志文件初始化与 timestamped entry 追加。
- `scripts/mary_workflow.py` 改为通过兼容适配层调用公共 runtime：
  - `write_state` 和 cycle 日志重置使用 `atomic_write_text`。
  - `append_log` 使用 `append_log_entry`。
  - CLI payload 使用公共 parser 和顶层 object 校验。
  - `apply_action` 使用 `action_envelope_parts`；`EnvelopeError` 仍路由到原有 `reject_action`，保留 rejected state、计数、日志和 `SystemExit` 行为。
- 删除 `mary_workflow.py` 中重复的 JSON 扫描与解析实现。
- runtime 专项测试统一放在 `tests/test_mw_runtime.py`，便于按模块名直接发现。
- P0 未加入 `/mw-paper`、paper schema、Marp、KaTeX 或其他 P1+ 功能。

验证：

- `python -m unittest discover -s tests -v`：41/41 通过，其中原 v2.1 workflow 边界回归 29/29、P0 runtime 专项 12/12。
- init 专项 3/3 通过：fresh init、active-phase init、prompt refresh state preservation。
- 故障注入覆盖 file `fsync` 和 `os.replace` 失败；旧 `state.yaml` 保持完整，临时文件得到清理。
- state read/write round trip 字节稳定，原 action 预日志顺序与 invalid data rejected path 保持不变。
- `python -m py_compile`、`git diff --check` 和 P0 范围扫描通过。

## 2026-07-18

v2.2 P1 paper state and `/mw-paper` skeleton.

完成内容：

- 新增独立的 `.mary-research/papers/<paper-id>/` 工作区，每篇论文使用 `state.json` 和 `log.md`，状态契约固定为 `paper_state_schema: 1`。
- paper state 不依赖 `/mw-init`，不读取或修改 `.mary-workflow/` 的 phase、grant 或 lease；`/mw-init --reset` 与 `/mw-cycle` 均保留论文工作区。
- v2.1 项目扫描器忽略 `.mary-research/`，避免运行时状态进入项目理解账本和 fingerprint 基线。
- 新增规范化 paper id：arXiv 使用保留显式版本号的 `arxiv-<identifier>`，其他来源默认使用 `local-<source-sha256-prefix>`；拒绝路径分隔符、`..` 和非规范 id。
- source、阶段输入和阶段输出统一使用小写 SHA-256 指纹；P1 只接收预计算 fingerprint，不抓取或解析论文。
- 新增 `read -> summary -> slides` 与 `read + summary -> quiz` 四阶段依赖图，以及 `pending`、`in_progress`、`complete`、`failed`、`stale` 进度机。
- 新增 `start_stage`、`complete_stage`、`fail_stage`、`reset_stage`、`update_source` 信封；依赖未完成、输入 lineage 变化、非法 artifact 路径和非法 fingerprint 均拒收。
- source fingerprint 变化或上游 reset 会将已经开始的下游阶段级联标记为 `stale`；从未开始的阶段保持 `pending`。
- 新增 `scripts/mw_paper.py` 和 `/mw-paper` 的 `create`、`list`、`status`、`apply-action` 独立命令面，复用 P0 的信封校验、原子写和 append log 公共 runtime。
- 新增 `commands/mw-paper.md`、`skills/paper/SKILL.md` 和 `references/paper-state-contract.md`，同步 plugin manifest、根 skill、OpenAI interface 与 README。
- P1 明确不生成 `paper-notes.md`、`summary.md`、`slides.md` 或 `quiz-log.md`，未提前实现 P2 及后续内容阶段。

验证：

- `python -m unittest discover -s tests -v`：59/59 通过，其中原 v2.1 workflow 边界 29/29、P0 runtime 12/12、P1 paper state 18/18。
- init 专项 3/3 通过：fresh init、active-phase init、prompt refresh state preservation。
- P1 回归覆盖独立创建与幂等、多论文隔离、arXiv/local id、schema 拒载、阶段 gate、失败重试、lineage、source/reset stale 级联、quiz 依赖、非法/损坏信封审计和 CLI 命令面。
- `python -m py_compile`、plugin validator、paper skill validator、manifest JSON 校验和 `git diff --check` 通过。
- plugin cachebuster 更新为 `2.2.0-alpha.1+codex.20260718064000`；当前个人 marketplace 是本地目录而非 Git marketplace，Codex CLI 不支持对其执行 `marketplace upgrade`，现有 skill/plugin 安装均通过符号链接直接指向本仓库。

### v2.2 P2 close-reading entry

Baseline commit: `386cc6a` - `P1 finished`

完成内容：

- 新增 `scripts/mw_paper_sources.py`，隔离单篇论文获取、HTML/PDF 规范化、五维解析质量评估和精读账本校验。
- `prepare-read` 对 arXiv 固定先请求 `/html/<id>`；HTML 不可用或 `text`/`structure` 核心质量失败时自动回退 `/pdf/<id>`。普通本地/远程 HTML/PDF 使用同一解析层。
- 网络获取使用明确 User-Agent、45 秒超时和 64 MiB 上限；PDF 通过 Poppler `pdftotext -layout` 降级抽取，无新增 Python 依赖。
- 每次准备精读落盘 `source.html|pdf`、带 locator 的 `source.md`、`parse-quality.json` 和机器生成的 `read-context.json`。
- 五维矩阵固定为 `text`、`structure`、`equations`、`figures`、`tables`；状态固定为 `pass`、`degraded`、`failed`、`not_applicable`，每维强制 metrics 和 evidence。
- LaTeXML HTML 解析区分公式布局 `ltx_eqn_table` 与科研表格 `figure.ltx_table`，提取表格行和单元格；仅保留图注而没有视觉像素时，figure 诚实标记为 degraded。
- 任一 failed 维度将质量 gate 设为 blocked；degraded/failed 维度必须出现在至少一个 uncertainty 的 `quality_dimensions` 中。
- 新增 `references/paper-notes-contract.md`：`paper-notes.md` 必须包含 schema 1 JSON 账本，强制书目信息、背景、问题、贡献、方法、实验/证明、局限、结论、逐节账本、解析质量和非空不确定性。
- HTML claim locator 使用 `html#<anchor>`，PDF 使用 `pdf:p<N>`；研究 claim、section ledger 和 uncertainty 均拒收无 locator 输入。
- `complete-read` 校验 paper/source 身份、source fingerprint、质量报告 fingerprint、五维状态、必填字段、locator、uncertainty 覆盖和 notes 实际字节 fingerprint 后，才允许 `read -> complete`。
- blocked gate 默认拒绝完成并保持 `read=in_progress`。只有明确 `--override-quality --override-reason` 才可覆盖；覆盖生成 `quality-override-<attempt>.json`，并在 state metadata 和 log 中记录原因与 fingerprint。
- `paper_state_schema: 1` 保持不变，通过可选 stage metadata 向前兼容；source 变化继续复用 P1 stale 级联并自动开启新的 read attempt。
- 更新 `/mw-paper` command、paper skill、根 skill、OpenAI metadata、paper state contract 和 plugin manifest；`summary.md`、`slides.md`、`quiz-log.md` 仍未实现。
- `README.md` 未修改。

验证：

- `python -m unittest discover -s tests -v`：78/78 通过，其中原 v2.1 workflow 29/29、P0 runtime 12/12、P1 paper state 18/18、P2 close reading 19/19。
- P2 覆盖 HTML 优先且不请求 PDF、HTML 404/核心质量失败自动 PDF 回退、LaTeXML 布局表排除、PDF 降级矩阵、source 变更重启、账本合法完成和各类拒收规则。
- 阻断/覆盖测试覆盖静默完成拒收、pass gate 禁止无意义 override、显式用户覆盖、原因文件落盘和 state fingerprint 对齐。
- 真实 arXiv `2401.00001` 冒烟通过：选择官方 HTML，表格行进入 `source.md`，最终 `gate=pass`；同一论文真实 PDF 经本机 `pdftotext` 抽取并生成页码 locator，`gate=pass`。
- `python -m py_compile`、paper skill validator、plugin validator、manifest JSON、`git diff --check` 和 README 零差异检查通过。
- plugin cachebuster 更新为 `2.2.0-alpha.2+codex.20260718072135`；当前 Codex CLI 无 `plugin add` 子命令，现有 `~/.codex/skills/mary-workflow` 与 `~/plugins/mary-workflow` 均通过符号链接直接指向本仓库。

### v2.2 P3 grounded summary

Baseline commit: `4603b01` - `P2 test finished`

完成内容：

- 新增 `scripts/mw_paper_locators.py`，将 `source.md` 的 HTML/PDF marker 构造成确定性 `source-locators.json` 索引。
- source locator 合同固定为 HTML `html#<anchor>` 和 PDF `pdf:p<N>`；每个 locator 必须解析到至少一个非空 source span。
- locator 索引记录 `source.md` fingerprint、raw source fingerprint、source format，以及每个 span 的行范围、规范化内容 SHA-256 和 preview。
- 重复 HTML anchor 不覆盖，统一表示为同一 locator 下的多个 spans；evidence 可在任一对应 span 中解析。
- `prepare-summary` 要求 P2 read 已完成且 `paper-notes.md` 字节与 read output fingerprint 一致，随后生成 `source-locators.json` 和 `summary-context.json` 并启动 summary 阶段。
- summary context 只允许同时满足“存在于 source.md”与“已被 paper-notes.md 接受”的 locator，阻止总结阶段引入未经精读账本覆盖的新 source region。
- 新增 `scripts/mw_paper_summary.py` 和 `references/summary-contract.md`；`summary.md` 固定为 ordered `background`、`method`、`experiments` 三段，每段至少一个 claim。
- claim 四元组固定为 `claim_id`、`claim_text`、`evidence`、`source_locators`；背景/方法/实验 id 分别使用 `Bxx`、`Mxx`、`Exx` 且全局唯一。
- evidence 必须是当前 normalized source span 中可解析的 8-500 字符原文片段；合法 locator 指向错误 span 同样拒收。
- `complete-summary` 重建 locator index，校验 context/input/index/source/notes fingerprints、三段结构、四元组字段、ID、locator 存在性、notes allowlist、evidence containment 和 summary 实际 fingerprint 后才允许完成。
- summary stage metadata 记录 claim 总数、分段计数、引用 locator 数量以及 context/index fingerprints；read reset/source change 继续通过 P1 DAG 使 summary 和下游 stale。
- 更新 `/mw-paper summarize` command/skill、根 skill、OpenAI metadata、paper state contract 和 plugin manifest；slides/quiz 未实现。
- `README.md` 未修改。

验证：

- `python -m unittest discover -s tests -v`：94/94 通过，其中原 v2.1 workflow 29/29、P0 runtime 12/12、P1 paper state 18/18、P2 close reading 20/20、P3 summary 15/15。
- P3 覆盖 HTML 重复 span、PDF page locator、非法/空 span、三段顺序、四元组字段、ID 前缀/唯一性、notes allowlist、evidence 解析、input/output drift、index tamper、CLI 完成和 read dependency gate。
- 真实 arXiv `2401.00001` 的 P2 `source.md` 内存索引通过：137 个 locator、141 个 spans、4 个重复 locator，抽样 evidence 可在对应 span 中解析。
- `python -m py_compile`、paper skill validator、plugin validator、manifest JSON、`git diff --check`、下游产物范围扫描和 README 零差异检查通过。
- plugin cachebuster 更新为 `2.2.0-alpha.3+codex.20260718083702`；当前 Codex CLI 无 `plugin add` 子命令，现有 skill/plugin 安装均通过符号链接直接指向本仓库。

### v2.2 P3.5 readable summary layer

Baseline commit: `a834764` - `P3 finished`

完成内容：

- 保留 P3 的 source locator index、summary context、paper-notes allowlist、evidence span containment 和 summary 状态机衔接，移除 `summary.md` 内嵌 JSON 填表格式。
- summary 阶段改为双文件产物：`summary.md` 只承载面向未读论文同行的博客体正文，`summary-ledger.json` 单独承载机器 claim 账本。
- 正文强制按 Background/背景、Method/方法、Experiments/实验三个 H2 顺序组织且内容非空；编排 prompt 要求方法节成为篇幅和解释重心，讲清直觉、机制与信息流，并允许使用 LaTeX 公式。
- claim ledger 固定为 `summary_ledger_schema: 1`、paper id、原样复制的 inputs 和扁平 claims 数组；每条 claim 仍严格使用 `claim_id`、`claim_text`、`evidence`、`source_locators` 四元组。
- 取消 `direct/inferred` 分类字段，额外字段一律拒收；ledger 只接受直接事实，解释、直觉和串联内容留在正文，不确定内容继续归 P2 uncertainties 和后续专家问答。
- 新增正文与账本双向锚定门禁：每个 ledger id 必须在正文出现，正文 claim id 必须存在于 ledger，B/M/E 前缀必须落在对应章节，独立成行的空锚点拒收。
- `complete-summary` 继续机器校验 locator 可解析、paper-notes 背书交集和 evidence 原文包含；论断语义真伪、正文是否正确使用证据及写作质量明确保留给人工与后续问答验真。
- summary stage output fingerprint 改为覆盖 `summary.md` 与 `summary-ledger.json` 精确字节的 bundle fingerprint；任一文件变化都会改变下游 lineage。metadata 分别记录正文/账本 fingerprint、claim/anchor 数和分节统计。
- `prepare-summary` 同时报告两个输出目标；同步更新 `/mw-paper` command、paper skill、根 skill、OpenAI metadata、summary/paper-state contracts 和 plugin manifest。
- `README.md`、`scripts/mw_paper_sources.py`、`scripts/mw_runtime.py` 均未修改；P2 遗留的 `atomic_write_bytes` 下沉 runtime 与 arXiv paper-id 版本解析本次未处理。

验证：

- `python -m unittest discover -s tests -v`：100/100 通过，其中原 v2.1 workflow 29/29、P0 runtime 12/12、P1 paper state 18/18、P2 close reading 20/20、P3.5 summary 21/21。
- P3.5 覆盖双文件合法完成、ledger 精确字段、禁用旧标签、B/M/E claim family、locator allowlist、evidence containment、正文三节、双向锚定、章节前缀、孤立锚点、旧/新内嵌账本拒收、双文件 fingerprint 漂移、index tamper、CLI 双目标和缺 ledger 拒收。
- `python -m py_compile`、root/paper skill validator、plugin validator、manifest JSON、`git diff --check`、README 和 P2/runtime 零差异检查通过。
- plugin cachebuster 更新为 `2.2.0-alpha.4+codex.20260718093644`；当前 Codex CLI 仍无 `plugin add` 子命令，`~/.codex/skills/mary-workflow` 与 `~/plugins/mary-workflow` 均通过符号链接直接指向本仓库。

### v2.2 P4 offline Marp template supply

Baseline commit: `3fc715f` - `gitignore 更新`

完成内容：

- 以 `VSPlab/vsp-marp` commit `d3ac970227782445e77009ca53fa8fd526cd2b43` 的 `tutorial-red-shtu` 为基线，将编译后主题就地本地化为 `assets/marp/themes/mary-shanghaitech-red.css`；没有 fork、submodule 或运行时 git clone。
- 按最终评审决定取消 `VENDOR.md`，仅在 CSS 第二行保留 `/* vendored from VSPlab/vsp-marp @ d3ac970, localized 2026-07 */` 工程溯源注释。
- 复制上海科技大学 16:9 背景、校徽和校名资源；主题中的 COS URL 全部替换为仓库内相对路径，CSS HTTP(S)/协议相对 URL 数量为 0。
- 本地化六个 Latin Modern OTF、完整 Noto Sans CJK SC regular/bold WOFF2，以及 KaTeX 0.16.45 的 20 个 WOFF2；中文、代码和数学公式均不依赖在线字体。
- 新增 `assets/marp/marp.config.mjs` 与 `marp-engine.cjs`，注册本地主题、允许本地资源并强制 KaTeX font path 指向 `../fonts/katex/`；禁用会引入远程图片的 emoji 转换。
- 新增四页 `offline-preview.md`，覆盖 `cover_e`、普通背景页、`toc_b` 和 `lastpage`，实测上海科技大学红色模板、校徽/校名、中文 regular/bold、背景及 KaTeX 求和/范数/上下标均正确显示。
- 新增 `scripts/validate_marp_assets.py`、`references/marp-assets-contract.md` 和 P4 单测，机器校验主题 provenance、33 个本地 URL 闭包、20 个 KaTeX 字体、两个完整 Noto 字重、配置/engine 和 smoke deck 必填标记。
- 修复 VS Code 预览未注册本地主题的问题：新增根目录 `.vscode/settings.json`，显式注册 `mary-shanghaitech-red`、允许模板 HTML 并选择 KaTeX；工作区内任意子目录的 Markdown 均使用同一主题。
- 将可维护的相对路径 CSS 保留为 `mary-shanghaitech-red.source.css`，运行时 CSS 由 `scripts/build_marp_theme.py` 确定性编译并内嵌全部资源，消除背景、校徽与字体相对 Markdown 目录解析造成的跨目录失效。
- 根 skill 与 paper skill 只声明 P4 离线供应基座；`slides.md` 生成和 slides completion gate 继续明确阻断，未提前实现 P5。
- 私有仓库自用风险由项目方接受；若未来公开发布 Mary Workflow，须在发布前补做主题、字体、校徽和背景资源的许可/商标审查。
- `README.md`、paper runtime、P0/P2/P3 源码均未修改，忽略的 `vsp-marp/` 源工作树保持 `main...origin/main` 干净状态。

验证：

- `python -m unittest discover -s tests -v`：104/104 通过，其中既有 100 项全量回归保持通过，P4 asset contract 新增 4/4。
- `npm_config_offline=true npx --yes @marp-team/marp-cli@4.3.1` 在 npm 离线模式成功生成四页 HTML/PNG；Marp CLI 4.3.1 搭配 Marp Core 4.4.0。
- Chromium 使用 `--disable-background-networking --host-resolver-rules='MAP * ~NOTFOUND'` 仍成功打开本地 HTML，封面校徽、校名与中文完整；四页 PNG 均为 1280x720 且像素标准差非零。
- 将同一 smoke deck 复制到仓库外 `/tmp/.../arbitrary/deep/paper/slides.md` 后，在 npm 离线模式重新渲染 4 页 PNG；日志无 missing local files，校徽、校名、16:9 背景、完整中文和 KaTeX 公式均正常，证明输出不再依赖 Markdown 所在目录。
- 人工逐页检查通过：修正目录页重复标题和尾页非三列布局后，四页无文字重叠、空白资源或公式缺字；按 2026-07-18 修订口径不要求 PDF 导出。
- `python -m py_compile`、Marp asset validator、root/paper skill validator、plugin validator、manifest JSON、`git diff --check`、无 `VENDOR.md`、README/runtime 零差异和上游工作树零修改检查通过。
- plugin cachebuster 更新为 `2.2.0-alpha.5+codex.20260718125033`；现有 skill/plugin 安装继续通过符号链接直接指向本仓库。

### v2.2 P5 grounded Marp research slides

Baseline commit: `c950395` - `P4 finished`

完成内容：

- 新增 `scripts/mw_paper_slides.py`，实现 `slides-context.json`、summary bundle 复验、claim catalog、可解析 Figure catalog、`slides.md` fingerprint 和 P5 lint；slides 完成不再接受通用占位 fingerprint。
- `prepare-slides` 要求 P3.5 summary 已完成且当前双文件字节仍匹配状态，生成上下文与 `figures/` 目录并启动 slides；`lint-slides` 无状态变更；`complete-slides` 复用同一 lint 后完成状态。
- 修复独立目标项目的 VS Code 主题作用域：`prepare-slides` 现在把 33/33 资源内嵌的自包含 CSS 原子部署到 `<project>/.mary-research/marp/themes/`，并合并 `<project>/.vscode/settings.json` 的 Marp HTML、KaTeX 与主题注册。已有无关设置和主题条目保留，重复执行幂等；lint 同时拒收缺失或漂移的项目主题/注册。
- `slides.md` 强制 `mary-shanghaitech-red`、16:9、`math: katex`、封面/背景/至少两页方法/实验/尾页结构，Method 不得弱于其他主体章节。
- 每个事实页使用隐藏 `<!-- claims: ... -->` 锚定 summary ledger；Background/Method/Experiments 分别限制 B/M/E claim family，未知 claim、可见 `[M01]` 标记和缺少任一 claim family 均拒收。
- 从当前 `source-locators.json` 的可解析 span 提取 Figure 编号、图注与 locator；占位必须显示论文原 Figure 编号、携带匹配 locator 并落在 `limg/mimg/rimg/timg/bimg` 面板。未知 Figure、错 locator、缺编号/图注节点和只提 Figure 不留占位均拒收。
- 本地媒体仅允许 paper workspace 内已存在的相对文件；HTTP(S)、data URI、绝对路径、`..` 越界和缺文件拒收。每页同时限制 900 可见字符、36 可见行、8 个列表项、14 行代码，总页数限制 6-24。
- 强制至少两页使用既有 VSP-Marp 多面板布局，包括 `cols-2-*`、`cols-3`、`rows-2-*` 和 `pin-3`；没有另造布局系统。
- 上科大主题新增 Figure 虚线占位、编号和图注样式，并重新确定性生成 33/33 资源内嵌的自包含 CSS；P4 远程 URL 继续为 0。
- `lint-slides` 与 `complete-slides` 支持可选 `--smoke-compile`：优先本地 `marp`，否则使用 npm 离线缓存的 Marp CLI 4.3.1；只生成并删除临时 HTML，不把 HTML/PDF/PPTX 纳入交付。
- 新增 `references/slides-contract.md`，同步 `/mw-paper` command、paper/root skill、paper state/Marp contract、OpenAI metadata 与 plugin manifest；P6 `quiz-log.md` 继续明确阻断。
- plugin 预发布基础版本保持 `2.2.0-alpha.6`，并通过 helper 刷新单一 cachebuster 为 `2.2.0-alpha.6+codex.20260718151254`。
- `README.md`、P0 runtime、P2 source acquisition、P3.5 summary runtime 均未修改；忽略的 `vsp-marp/` 来源仓库未修改。

验证：

- `python -m unittest discover -s tests -v`：119/119 通过，其中既有 104 项回归保持通过，P5 共 15 项契约测试。
- P5 覆盖合法完成、prepare/lint/complete CLI、context/summary/fingerprint 漂移、frontmatter、结构顺序、方法页下限、claim allowlist/family/隐藏语义、Figure id/locator/节点/缺位、布局下限、远程/缺失媒体和单页超量拒收。
- 跨 workspace 覆盖项目主题落盘、VS Code JSONC 设置合并、既有主题保留、单次注册、重复准备幂等、非法设置无部分主题写入，以及主题注册漂移后拒收/重备修复。
- 完整 fixture 流水线从 read → summary → slides 生成 7 页 deck；`lint-slides --smoke-compile` 在 npm 离线模式通过，报告 pages=7、layouts=4、figures=1，状态目录没有残留导出物。
- 使用同一 P5 `slides.md` 离线渲染 7 张 1280x720 PNG 并逐页检查：上科大封面/背景/Logo、KaTeX、双栏 Figure 占位、三栏、上下栏和尾页均正常，无空白页、资源缺失或文字重叠。
- 对真实 `test/v2.2/.mary-research/papers/arxiv-2308.04079/slides.md` 复验通过：从 `test/v2.2` 独立工作目录仅注册项目内 CSS，离线生成 13/13 张 1280x720 PNG；封面、中文、校徽、红色母版、Figure 1/5 占位和尾页正常，证明不再依赖 Mary 仓库根 `.vscode` 或 Marp CLI config。

### v2.2 P6 append-only expert Q&A

Baseline commit: `f2d9e9e` - `项目目录无法正常渲染问题解决`

完成内容：

- 新增 `scripts/mw_paper_quiz.py` 与 `references/quiz-contract.md`，将 P2 `uncertainties` 编为 Uxx 出题锚点，将 P3.5 Method direct claims 保留为 Mxx 锚点；`quiz-context.json` 固定 read/summary/source-index 字节 lineage 和当前 attempt。
- 新增 `prepare-quiz`、`next-quiz-question`、`append-quiz-session`、`lint-quiz`、`complete-quiz` 五个命令；出题器先补 Uxx、再补 Mxx，之后按最少使用次数交替，quiz 继续只依赖 read + summary、不依赖 slides。
- session 只接受 `supported`、`partially-supported`、`unsupported`、`uncertain` 四值，不提供二元判错；每条记录强制 question/anchors/answer/judgment/rationale/citations 六字段和至少一条原文引用。
- citation locator 必须属于所选 U/M 锚点，evidence 必须是对应 `source.md` span 内 8-500 字符的逐字摘录；未知锚点、跨锚点 locator、虚构摘录和重复引用拒收。
- `quiz-log.md` 使用真实 `O_APPEND + fsync` 追加规范 session；用户直接阅读 Question/Answer/Judgment/Rationale/Anchors/Source citations，完整机器记录折叠在 `<details>` 中并与可读视图一起确定性重建。每条 session 哈希全部不可变字段并串联前一条，`quiz-head.json` 固定 session count、链头和整文件 fingerprint；改答案、改判、删史、插入自由文本、断链、head 漂移和符号链接均拒收。
- quiz reset 不删除旧 session；新 `quiz_attempt` 产生不同 context fingerprint，旧史继续可审计但不能替当前 attempt 满足 U/M 覆盖。更正只能新增 session，不能覆盖旧判定。
- `complete_stage quiz` 接入专用 gate，要求 artifact=`quiz-log.md`、当前 attempt 至少一个 session且同时覆盖 U/M、四值/引用/链/head 全通过、声明 fingerprint 与日志字节一致；低层 action 不能绕过。
- 同步 root/paper skill、`/mw-paper` command、paper state contract、OpenAI metadata 和 plugin manifest；交互 prompt 明确一次只问一题、等待用户回答后再判定，禁止替用户编答案。
- plugin 预发布基础版本更新为 `2.2.0-alpha.7`，并通过 helper 写入单一 cachebuster `2.2.0-alpha.7+codex.20260719054059`。
- `README.md`、P0 runtime、P2/P3/P5 专用 runtime 和忽略的 `vsp-marp/` 均未修改。

验证：

- `python -m unittest discover -s tests -v`：133/133 通过；P5 验收时的 119 项全部保持通过，P6 新增 14/14。
- P6 覆盖 context/catalog、U→M 出题、四种 judgment、CLI 全链路、非法 judgment 无落盘、空/未知锚点、跨锚点 locator、虚构 evidence、双族完成门、context 漂移、输出 fingerprint、改判、删史、symlink 和 reset 跨 attempt 保史。
- 真实 `arxiv-2308.04079` 的已完成 P2/P3 工件只读验收：解析出 4 条 Uxx uncertainty 与 13 条 Mxx Method claim，在临时目录追加 U01/M01 两条 session，得到 `supported=1`、`uncertain=1`，完整 lint 通过；原测试项目 state/log 未改动。

### v2.2 P6.1 paper-understanding quiz correction

Baseline commit: `147b8bc` - `P6 finished`

完成内容：

- 根据实弹反馈修正出题边界：双栏顺序、PDF 解析、公式抽取、缺失图像像素和表格对齐等解析质量问题不再进入用户题库，只保留为内部 `source_quality_notes` 审计信息。
- `quiz_context_schema` 升级为 2；P2 uncertainty 按 `quality_dimensions` 分流，无质量维度的科学内容不确定性进入 `scientific_uncertainty_catalog`，带质量维度的条目转为不可出题的 SQxx note。
- 出题顺序改为先问一个 P3.5 Mxx Method claim，content catalog 非空时再覆盖一个科学 Uxx，随后返回剩余 Method；完成门始终要求 Method，并且只在 content catalog 非空时动态要求 Uxx，纯解析质量论文降级为 method-only。
- 方法题干按 claim 语言生成，中文 claim 直接生成中文论文理解题，要求用户解释论断的含义、对应的方法环节以及它如何帮助把握论文核心贡献。
- `quiz-log.md` 明确为唯一交付归档：每道实际问答的 Question、用户 Answer、四值 Judgment、Rationale、Anchors 和原文 Citations 均追加在同一个 Markdown；`quiz-context.json` 与 `quiz-head.json` 仅为机器校验 sidecar。
- append-only、哈希链、四值判定、exact source excerpt、旧 session 禁止改判/删史等 P6 机器骨架保持不变。
- plugin 基础版本保持 `2.2.0-alpha.7`，cachebuster 刷新为 `2.2.0-alpha.7+codex.20260719062900`。
- `README.md`、P0/P2/P3/P5 runtime 和忽略的 `vsp-marp/` 均未修改。

验证：

- `python -m unittest discover -s tests -v`：136/136 通过；P6 问答测试为 17/17，覆盖 content U 非空时缺 U 拒收与 parse-only 时 method-only 放行两个方向。
- 真实 `arxiv-2308.04079` 重建 context 后得到 0 条 scientific uncertainty、4 条不可出题 SQ quality note、13 条 Method claim；第 1 题锚定 M01，题干为中文方法理解题，不再询问双栏 PDF 可靠性。
- `python -m py_compile`、root/paper skill validator、plugin validator 和 `git diff --check` 通过。
