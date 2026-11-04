# 实测输出示例

三个真实场景的命令输入与关键输出（数据来自 <实测工作区> 犬牙区实测，2026-11）。

## 示例 1：ensure 三态（未声明区）

```
$ python govhub.py ensure --root <工作区>
gov-hub · 项目地图（未声明）
每次会话都先翻目录找文件？装一张项目地图，AI 直达权威文件——
实测导航成本降低 96.7%~99.3%，端到端问答 141 秒/40 次调用 → 40 秒/5 次调用。

  1. 好，装上（写 gov-hub.yaml，之后每问先查地图）
  2. 暂不启用，别再问（永久静默）
  3. 这次先不用 → 不写任何文件，继续回答
[NEXT] 请向用户展示以上说明并询问选择。
```
→ agent 调 ask_user_question 三选一；选 1 后立刻 `init --main` 并回填已读文件。

## 示例 2：lookup 命中（直达）

```
$ python govhub.py lookup "验证码爆破 XFF 绕过" --root <实测工作区>
命中 1 条：
  work/07_evidence/otp_bruteforce_200qps.json [generated]
  能回答: 200QPS 验证码爆破压测的请求构造、XFF 轮换与限流绕过实测数据
  关键词: 验证码撞码, XFF 轮换, 200QPS, 验证码爆破, 限流绕过
```
→ agent 直接读该 JSON 引用数据，全程 5 次调用收尾（对照组蛮力翻目录 40 次/141 秒+）。

## 示例 3：回灌（add 一条新权威文件）

```
$ python govhub.py add docs/登录口令枚举-测试环境实测.md --root <实测工作区> \
    --keywords 登录,口令枚举,弱口令 --answers "登录口令枚举的实测步骤与结论"
[OK] 已登记 docs/登录口令枚举-测试环境实测.md
[OK] check 通过（supply 3 green, 0 warn）；索引已同步
```
→ 登记即机检：路径不在盘、关键词为空都会当场拒绝并回滚，不会写出坏地图。
