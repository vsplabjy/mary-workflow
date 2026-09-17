# Mary Workflow

Mary Workflow 3.0 是一套与模型无关的 agent 工作流，适用于代码开发、研究实验、课程学习、论文阅读和文档操作。主线负责理解需求、派单、核对证据和验收；子代理负责有明确边界的实现、调研和独立检查；Python 运行时验证阶段、计划身份、改动范围和交付证据。

工作流不指定模型、供应商、推理档位、上下文大小或服务等级。主线和子代理继承用户的宿主设置，不根据模型名称选择流程，也不修改全局配置或 shell 启动文件。

## 核心行为

- **上下文复用**：保留已有探索成果，阶段边界核对状态与变化；项目说明和机器清单保存在项目内，不要求声明丢弃记忆。
- **分级理解**：小项目直接阅读，中项目形成模块摘要，大项目可由 explorer 并行分片。运行时核算清单覆盖，无需为每个文件填写重复的用途、导出和消费者字段。
- **必要访谈**：只问影响范围、验收或重要选择的问题，信息充分时不额外提问。里程碑按可独立验收边界划分，不限制文件数和里程碑数。
- **明确执行起点**：计划冻结后，用户明确发出 `/mw-run` 即开始。记录计划哈希、确认来源和运行身份，不搬运一次性口令，也不重复请求已给出的授权。
- **委派与独立审查**：worker 提交待审结果，主线核对任务身份、真实改动和实际验证。实现者不能自行接受交付；独立 verifier 审查之后，主线完成状态转换。
- **可恢复执行**：停止时中断或通知 worker，保留现场；恢复时核对残留改动和计划版本，拒绝旧任务的迟到或重复结果。
- **聚焦修复**：DEBUGGING 只诊断并排入修复任务，回到 EXECUTING 才修改产品文件；保留失败、执行、审查和重试证据。
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

项目根目录的 `.maryignore` 与 `.mary-workflow/config.yaml` 中 `init.ignore` 控制扫描排除项，例如：

```gitignore
data/**
*.log
```

排除规则会影响所声称的覆盖范围；覆盖记录不能证明语义理解。缺少数据、GPU 或工具时，如实保留未运行的验证，不能以 CPU 或格式检查冒充真实实验。

## 命令

| 命令 | 用途 |
| --- | --- |
| `/mw-init` | 初始化、理解或刷新当前项目；保留已有固定版本 |
| `/mw-plan [需求]` | 必要澄清与可验收计划，规划阶段不执行产品工作 |
| `/mw-run` | 开始冻结计划或恢复暂停的运行 |
| `/mw-status` | 查看阶段、worker、证据与阻塞，不修改状态 |
| `/mw-stop` | 协调暂停、保留部分产物与恢复记录 |
| `/mw-debug` | 诊断当前错误并排入聚焦修复 |
| `/mw-cycle` | 刷新项目认知并归档当前周期 |
| `/mw-learn` | Lecture 学习、slides、原始录音转写与课堂增量融合 |
| `/mw-exam`、`/mw-review` | 章节/考试复习、错题本、自测与模拟卷 |
| `/slide-learning` | 整理 Slide → Lecture 基础笔记 |
| `/mw-paper` | 论文阅读、总结、汇报与基于来源的问答 |
| `/mw-notion [请求]` | 读取或修改 Notion，检查 schema 并回读验证 |

`/mw-init --reset` 仅用于用户明确要求删除并重建工作流数据的情况，不能用来代替升级。旧的模型设置命令已退出入口；`scripts/mw_model.py` 只保留不读写配置的兼容提示。既有用户 shell 配置不会被本次升级擅自删除或修改。

## 委派、验证和并行

每个 worker 任务包含身份与 attempt、计划版本、目标、交付物、允许写入范围、验收、改动基线和必要上下文。worker 返回 `ready_for_review`、真实文件变化、实际验证与证据路径，以及越界、阻塞和不确定性。执行与审查证据分别保存；旧证据不能在产物变化后继续作为通过依据。

主线是控制状态的唯一写入者，使用 `mary_workflow.py apply-action`。它保留用户交互、最终判定、Git 写操作和已授权外部修改；worker 不直接修改正式状态、日志或报告。合法测试修订可以纳入范围，但删除断言或弱化验收以换取通过不可接受。

第一版保持里程碑串行，支持当前里程碑内部的独立任务并行，以及 init 分片阅读。文件不相交还不够：共享接口、生成文件、数据库、端口和构建输出也可能冲突。紧耦合工作保留在同一个 worker 或串行处理，不为小任务制造派单仪式。

宿主缺少子代理时，可以按契约运行明确标注的单 agent 兼容模式，不能声称已经完成独立 agent 审查。TodoList 是持久记录的进度视图；结构化提问、memory、goal 和 hooks 都是可选能力。辅助 hooks 应短时、幂等、失败不阻塞；没有它们，核心流程也必须工作。

具体协议见 [子代理契约](references/subagent-contract.md)、[状态契约](references/state-contract.md)、[记忆契约](references/memory-contract.md) 和 [宿主能力契约](references/host-contract.md)。

## 多场景边界

课程学习和考试复习使用 milestone/cycle 生命周期，交付物放在项目已有课程或笔记目录；原始资料和录音转写保持完整。内容验收包含来源、范围、公式、图像和学习结果，不能仅检查文件存在。

论文继续使用独立的 `paper_state_schema: 1` 和 `.mary-research/papers/<paper-id>/`，不要求 milestone init/run。来源定位、解析质量、下游失效、slide 编译与视觉检查、quiz 的追加哈希链保持原契约。原文与生成 JSON sidecar 放在 `artifacts/`；`slides.tex` 是可编辑汇报源。paper workspace 中 `make slide` 生成 `build/slides.pdf`，`make hypo-template` 保留独立模板对照。详见 [paper 技能](skills/paper/SKILL.md)。

Notion 操作依赖已授权的实际连接，先读取目标与 schema、最小范围修改、再回读确认。worker 可准备内容和调研，主线执行已授权的外部写入。没有工具时报告具体依赖，不能声称已同步。详见 [Notion 技能](skills/notion/SKILL.md)。

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

同一状态版本的运行时/提示 bundle 更新使用 `upgrade` 预览和 `upgrade --apply`。迁移保留历史并创建备份；不要为了升级 reset。使用已授权任务实施升级时，无需再次请求相同授权。

维护者修改源后运行：

```bash
python scripts/mw_surfaces.py
python scripts/mw_surfaces.py --check
python -m unittest discover -s tests
```

`--check` 只报告生成物漂移，不写入文件。核心运行时测试验证阶段和交付边界；真实宿主、远端连接和真实模型表现需要对应环境实测，不能由本地合成测试替代。
