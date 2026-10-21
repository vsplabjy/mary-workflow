# Mary Workflow

Mary Workflow 3.0 是一套与模型无关的 agent 工作流，适用于代码开发、研究实验、课程学习、论文阅读和文档操作。按任务选择直接实现、快速实验或正式里程碑。主线复用上下文，必要时委派独立工作；正式验收运行时核对计划、范围和证据。

工作流不指定模型、供应商、推理档位、上下文大小或服务等级。主线和子代理继承用户的宿主设置，不根据模型名称选择流程，也不修改全局配置或 shell 启动文件。

## 快速实验与直接修改

方法已确定、要求“立即跑实验”时，使用 `/mw-experiment`；局部修复、文档或配置修改使用 `/mw-quick`。这两个入口无需全项目 init、brief 覆盖或 SDD，也不要求先派实现者和审查者。已有正式任务的停止、范围和验收绑定继续有效，不能借快速入口绕过。

```text
/mw-experiment 按刚才确定的配置立即运行，使用已分配的 GPU，预算一小时
/mw-experiment status <run-id>
/mw-experiment stop <run-id>
/mw-experiment compare <run-a> <run-b>
/mw-quick 修复配置读取错误，只运行相关检查
```

本地 Linux 脚本可直接运行，`--` 后为字面 argv：

```bash
python /path/to/mary-workflow/scripts/mw_experiment.py run \
  --config configs/train.yaml --resource GPU-actual-uuid --timeout 3600 \
  -- python train.py --config configs/train.yaml
```

启动不扫描仓库、不计算数据集或 checkpoint 哈希、不运行全项目测试。保存命令、小配置原始副本、Git HEAD 引用、日志、资源声明和退出状态。后台 supervisor 负责进程；会话结束不代表实验完成。`--resource` 只协调同用户同主机的 Mary 运行，不分配 GPU 或发现外部作业；CUDA 设备和训练输出路径仍由实际命令指定。输出目录必须是新目录，runner 提供 `MARY_OUTPUT_DIR` 环境变量。

`compare` 按需读取 `<output-dir>/metrics.json` 的有限数值，或启动时 `--metrics-file` 指定的位置。进程退出码为 0 不代表结果有效或科学验收。默认来源记录为 `partial`、审阅为 `unreviewed`；未追踪脏工作区和全部数据依赖，不能承诺精确复现。需要时使用 `audit <run-id> --artifact <file>` 对已退出运行的指定产物计算哈希，它只证明审计时的文件内容。

旧项目保持固定版本；可以显式调用安装位置的实验脚本启动独立新实验。新建或显式升级的 bundle 携带实验能力，不静默迁移活跃任务。详见 [实验技能](skills/experiment/SKILL.md)、[运行合同与设计来源](references/experiment-contract.md)。

## HTML 可视化汇报

一轮实验结束（包括失败、停止）、较大任务或独立里程碑完成、较大任务失败/被外部资源阻塞/修复预算耗尽/停止交接，或者用户明确要求汇报时，主线必须生成静态 HTML 汇报，并在交付回复中提供具体路径。运行中的汇报标注快照时间和未完成项；普通小修改、日常进度与只读查询不逐次生成报告；只读讨论和用户明确禁止写文件的情形除外。失败收尾前先停止派发并适当停止自有进程、等写入稳定；报告不等于验收，也不为了填报告重跑实验。文件无法生成时在聊天里如实交接同样的内容。

```text
.mary-workflow/reports/
  index.html                           # 汇报目录，最新优先
  <YYYYMMDDTHHMMSSZ>-<task-or-run-id>/
    index.html                         # 本次汇报，浏览器直接打开
    assets/                            # 图片、缩略图、短视频等展示资源
```

第一屏先给结论和真实效果，再按需展示前后对比、关键指标、验证结果、证据与复现命令。验证标为「通过、失败、运行中、未运行」，区分程序退出、工程验证、视觉质量和科学验收。失败/停止/预算耗尽的汇报首屏给出最早已证实原因（或 `UNKNOWN`）、已完成与未完成、实际改动路径、检查状态、剩余修复预算和下一步。没有基线或视觉产物就说明，不伪造结果，也不为了填报告重新跑实验。

HTML 默认中文，离线打开，不需要启动服务、安装前端依赖或访问 CDN；核心内容直接写入页面，展示资源用相对路径。使用缩略图与精选结果，不把数据集、checkpoint、完整日志复制进报告。交付前实际打开浏览器检查首屏和本地链接；工具不可用时明确验证限制。

初始化时 `/.mary-workflow/` 已整体覆盖 HTML、assets、实验记录与输出、配置、哈希、runtime 和归档；其他 workflow 自有项目目录同样自动忽略，详见下方初始化说明。目录按需创建，但忽略规则在初始化时先安装。历史汇报包保留，cycle 不删除总入口或含 regular `index.html` 的非 cycle 汇报目录；`reports/C0/` 等名称保留给正式收据，仍按周期归档。新建/显式升级的 bundle 携带规范；不静默升级旧项目。完整要求见 [汇报契约](references/report-contract.md)。

## 新对话接手与模块说明

使用 `/mw-context`，或让 Mary 在新对话开始时先读取项目内的记录：

```text
.mary-workflow/knowledge/
  index.json          # 维护源：模块归属、依赖、版本和过期标记
  overview.md         # 项目用途、架构、能力边界、模块索引
  modules/<id>.md     # 职责、入口、输入输出、约束、使用/验证方法、已知缺口
  handoff.md          # 当前进度、决策原因、结果位置、阻塞、停止状态和下一步
```

默认先读总览、相关模块介绍和接手说明，修改或解决具体疑点时再读对应代码。`python /path/to/mary-workflow/scripts/mw_knowledge.py read` 直接从维护源输出总览和接手说明，`read --module <id>` 按需增加模块详情；读取不要求 init、不写状态、不恢复实验。

每次修改按明确文件路径更新对应介绍，来不及就保留 `stale`；所属模块及依赖它的模块会被标记，新文件尚未归属时显示 `unmapped_files`。正式 worker 提交复用已有变更列表自动标记；直接修改由 agent 在编辑前登记路径、完成后补记额外变更。新建或更新介绍使用带版本的 `update`，防止旧回复清除新变更标记。已有 brief 可以导入，但简短摘要先标为 `incomplete`，不冒充完整说明。

这套记录不遍历源码、不新增哈希校验、不要求重写未改模块，也不阻塞已经确定的实验。它依赖 agent 登记直接修改，不能自动发现外部未报告的编辑；本地记录默认忽略，不会自动传到其他机器。旧项目不自动升级。[维护命令与格式](references/knowledge-contract.md)。

## 正式流程的核心行为

以下阶段与冻结规则适用于正式 milestone 流程；快速实验和直接修改采用上面的独立入口。

- **上下文复用**：保留已有探索成果，阶段边界核对状态与变化；项目说明和机器清单保存在项目内，不要求声明丢弃记忆。
- **分级理解**：小项目直接阅读，中项目形成模块摘要，大项目可由 explorer 并行分片。运行时核算清单覆盖，无需为每个文件填写重复的用途、导出和消费者字段。
- **必要访谈**：只问影响范围、验收或重要选择的问题，信息充分时不额外提问。里程碑按可独立验收边界划分，不限制文件数和里程碑数。
- **明确执行起点**：计划冻结后，用户明确发出 `/mw-run` 或“通过，直接修改”等执行指令即开始。记录计划哈希、确认来源和运行身份，不搬运一次性口令，也不重复请求已给出的授权。
- **委派与审查**：worker 提交待审结果，主线核对任务身份、真实改动和实际验证。delegated 模式由独立 verifier 审查后主线验收；小任务或紧耦合任务即使有 workers 也可选择 single-agent，分开实现和审查并明确记录 `same_agent`、`independent_review: false`，不冒充独立审查，也不在审查阶段临时切换模式绕过身份检查。
- **可恢复执行**：停止时中断或通知 worker，保留现场；恢复时核对残留改动和计划版本，拒绝旧任务的迟到或重复结果。
- **聚焦修复**：DEBUGGING 只诊断并排入修复任务，回到 EXECUTING 才修改产品文件；保留失败、执行、审查和重试证据。
- **修复预算**：每个里程碑可用 `max_repair_rounds` 限制自动修复轮数，默认 `2`，`0` 表示失败后不自动修复。首次实现与验证不计；失败后排队修复、审查退回重做、worker/验证失败后的重新派单各计一轮。换任务 ID、换 agent、`retry_of`、嵌套修复、停止恢复或重新规划都不会重置计数；verifier/explorer 与初始并行分片不消耗预算。达到上限后运行时拒绝继续自动修复：保留证据和当前合法 phase，不伪 FINISHED，不借 `/mw-quick` 或 `/mw-experiment` 改名绕过，也不因此获得 GPU/训练/付费授权，并以失败 HTML 汇报收尾。继续修复需要用户记录在案的明确授权。详见 [修复预算契约](references/repair-contract.md)。新建或显式升级的 bundle 携带该能力；旧项目保持固定版本，需要时显式 `upgrade`。
- **增量归档**：cycle 检测文件变化，更新受影响认知并列出仍有效条目，合并成完整项目说明后归档。

文件哈希和动作白名单用于发现正常流程中的误操作，不能阻止拥有任意 shell 权限的 agent 绕开脚本。所谓只读 worker 也需要宿主实际权限支持；提示词本身不是文件系统隔离。

## 安装与运行

需要 Python 3.10 或更高版本、Git，以及能够读取技能和执行本地工具的 agent 宿主。核心运行时不依赖额外 Python 包。以下是 Codex 的安装示例；其他宿主可以使用相同脚本和契约，按实际工具能力适配。

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/reversevertin1999/mary-workflow.git \
  ~/.codex/skills/mary-workflow
```

在目标项目根目录开启宿主会话，依次使用：

```text
/mw-init
/mw-plan 为后台管理系统增加角色权限管理，并补充相应测试
/mw-run
```

`/mw-init` 建立项目说明；`/mw-plan` 保存真实需求、必要澄清、交付路径和验收条件并冻结计划；`/mw-run` 确认并执行这个计划。讨论中的“可以/对”必须按其回答的问题理解，不能把对方案的认可偷换成开始执行的授权。用户已有明确执行授权时，不再机械追问。

初始化及独立论文创建会自动补齐项目根目录 `.gitignore`：默认忽略 `/.mary-workflow/`、`/.mary-workflow-worker/`、`/.mary-research/`、`/.vspi/`。初始化在生成项目记录前安装这些规则，覆盖 HTML 汇报及其 assets、实验记录与本地输出、哈希清单、生成配置、固定运行时、归档和 worker 临时目录；无需为每个子目录重复加规则。其他路径的流程记录应在生成前添加精确忽略项。已有规则和 Git 索引保持原样，因此已跟踪文件仍会被跟踪。不得使用宽泛的 `reports/`、`outputs/` 规则误忽略项目源码、正式交付物或手写 OpenSpec 规范。

项目根目录的 `.maryignore` 与 `.mary-workflow/config.yaml` 中 `init.ignore` 控制扫描排除项，例如：

```gitignore
data/**
*.log
```

排除规则会影响所声称的覆盖范围；覆盖记录不能证明语义理解。缺少数据、GPU 或工具时，如实保留未运行的验证，不能以 CPU 或格式检查冒充真实实验。

## 命令

| 命令 | 用途 |
| --- | --- |
| `/mw-experiment [请求]` | 快速启动、状态、停止、比较和显式审计实验 |
| `/mw-quick [请求]` | 单 agent 直接完成局部修改与相关检查 |
| `/mw-init` | 初始化、理解或刷新当前项目；保留已有固定版本 |
| `/mw-plan [需求]` | 必要澄清与可验收计划，规划阶段不执行产品工作 |
| `/mw-run` | 开始冻结计划或恢复暂停的运行 |
| `/mw-status` | 查看阶段、worker、证据与阻塞，不修改状态 |
| `/mw-stop` | 协调暂停、保留部分产物与恢复记录 |
| `/mw-debug` | 诊断当前错误并排入聚焦修复；预算耗尽时停止自动修复并如实交接 |
| `/mw-cycle` | 刷新项目认知并归档当前周期 |
| `/mw-learn` | Lecture 学习、slides、原始录音转写与课堂增量融合 |
| `/mw-exam`、`/mw-review` | 章节/考试复习、错题本、自测与模拟卷 |
| `/slide-learning` | 整理 Slide → Lecture 基础笔记 |
| `/mw-paper` | 论文阅读、总结、汇报与基于来源的问答 |
| `/mw-humanize [文本或文件路径]` | 使用 Humanizer-zh 润色中文，保留事实、语气和引用 |
| `/mw-notion [请求]` | 读取或修改 Notion，检查 schema 并回读验证 |

`/mw-init --reset` 仅用于用户明确要求删除并重建工作流数据的情况，不能用来代替升级。旧的模型设置命令已退出入口；`scripts/mw_model.py` 只保留不读写配置的兼容提示。既有用户 shell 配置不会被本次升级擅自删除或修改。

## 委派、验证和并行

每个 worker 任务包含身份与 attempt、计划版本、目标、交付物、允许写入范围、验收、改动基线和必要上下文。worker 返回 `ready_for_review`、真实文件变化、实际验证与证据路径，以及越界、阻塞和不确定性。执行与审查证据分别保存；旧证据不能在产物变化后继续作为通过依据。

主线是控制状态的唯一写入者，使用 `mary_workflow.py apply-action`。它保留用户交互、最终判定、Git 写操作和已授权外部修改；worker 不直接修改正式状态、日志或报告。合法测试修订可以纳入范围，但删除断言或弱化验收以换取通过不可接受。

第一版保持里程碑串行，支持当前里程碑内部的独立任务并行，以及 init 分片阅读。文件不相交还不够：共享接口、生成文件、数据库、端口和构建输出也可能冲突。紧耦合工作保留在同一个 worker 或串行处理，不为小任务制造派单仪式。

小任务、紧耦合工作或缺少子代理时，可以按契约选择单 agent 模式，不能声称已经完成独立 agent 审查。TodoList 是持久记录的进度视图；结构化提问、memory、goal 和 hooks 都是可选能力。辅助 hooks 应短时、幂等、失败不阻塞；没有它们，核心流程也必须工作。

具体协议见 [子代理契约](references/subagent-contract.md)、[状态契约](references/state-contract.md)、[记忆契约](references/memory-contract.md) 和 [宿主能力契约](references/host-contract.md)。

## 多场景边界

课程笔记、slides 整理和章节复习默认直接执行，复用已有资料与目录，无需先 init、冻结计划或 cycle。缺少可选录音或考试日期时，先交付现有来源支持的内容并标注缺口。保留原始资料和内容检查；不为整理一讲笔记重建整个 Course Hub，也不为章节复习自动追加两套模拟卷。

显式分阶段课程项目或已绑定的正式任务继续使用 milestone。`mw_codex.py mw-learn --formal`（考试使用 `mw-exam`）选择正式入口。默认课程 CLI 不读取项目状态或验证 runtime bundle，且不创建控制文件。

论文继续使用独立的 `paper_state_schema: 1` 和 `.mary-research/papers/<paper-id>/`，不要求 milestone init/run。来源定位、解析质量、下游失效、slide 编译与视觉检查、quiz 的追加哈希链保持原契约。原文与生成 JSON sidecar 放在 `artifacts/`；`slides.tex` 是可编辑汇报源。paper workspace 中 `make slide` 生成 `build/slides.pdf`，`make hypo-template` 保留独立模板对照。详见 [paper 技能](skills/paper/SKILL.md)。

Notion 操作依赖已授权的实际连接，先读取目标与 schema、最小范围修改、再回读确认。worker 可准备内容和调研，主线执行已授权的外部写入。没有工具时报告具体依赖，不能声称已同步。详见 [Notion 技能](skills/notion/SKILL.md)。

## 中文润色：Humanizer-zh

已集成 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)，保留上游规则快照与 MIT 许可。可直接调用：

```text
/mw-humanize 请润色 article.md 的正文，保留技术评论的语气
/mw-humanize 只审阅这段文字，给建议，不修改文件：……
```

中文论文总结、课程笔记、报告和 Notion 正文在验证交付前按需调用。润色保留事实、确定程度、作者声音、来源标记和文件结构，不改原文引语、证据记录、公式或代码。它是编辑指导，不判断作者身份，也不保证通过 AI 检测器。详见 [集成入口](skills/humanizer-zh/SKILL.md)。新建或显式升级的项目 bundle 携带此技能；已有项目不会静默升级。

## 共享规则与正式证据范围

[task-policy.md](references/task-policy.md) 是过程选择、授权、委派和共享交付规则的维护源。子技能保留领域内容，阶段源只描述正式状态操作，命令和提示继续自动生成。重复的课程阶段表和各技能通用协调段已改为引用。

正式任务已知验收命令的依赖时，在冻结 milestone 或 `mary-task` 中声明：

```json
{"validation_inputs": ["src/export.py", "tests/test_export.py", "fixtures/input.csv"]}
```

必须包含实际读取的代码、测试、配置和 fixture。字段绑定到计划，不能在运行后临时缩小。命令前后只读取声明的交付/依赖范围，收据按 `validation_inputs` 判断是否失效；授权范围内、未被该命令读取的笔记修改不再要求重跑测试。交付及接受时仍检查全局越界与 Git index，正式 SDD 归档仍核对完整已接受快照。依赖不明或未声明该字段时保留旧的全项目证据语义。详情集中在 [worker 合同](references/subagent-contract.md#validation-inputs-and-ownership-audits)。

## 指令来源与升级

维护源只有技能和共享契约：

| 位置 | 角色 |
| --- | --- |
| `skills/*/SKILL.md` | 命令对应的维护入口 |
| `references/phases/*.md` | 阶段指令的维护源 |
| `commands/*.md` | 从技能生成的兼容路由，不手工维护行为 |
| `.mary-workflow/prompts/*.md` | 从阶段源生成的版本副本 |
| 项目 `.mary-workflow/runtime/` | 项目固定的运行时及其兼容契约 |

更新技能代码不会在普通 init 中静默替换项目的运行时和提示。旧项目保持完整版本的一致行为；不能把旧提示词与新状态逻辑混用。

从 2.1 升级时，先在目标项目根目录预览，再在已有升级授权范围内应用：

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py migrate
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py migrate --apply
```

同一状态版本的运行时/提示 bundle 更新使用 `upgrade` 预览和 `upgrade --apply`。迁移保留历史并创建备份；不要为了升级 reset。使用已授权任务实施升级时，无需再次请求相同授权。修复预算（`max_repair_rounds`，见 [修复预算契约](references/repair-contract.md)）属于这类新能力：新安装和显式升级携带；已固定的旧项目不会在普通 init 中静默获得或被改动。

正式上下文默认只显示当前阶段所需部分；`mw_codex.py <alias> --full-context` 可显式展开完整历史。

维护者修改源后运行：

```bash
python scripts/mw_surfaces.py
python scripts/mw_surfaces.py --check
python -m unittest discover -s tests
```

`--check` 只报告生成物漂移，不写入文件。核心运行时测试验证阶段和交付边界；真实宿主、远端连接和真实模型表现需要对应环境实测，不能由本地合成测试替代。

## SDD：规格、变更与执行

跨模块行为变更、长期规格或显式正式验收使用 [SDD 契约](references/sdd-contract.md)。已接受的行为保存在 `openspec/specs/<capability>/spec.md`；当前变更位于 `openspec/changes/<change-id>/`，包含 `proposal.md`、增量规格、按需要编写的 `design.md` 和 `tasks.md`。规格描述可观察行为，任务描述实现与验证。既有未绑定计划继续兼容；论文与 Notion 保持独立流程。

`tasks.md` 是唯一人工维护的任务定义。每个编号勾选项后附 `mary-task` JSON，声明交付路径、验收命令及场景到验收编号的映射。运行时从它生成 milestone；只有验收通过才回写勾选，不能靠手工勾选跳过验证。

```bash
python scripts/mary_workflow.py sdd-check add-export
```

此命令只读检查变更并输出里程碑与覆盖信息。主线将这些里程碑和真实澄清写入 `update_interview`，再执行 `bind_change` 和 `update_state` 冻结。计划身份绑定规格、设计、任务和已接受规格基线；改动后走合法重新规划路径。审查为每个场景记录具体证据与结论，覆盖完整不等于语义正确。

完成并验收后的 `cycle` 合并 delta 并归档变更；遇到基线冲突停止覆盖，归档中断通过日志恢复。停止的未完成周期只归档执行证据，保留尚未合并的变更。纯文档/重构可通过 `.openspec.yaml` 的 `skip_specs: true` 与 `skip_reason` 明确解释无行为变化；不要为了格式发明需求。

设计参考 [OpenSpec 概念](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md) 和 [默认 spec-driven schema](https://github.com/Fission-AI/OpenSpec/blob/main/schemas/spec-driven/schema.yaml)。兼容边界是本地文件布局和受支持的 Requirement/Scenario 增量格式，`mary-task` 和证据绑定是 Mary 扩展；不宣称完整 OpenSpec CLI 兼容，不要求 Node/OpenSpec CLI，也不模拟 stores、自定义 schema 或并发 change 执行。

## 效率基准

用 `python scripts/benchmark_experiments.py --repeats 5` 在临时目录运行 CPU 假实验，报告启动（含握手）、首次进度、状态读取和旧快照组件的独立耗时。可用 `--output .mary-workflow/analysis/efficiency/benchmark.json` 保存本地结果。旧快照耗时不是旧 agent 全流程耗时；少量暖缓存样本不证明总体 p95 或 GPU 训练速度。实验启动测试验证不调用仓库快照或内容哈希。
