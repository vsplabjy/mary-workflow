# Mary Workflow

Mary Workflow 3.0 是一套与模型无关的 agent 工作流，用于代码开发、研究实验、课程学习和论文阅读。它把项目上下文、执行记录与验收证据保存在项目内，方便新会话接手；按任务选择直接修改、快速实验或正式里程碑，不要求每件小事都走完整流程。

**工作流管理任务，不管理模型。** 主线与子代理继承宿主设置，不修改模型、供应商、推理档位、全局配置或 shell 启动文件。程序退出、测试通过、视觉质量和科学验收分别报告。

[安装与运行](#安装与运行) · [选择入口](#选择入口) · [常见操作](#常见操作) · [命令速查](#命令速查) · [维护与升级](#维护与升级) · [详细契约](#详细契约)

## 安装与运行

需要 **Python 3.10+、Git**，以及能读取技能文件、执行本地工具的 agent 宿主。核心运行时只使用 Python 标准库；后台实验 runner 另需 Linux `/proc`。论文编译、浏览器核验和 Notion 操作需要各自的实际工具，不包含在核心依赖中。

以 Codex 的技能目录为例：

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/vsplabjy/mary-workflow.git \
  ~/.codex/skills/mary-workflow
```

在**目标项目根目录**打开宿主会话。宿主加载技能后，可以使用下方的 `/mw-*` 入口；斜杠命令的识别取决于宿主集成，克隆仓库不等于为所有宿主注册命令。

OpenCode 或其他未注册这些入口的宿主，也可以通过普通请求明确加载技能：

```text
先读取 /实际安装路径/mary-workflow/SKILL.md，按其中的路由处理当前项目。
这次只修复配置读取错误，使用 quick 入口并运行相关检查。
```

后续 shell 示例用 `MARY_WORKFLOW` 指向安装目录；在当前终端设置即可，不需要修改 shell 配置：

```bash
export MARY_WORKFLOW="$HOME/.codex/skills/mary-workflow"
python "$MARY_WORKFLOW/scripts/mary_workflow.py" --help
```

## 选择入口

| 当前任务 | 入口 | 执行边界 |
| --- | --- | --- |
| 新对话接手已有项目 | `/mw-context` | 先读总览、相关模块和接手记录；不自动恢复运行 |
| 局部代码、文档或配置修改 | `/mw-quick` | 直接修改，运行相关检查；无需全项目 init 或 SDD |
| 方法、配置已确定，立即跑实验 | `/mw-experiment` | 保存命令、日志和退出状态；无需先冻结里程碑 |
| 跨模块变更、长期规格或正式验收 | `/mw-init` → `/mw-plan` → `/mw-run` | 项目理解、冻结计划、执行、验证与审查 |
| 课程笔记、复习、论文、中文润色、Notion | 对应内容入口 | 默认独立执行，不为了内容任务初始化正式流程 |

已有正式任务的范围、停止状态和验收绑定继续有效，不能借快速入口绕过。小任务或紧耦合工作优先单代理；有独立切片、上下文隔离收益或明确独立审查要求时再委派。

## 常见操作

### 接手项目与直接修改

```text
/mw-context
/mw-quick 修复配置读取错误，只运行相关检查
```

项目记录位于 `.mary-workflow/knowledge/`：`overview.md` 描述总览，`modules/<id>.md` 描述模块，`handoff.md` 保存进度与阻塞，`index.json` 维护归属、依赖和过期标记。也可直接读取：

```bash
python "$MARY_WORKFLOW/scripts/mw_knowledge.py" read
python "$MARY_WORKFLOW/scripts/mw_knowledge.py" read --module <module-id>
```

读取不初始化项目、不写状态、不恢复实验。直接修改无需事先登记；交付时若项目已有这些记录，就用 `mw_knowledge.py changed` 登记实际改动路径并更新 handoff，没来得及更新的介绍保留 `stale`，尚未归属的文件保留 `unmapped_files`。记录依赖 agent 登记变更，不能自动发现所有外部编辑，也不证明语义理解。[上下文维护契约](references/knowledge-contract.md)

### 运行实验

```text
/mw-experiment 按刚才确定的配置立即运行，使用已分配的 GPU，预算一小时
/mw-experiment status <run-id>
/mw-experiment stop <run-id>
/mw-experiment compare <run-a> <run-b>
```

Linux 下可以直接调用 runner，`--` 后是字面 argv，不隐式解析 shell 语法：

```bash
python "$MARY_WORKFLOW/scripts/mw_experiment.py" run \
  --config configs/train.yaml --resource GPU-actual-uuid --timeout 3600 \
  -- python train.py --config configs/train.yaml
```

- 启动保存命令、小配置原始副本、Git HEAD 引用、日志、资源声明和退出状态；不预先扫描仓库、计算数据集/checkpoint 哈希或运行全项目测试。
- 后台 supervisor 管理本地前台子进程，会话结束不代表实验完成。远端提交或自行 daemonize 的程序需要原生调度器，不能靠本地 PID 证明已经结束。
- `--resource` 只协调同用户、同主机的 Mary 运行，不分配 GPU，也不发现外部作业。CUDA 设备由实际命令指定。输出目录必须是新目录；runner 提供 `MARY_OUTPUT_DIR`，训练程序仍需实际使用它。
- `compare` 读取 `<output-dir>/metrics.json` 或启动时 `--metrics-file` 指定的有限数值；`audit <run-id> --artifact <file>` 只对已退出运行的指定产物做事后完整性记录。

退出码 `0` 只表示进程正常退出。默认来源记录为 `partial`、审阅为 `unreviewed`，不承诺精确复现、质量或科学结论。旧项目可显式调用安装位置的实验脚本，不因此升级或恢复原正式任务。[实验技能](skills/experiment/SKILL.md) · [实验契约](references/experiment-contract.md)

### 执行正式变更

```text
/mw-init
/mw-plan 为后台管理系统增加角色权限管理，并补充相应测试
/mw-run
```

`/mw-init` 建立或刷新项目说明；`/mw-plan` 记录需求、必要澄清、交付路径和验收条件并冻结计划；`/mw-run` 开始冻结计划或恢复暂停的执行。明确的执行指令就是授权，不重复索要确认；对讨论方案的认可不能被当成执行授权。

正式运行保存计划身份和 `execution_mode`：

- `single_agent`：同一 agent 实现后单独复核，记录 `same_agent`、`independent_review: false`。
- `delegated`：worker 按任务身份、允许写入范围和验收条件交付 `ready_for_review`，由不同实际身份的 verifier 审查；主线负责控制状态、验收、Git 和已授权外部操作。

两种模式都保留真实验证与审查证据；明确要求独立审查时不能降级为自审。里程碑串行，当前里程碑内可委派独立任务；还要考虑共享接口、端口、数据库和构建输出，不能只看文件是否相交。

`/mw-stop` 协调暂停并保存现场；`/mw-debug` 诊断并排入修复，回到执行阶段再修改产品；`/mw-cycle` 增量刷新项目认知并归档。旧任务的迟到结果或产物修改前的验证，不能继续充当当前验收依据。[状态契约](references/state-contract.md) · [worker 契约](references/subagent-contract.md)

需要 SDD 时，已接受规格放在 `openspec/specs/`，当前变更放在 `openspec/changes/<change-id>/`。`tasks.md` 是人工维护的任务源，`mary-task` JSON 绑定交付、验收及场景；只读检查使用：

```bash
python "$MARY_WORKFLOW/scripts/mary_workflow.py" sdd-check <change-id>
```

主线随后按契约绑定并冻结计划，验收通过后由运行时回写进度。已知验证依赖可用 `validation_inputs` 声明代码、测试、配置和 fixture；不能事后缩小范围以维持旧证据。Mary 使用 OpenSpec 风格布局，不宣称完整 OpenSpec CLI 兼容。[SDD 契约](references/sdd-contract.md)

## 命令速查

| 命令 | 用途 |
| --- | --- |
| `/mw-context` | 读取项目总览、模块说明与接手记录 |
| `/mw-quick [请求]` | 直接完成局部修改与相关检查 |
| `/mw-experiment [请求]` | 实验启动、状态、停止、比较和显式审计 |
| `/mw-init` | 初始化、理解或刷新当前项目；保留已有固定版本 |
| `/mw-plan [需求]` | 澄清必要问题并冻结可验收计划，不执行产品工作 |
| `/mw-run` | 开始冻结计划或恢复暂停的运行 |
| `/mw-status` | 只读查看阶段、worker、证据和阻塞 |
| `/mw-stop` | 协调暂停，保留部分产物和恢复记录 |
| `/mw-debug` | 诊断错误并排入聚焦修复 |
| `/mw-cycle` | 刷新项目认知并归档当前周期 |
| `/mw-learn` | Lecture 学习、slides、原始转写与课堂增量融合 |
| `/mw-exam`、`/mw-review` | 章节/考试复习、错题本、自测与模拟卷 |
| `/slide-learning` | 整理 Slide → Lecture 基础笔记 |
| `/mw-paper` | 论文阅读、总结、汇报和基于来源的问答 |
| `/mw-humanize [文本或路径]` | 润色中文，保留事实、语气、引用和确定程度 |
| `/mw-notion [请求]` | 读取或修改 Notion，检查 schema 并回读验证 |

课程内容默认直接处理，缺少可选录音或考试日期不阻塞已有来源支持的交付；显式分阶段或已绑定任务才使用正式流程。`mw_codex.py mw-learn --formal`、`mw-exam --formal` 可选择正式课程入口。

论文使用独立的 `paper_state_schema: 1` 与 `.mary-research/papers/`；来源和 JSON sidecar 放在 `artifacts/`，`slides.tex` 是可编辑汇报源，paper workspace 中 `make slide` 生成 `build/slides.pdf`。Notion 必须有实际授权连接，先读取、最小范围写入、再回读；没有连接不能声称同步成功。Humanizer-zh 保留[上游来源与 MIT 许可](skills/humanizer-zh/SKILL.md#来源与维护)，不判断作者身份或保证通过 AI 检测。

## 本地记录与汇报

初始化在生成记录前补齐项目根目录的精确忽略项：`/.mary-workflow/`、`/.mary-workflow-worker/`、`/.mary-research/`、`/.vspi/`。已有规则和 Git 索引保持原样，**已跟踪文件不会自动取消跟踪**。不使用宽泛的 `reports/`、`outputs/`、`docs/` 规则误忽略产品文件或手写 `openspec/` 规格。

`.maryignore` 和 `.mary-workflow/config.yaml` 的 `init.ignore` 控制扫描排除范围，例如 `data/**`、`*.log`；扫描排除不等于 Git 忽略，覆盖记录也不证明已理解源码。本地记录默认不自动同步到其他机器。

结果默认在聊天中汇报（quick 修改、每轮实验均如此）。只有用户明确要求或正式里程碑完成时才生成 HTML 报告：

```text
.mary-workflow/reports/
  index.html                           # 总入口，最新优先
  <YYYYMMDDTHHMMSSZ>-<task-or-run-id>/
    index.html                         # 离线结果卡
    assets/                            # 精选展示资源
```

使用固定渲染器，避免每个 worker 重写网页：

```bash
python "$MARY_WORKFLOW/scripts/mw_report.py" \
  --project . --input .mary-workflow/analysis/report.json --name task-result
```

输入最少包含 `title` 和 `summary`；`tasks`、`verification` 可引用已有结果/执行回执，再按需添加 `metrics`、`artifacts` 和 `next_steps`。报告用「通过、失败、运行中、未运行」区分实际状态；渲染器不执行测试、不做验收，自填状态不能冒充证据。

报告是给人阅读的，不是 agent 接手前置。页面离线打开，保留历史包和索引，不复制整份数据集或 checkpoint。浏览器核验是可选项；没做就标注视觉核验「未运行」。只读请求不写报告，也不为填报告重跑实验。[汇报契约与输入格式](references/report-contract.md)

## 维护与升级

技能和共享契约是维护源；生成入口不手工修改：

| 位置 | 角色 |
| --- | --- |
| `SKILL.md`、`skills/*/SKILL.md` | 路由及各领域技能 |
| `references/*.md`、`references/phases/*.md` | 共享契约与正式阶段指令 |
| `commands/*.md` | 从技能生成的命令入口 |
| `.mary-workflow/prompts/*.md` | 从阶段源生成的版本副本 |
| 项目 `.mary-workflow/runtime/` | 固定运行时及兼容契约 |

更新安装目录不会在普通 init 中替换已有项目 bundle。不要混用新脚本与旧正式提示，也不要用 `/mw-init --reset` 代替升级；reset 只适用于明确授权删除重建。

在目标项目根目录预览，获得升级授权后再应用：

```bash
# 从 2.1 迁移状态
python "$MARY_WORKFLOW/scripts/mary_workflow.py" migrate
python "$MARY_WORKFLOW/scripts/mary_workflow.py" migrate --apply

# 同状态版本的 runtime/prompts 更新
python "$MARY_WORKFLOW/scripts/mary_workflow.py" upgrade
python "$MARY_WORKFLOW/scripts/mary_workflow.py" upgrade --apply
```

迁移/升级保留备份。正式上下文默认只显示当前阶段所需部分，`mw_codex.py <alias> --full-context` 可显式展开历史。旧模型设置入口已退役，工作流不会清理或改写用户现有宿主配置。

在本仓库修改技能或阶段源后生成入口，并做相关验证：

```bash
python scripts/mw_surfaces.py
python scripts/mw_surfaces.py --check
python -m unittest discover -s tests
```

`--check` 只报告漂移，不写文件。核心测试覆盖运行时边界，不代替真实宿主、免费模型、远端连接或 GPU 实验。`python scripts/benchmark_experiments.py --repeats 5` 可在临时目录测 CPU 假实验的启动、首次进度和状态读取；组件耗时不是完整 agent 流程耗时，少量暖缓存样本也不证明总体 p95 或训练速度。

## 详细契约

- [共享策略](references/task-policy.md)：流程选择、授权、委派与交付规则。
- [项目认知](references/memory-contract.md) · [上下文维护](references/knowledge-contract.md)：项目理解、增量更新和接手。
- [状态](references/state-contract.md) · [worker](references/subagent-contract.md) · [SDD](references/sdd-contract.md)：正式执行、证据与归档。
- [宿主能力](references/host-contract.md)：实际工具与可选 hooks；没有 hooks 也可运行核心流程。
- [实验](references/experiment-contract.md) · [汇报](references/report-contract.md)：本地运行记录与人类可读结果。
- [论文](skills/paper/SKILL.md) · [课程](skills/lecture-learning/SKILL.md) · [复习](skills/exam-review/SKILL.md) · [Notion](skills/notion/SKILL.md)：独立内容流程。

文件哈希、动作白名单和提示词能发现正常流程中的误操作，**不是 shell 或文件系统沙箱**。不可信 agent 的只读范围、网络和凭据隔离必须由宿主实际执行。
