# gov-hub · 项目地图（Project Map for AI Coding Agents）

[English](README.en.md) | 中文

![License](https://img.shields.io/badge/license-MIT-blue) ![Python](https://img.shields.io/badge/python-%E2%89%A53.9-3776AB) ![DSH](https://img.shields.io/badge/DSH-plugin-6E56CF)

*DSH 插件 · Agent Skill · 项目地图（Project Map） · 文件导航 / 代码库导航 · AI coding agent*

**gov-hub 是一个 DSH 插件，也是一份通用的 Agent Skill**：给 AI coding agent 装一张「项目地图」。
它把"某个结论 / 规范 / 报告到底在哪个文件"记录在工作区内一个普通的 `registry.yaml` 里，
agent 用一条 `lookup` 命令就能直达权威文件，而不是靠 glob / grep 在几万个文件里蛮力翻找。
它做的是**文件级导航**（该读哪份文档），不做代码符号索引——查函数 / 类仍请用宿主自带 grep。

> **状态：0.3.0**（loose 档 MVP + `ensure` 入口 + 一键安装 + 三路分发）
> 适用：DSH（DeepSeek Harness）、Claude Code、以及任何支持读取 `SKILL.md` / `AGENTS.md` 的 Agent 宿主。

## 30 秒了解

| 问题 | 答案 |
|---|---|
| **这是什么** | 工作区内的文件导航图 + 一个只依赖 PyYAML 的 Python CLI；不是聊天记忆、不是向量库、不做代码符号索引 |
| **解决什么** | Agent 每次会话都要重新"翻目录找文件"，token 烧在导航上，还经常读错文件 |
| **怎么装** | `pip install pyyaml`，再执行 `python govhub.py install`，一分钟；`uninstall` 完全可逆 |
| **怎么用** | 提问前 `lookup "关键词或整句问法"` → 直达权威文件；答完 `add` 把新文件补进地图 |
| **效果** | 真实项目实测：10 次查询导航成本降低 **96.7%~99.3%**，单查询最高约 **376 倍**；同题问答 **141s/40 次调用 → 40s/5 次调用**（快 3.5 倍、调用 ÷8） |

## 为什么用它

Agent 不记得你的工作区里东西放在哪。每一次新会话都会把同样的"发现成本"再付一遍：
列目录、全文搜索、读一堆不相干的文件，最后才找到那一份权威文档。

gov-hub 把这份知识从"模型的临时推断"搬进**你工作区里的普通文本文件**：

- `registry.yaml` —— 人可读的登记表：路径、关键词、"这条能回答什么"、权威级别；
- `gov-hub.yaml` —— 范围声明：AI 只在声明的目录内活动，越界不静默扩界；
- `.govhub/index.json` —— 可随时重建的检索索引（生成物，永不当权威引用）。

没有云端、没有向量化、没有遥测；拷走仓库，地图跟着走。

## 快速上手

```bash
# 1. 获取
git clone https://github.com/songzhou666/gov-hub.git
cd gov-hub
pip install pyyaml                          # 唯一第三方依赖

# 2. 一键安装：技能文件进发现根 + AGENTS.md 入口块 + 自检
python govhub.py install                    # 用户级（推荐），所有会话生效
python govhub.py install --scope project    # 或仅当前项目（.dsh/skills/）

# 3. 卸载（完全可逆；工作区里的地图数据不会被删）
python govhub.py uninstall
```

非 DSH 宿主（如 Claude Code）用 `--skill-dir` 显式指定技能目录，入口块可用
`attach --file` 写入该宿主的入口文件：

```bash
python govhub.py install   --skill-dir <宿主技能目录>        # 如 Claude Code：~/.claude/skills
python govhub.py attach    --root <工作区> --file <工作区>/CLAUDE.md
```

安装完成后即全自动：在任何会话里问"登录的测试结论在哪个文件？"，agent 会先
`ensure`（判断该不该用地图），再 `lookup` 命中权威文件，作答后顺手把新读到的文件
`add` 回地图。**不需要你记命令。**

## 环境要求

- Python ≥ 3.9（无需虚拟环境）
- PyYAML（`pip install pyyaml`）——所有命令都依赖它；**没有降级路径**
- 不需要数据库、向量库或网络

先想亲手跑一遍？仓库自带两个虚构示例工作区（loose / mapped 档），开箱可验证：

```bash
python govhub.py check  --root seeds/sample-workspace   # 结果：通过 ✅（6 条）
python govhub.py lookup 账期 --root seeds/sample-workspace
# [  7.0] rule.billing-cycle · canonical · rules/03_账期对账规则.md
```

## 工作原理：三条命令一个闭环

| 命令 | 作用 |
|---|---|
| `ensure` | 入口闸门：`[OK]` 已启用 → 先查表；`[MUTED]` 用户已拒绝 → 静默；未声明 → 打印欢迎说明 + `[NEXT]`，由 agent 问你一次 |
| `lookup "<关键词或整句问法>"` | 分层打分（标题 / 关键词 / 能回答什么 / 路径，相等满分、包含半分），同分按权威级别排序 → 返回权威文件路径 |
| `add <文件> --keywords ... --answers "..."` | 回灌：任何"靠翻找才找到"的权威文件，一条命令登记并同步索引 |

配套命令：`init`（范围确认 + 登记表骨架）· `check`（登记表 ↔ 磁盘一致性机检）·
`status`（四段健康灯）· `suggest`（从查询轨迹提炼该补的条目）·
`attach` / `detach`（在 `AGENTS.md` 写/删自己的标记块，块外内容不改）· `install` / `uninstall`。

**四段健康灯**：供给（登记表一致性）/ 执行 / 产出 / 回灌，各绑定机检；
`loose` 档默认零假设、只读治理，`mapped` 档声明容器映射后才启用后三段扫描。

**关键设计：决定由命令输出做，不交给模型判断。** 该不该启用、要不要提问，是 `ensure`
的打印结果，不是模型的自由裁量——把时机判断留给模型，实测会失败
（见 [`references/anti-patterns.md`](references/anti-patterns.md)）。

## 常用命令

```bash
# 初始化（范围确认关：候选目录需人工确认后才固化）
python govhub.py init --root <工作区>

# 登记一条资产（自动机检 + 同步索引）
python govhub.py add docs/登录测试报告.md --root <工作区> \
  --keywords 登录,验证码,测试结论 --answers "登录验证码的测试结论与证据"

# 检索
python govhub.py lookup "登录 验证码 结论" --root <工作区>

# 机检 / 体检 / 补条目提案
python govhub.py check   --root <工作区>
python govhub.py status  --root <工作区>
python govhub.py suggest --root <工作区>

# 把入口块写进 AGENTS.md（幂等；detach 只移除标记块，块外不动）
python govhub.py attach --root <工作区> --scope project
python govhub.py detach --root <工作区> --scope project
```

**登记纪律**：同一主题下有多份独立文件（如各子端各一份清单）→ **每份一条**，
不要合并成"总表"；地图里不记录数量或统计值——数量现数即可，写进地图必然过期。

## 效果数据与出处

**微基准（导航成本）**：在真实项目资产区（36 个 Markdown 文件、167 条登记表）上，
用 10 个来自登记表的真实高频词做对照。两条路径**都包含"读目标文件"的成本**，
差值纯粹是"找到该读哪个文件"：

| 指标 | 蛮力导航 | 项目地图 | 差距 |
|---|---|---|---|
| 单查询导航成本 | 9,901 ~ 140,949 chars | 276 ~ 719 chars | 最高约 376 倍 |
| 10 查询累计（中性高频词，`bench_lookup.py` 可复现） | 624,262 chars（≈37.5 万 tokens） | 4,173 chars（≈2,500 tokens） | **降低 99.3%** |
| 10 查询累计（早期业务词，同口径另一组） | 110,758 chars（≈6.6 万 tokens） | 3,617 chars（≈2,200 tokens） | 降低 96.7% |

![导航成本对照](docs/assets/perf_chart.png)

**端到端（同题真跑）**：在约 5.7 万个文件的真实工作区，同一句"登录验证码那里发现了
什么问题？"：无地图时 141s+、40 次调用未答完；回灌 3 条后第二问 **40s、5 次调用**答完
（快 3.5 倍、调用减少 8 倍）。命中组稳定在 23~75s / 4~10 次调用，蛮力组 93~230s /
15~40 次调用，最悬殊一对 tokens 差 ≈6.8 倍。

**口径与边界（别当绝对承诺）**：

- 微基准未计蛮力路径的试错重试、误读返工与上下文污染，数字偏保守；
- token 按 chars×0.6 粗估，只看量级；
- 端到端样本量小（每组 2~4 轮）、单工作区、单日，问题不完全相同，量级可比、非精确比值；
- **装了 ≠ 立刻省钱**：空表首日仍会走蛮力（实测 43 次调用），收益在回灌 2~3 轮、
  覆盖高频问题后才兑现——所以 `add` 才是产品的核心循环。

完整实验脚本与原始数据：[`bench/bench_lookup.py`](bench/bench_lookup.py) ·
[`bench/RESULTS.md`](bench/RESULTS.md) · [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)。

## 适用与不适用

**适用**：有长期积累的文档 / 规范 / 报告 / 测试证据，且 agent 需要反复回答
"某结论在哪、什么时候做过什么"的工作区。

**不适用**：写业务功能代码、检索代码符号（用宿主自带 grep 更快）、
问"上次我们聊了什么"（地图不含对话内容）、工作区里没有任何权威文档。

**让位条款**：若项目已有自己的查询协议（如 `AGENTS.md` 里定义了 lookup 工具、
自有 `_registry.yaml`），以项目协议为准，本技能整体忽略、不邀请初始化。

## 隐私与硬边界

- **纯本地**：所有命令不发起网络请求、不上传任何数据、不收集统计；
- **依赖极简**：仅 Python ≥3.9 + PyYAML；无数据库、无向量库；
- **只新增**：除你显式执行的 `install` / `attach` / `init` / `add` 外，不写任何工作区文件（拒绝只落一个意图标记）；
- **完全可逆**：`detach` 只移除自己的标记块（块外内容不动），`uninstall` 撤销安装；
- 地图只索引**路径与关键词**，不复制文件内容；`.govhub/` 删掉即消失。

## 分发形态

同一份技能文件，三种装法任选：

- **DSH 原生 bundle**：`package.json` 声明 `dsh.bundle`，可被插件市场收录，
  DSH 的 `install_bundle` 也可直接指定本仓库 Git URL；
- **SkillHub 技能包**：根 `SKILL.md` 携带完整发布元数据，整目录上传即符合规范，
  `references/` 渐进式披露；
- **纯 clone**：不依赖任何平台，`python govhub.py install` 即可（Claude Code 等宿主同理）。

## 目录结构

```
gov-hub/
├── SKILL.md                 # 技能正文（发布元数据 + 操作手册）
├── govhub.py                # CLI 入口（包装 src/govhub）
├── src/govhub/              # 核心实现（cli.py / core.py）
├── lib/index.js             # DSH bundle 提供者（零依赖 ESM）
├── package.json             # dsh.bundle 声明与发布元数据
├── docs/                    # DESIGN / PERFORMANCE / UX_COPY / 脱敏清单 / 图表
├── bench/                   # 导航成本对照实验脚本与原始结果
├── references/              # 渐进式披露：反模式 / 示例 / 深度 FAQ
└── seeds/                   # 两个可直接运行的虚构示例工作区
```

## FAQ

1. **装了之后为什么有时候不触发？** 技能路由按 `description` 概率命中；确定性入口是
   `attach` 写进 `AGENTS.md` 的标记块，建议启用后顺手 attach。
2. **lookup 没命中怎么办？** 如实说"地图上没有"，用普通方式查找；找到权威文件后
   立刻 `add`，下次就命中（`suggest` 会把高频未命中词提成待办）。
3. **换电脑地图还在吗？** 在。地图数据都在工作区里，跟仓库走；技能重新 `install` 即可。
4. **会拖慢没启用的项目吗？** 不会。未启用区 `ensure` 返回 `[NEXT]`，一条命令即过；
   拒绝过的区 `[MUTED]` 完全静默。
5. **为什么叫 gov-hub？** governance hub 的缩写——给 agent 工作区补一层"哪个文件是权威"
   的公共约定。对用户始终只说"项目地图"。

更多：[`references/faq-deep.md`](references/faq-deep.md) ·
[`references/examples.md`](references/examples.md) ·
[`docs/UX_COPY.md`](docs/UX_COPY.md) · [`docs/DESIGN.md`](docs/DESIGN.md)

## 关键词

DSH 插件 · plugin · Agent Skill · 项目地图 · 文件导航 / 代码库导航 · project map ·
AI coding agent · Claude Code skill · 省 token · 权威文件

## 维护者

songzhou

## License

[MIT](LICENSE)
