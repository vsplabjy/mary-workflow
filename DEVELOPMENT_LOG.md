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

- `python -m unittest discover -s tests -v`：21/21 通过。
- `python -m py_compile scripts/mary_workflow.py scripts/mw_codex.py` 通过。
- `.codex-plugin/plugin.json` JSON 校验与 `git diff --check` 通过。
- 覆盖 nonce 明文不落盘、grant 轮换/重放拒绝、原子启动、stop/resume、debug/review lease 保持、FINISHED/replan/cycle 释放，以及早期/缺失 version 拒载。
- 剩余信任边界：仓库运行时证明的是“调用者持有 `/mw-run` 渲染 grant”；若要密码学证明由人类而非具备直接进程权限的 agent 发起，必须由 Codex 宿主 slash dispatcher 作为可信签发方。
