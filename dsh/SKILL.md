---
name: gov-hub
description: 当需要查找项目内容时加载——包括"某功能/结论/规范/报告在哪个文件"、"项目什么时候做过什么测试/检查/改动"等询问项目历史与现状的问题。让 AI 按项目地图直达权威文件而不是蛮力翻文件夹，实测导航成本降低 96.7%~99.3%。触发场景：找文件、找结论、问项目过去做过什么、收尾检查新增产出是否归档、用户提到项目地图/资产索引。注意：若项目已有自己的资产查询协议（如 AGENTS.md 中定义的 lookup 工具），以项目协议为准，本技能自动让位。关键词：在哪、找、哪个文件、什么时候、做过什么、历史、报告、结论、项目地图、资产、归档。
---

本技能是**薄壳**，不含实现正文。CLI 唯一权威用法来源：gov-hub 仓库（https://github.com/songzhou/gov-hub ，本地安装见 README）。

> **安装参数（安装者必改：把下面路径改成你本机的实际克隆位置）**
> CLI_PATH = E:\Mytest_plugin\gov-hub\govhub.py
> PYTHON = C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe
> （下文所有命令用这两个值代入；找不到 CLI_PATH 时**禁止**静默放弃——告知用户"gov-hub 未安装或路径失效，请按 README 安装"，然后才回退普通方式。）

命中场景时**必须按以下顺序执行，不得跳步**：

## 第 0 步：查声明（必做，无论项目是否启用过）

用 glob 检查工作区根目录是否存在 `gov-hub.yaml`。两种分支：

**分支 A：不存在（未声明区）——这是第一交互重点，绝不能跳过直接干活：**

1. 运行：`PYTHON CLI_PATH init --explain --root <工作区>`，
   把输出的欢迎式说明**完整展示给用户**；
2. 用 `ask_user_question` 工具按三岔口提问：
   - **启用**（推荐）→ 运行 `PYTHON CLI_PATH init --main <探测到的主目录>`，完成后继续第 1 步；
   - **暂不启用，别再问** → 运行 `PYTHON CLI_PATH init --decline`，告知已静默，然后按项目原有方式干活；
   - **这次先不用** → 不写任何文件，按项目原有方式干活（下次会话只轻问一句）；
3. 三岔口回答前**不得开始翻文件回答用户原问题**——先问完，再干活。

**分支 B：存在（已启用区）——按下面第 1~3 步干活。**

## 动手前（供给）
```bash
PYTHON CLI_PATH lookup <关键词> --root <工作区>
```
- 命中 → 读列出的权威文件，不蛮力翻文件夹；
- `[UNDECLARED]` → 先向用户展示 `init --explain` 说明并**询问一次**：
  同意 → `init --main <探测路径>`；拒绝/跳过 → `init --decline`，此后本项目永久静默、不得再提；
- `[MUTED]` → 用户已拒绝，静默跳过，一切按项目原有方式干活。

## 回灌（每次会话的收尾动作，两个来源都要登记）

1. **新增/移动了重要文件** → 在 registry.yaml 补条目；
2. **回答问题时用到了地图上没有的文件**（lookup 未命中、靠浏览找到的权威文件）
   → **必须**把该文件登记成新条目（id/type/title/path/keywords/answers/authority/updated
   八字段齐全，keywords 里加用户本次的实际问法）——这是地图生长的主要方式；
   只读的临时/生成文件登记 authority: generated 或不登记。
3. 登记后跑 `PYTHON CLI_PATH check --root <工作区>` 验证（全绿才算改完）。

## 会话收尾（体检）
`PYTHON CLI_PATH status --root <工作区>` 看四灯；`PYTHON CLI_PATH suggest --root <工作区>`
看路线迹里有没有高频路线值得补关键词。

## 文案纪律
对用户只说"项目地图"，禁用"治理/登记表/回灌"等内部词；完整口径见仓库 `docs/UX_COPY.md`。
