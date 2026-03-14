# OpenClaw Status Summary

从 OpenClaw 本地运行数据生成多 Agent 摘要，并同步到飞书多维表格。

当前能力：
- 汇总 agent 状态
- 汇总 session 活跃度
- 恢复任务数据
  - session 任务消息
  - `HEARTBEAT.md`
  - `TODO.md` / `TASKS.md`
- 识别风险和卡点
- 同步到飞书多维表格

## 目录结构

```text
openclaw-status-summary/
├── README.md
├── SKILL.md
├── .feishu_sync.env
├── .feishu_sync.env.example
├── .gitignore
├── deploy/
│   ├── linux/
│   ├── macos/
│   └── windows/
├── references/
│   └── schema.md
└── scripts/
    ├── collect_openclaw_summary.py
    ├── sync_feishu_bitable.py
    └── run_feishu_sync.sh
```

## 下载

如果这是一个 GitHub 仓库，常见下载方式：

```bash
git clone <your-repo-url>
cd openclaw-status-summary
```

如果只是复制当前目录，保证下面这些文件都在即可：
- `SKILL.md`
- `references/schema.md`
- `scripts/collect_openclaw_summary.py`
- `scripts/sync_feishu_bitable.py`
- `scripts/run_feishu_sync.sh`
- `scripts/run_feishu_sync.ps1`
- `scripts/run_feishu_sync.bat`

## 前置条件

- 本机已安装 OpenClaw
- 本机存在 `~/.openclaw/openclaw.json`
- 已创建飞书应用，并拿到：
  - `app_id`
  - `app_secret`
  - `app_token`
- 飞书多维表已创建  
  当前示例使用 4 张表：
  - `Agents`
  - `Tasks`
  - `Risks`
  - `Snapshots`

## 配置

先复制模板：

```bash
cp .feishu_sync.env.example .feishu_sync.env
```

再编辑 [`.feishu_sync.env`](/Users/mac/Desktop/7654/openclaw-status-summary/.feishu_sync.env)：

```env
APP_ID=your_app_id
APP_SECRET=your_app_secret
APP_TOKEN=your_bitable_app_token
```

模板文件：
- [`.feishu_sync.env.example`](/Users/mac/Desktop/7654/openclaw-status-summary/.feishu_sync.env.example)

## 使用方法

### 1. 只生成本地摘要

```bash
python3 scripts/collect_openclaw_summary.py
```

输出包含两部分：
- `summary_text`
- `summary_json`

### 2. 同步到飞书

直接运行包装脚本：

macOS / Linux:

```bash
./scripts/run_feishu_sync.sh
```

Windows PowerShell:

```powershell
.\scripts\run_feishu_sync.ps1
```

Windows CMD:

```bat
scripts\run_feishu_sync.bat
```

或者直接调用同步脚本：

```bash
python3 scripts/sync_feishu_bitable.py \
  --app-id "$APP_ID" \
  --app-secret "$APP_SECRET" \
  --app-token "$APP_TOKEN"
```

## 任务来源

当前支持 3 类任务来源：

### 1. Session 任务消息

支持识别：
- `ASSIGNED: ...`
- `Task ID: ...`
- `Task Stuck Alert`
- `PERSISTENT Stuck Task Alert`

### 2. `HEARTBEAT.md`

示例：

```md
- [ ] Check inbox priority:high schedule:daily
- [ ] Review landing page copy id:copy-review status:scheduled
```

### 3. `TODO.md` / `TASKS.md`

示例：

```md
# Inbox
- [ ] Check inbox priority:high

# In Progress
- [ ] Review landing page copy id:copy-review

# Blocked
- [ ] Wait for decision priority:high
```

支持的内联字段：
- `id:...`
- `priority:...`
- `status:...`
- `schedule:...`

## 如何调整同步频率

这个项目本身不强绑定某一种定时器。你可以用任意外部调度器去运行：

```bash
./scripts/run_feishu_sync.sh
```

常见方式：

### 1. 手动执行

适合调试：

```bash
./scripts/run_feishu_sync.sh
```

### 2. Codex 自动化

适合整点或按小时执行。

### 3. 系统定时器

适合高频任务，比如：
- 每 5 分钟一次
- 只在 08:00 到 24:00 之间执行

推荐让定时器只调用平台包装脚本，这样同步逻辑和调度逻辑是分开的。

## 如果你要改成每 5 分钟同步

### macOS

示例文件：
- [openclaw-feishu-sync.plist](/Users/mac/Desktop/7654/openclaw-status-summary/deploy/macos/openclaw-feishu-sync.plist)

推荐用 `launchd`。  
注意：示例 plist 只是模板，路径和时间规则需要按你的机器改。

### Linux

示例文件：
- [openclaw-feishu-sync.cron.example](/Users/mac/Desktop/7654/openclaw-status-summary/deploy/linux/openclaw-feishu-sync.cron.example)

典型 cron 规则：

```cron
*/5 8-23 * * * /path/to/openclaw-status-summary/scripts/run_feishu_sync.sh
```

### Windows

示例文件：
- [openclaw-feishu-sync-task.ps1](/Users/mac/Desktop/7654/openclaw-status-summary/deploy/windows/openclaw-feishu-sync-task.ps1)

推荐使用 `Task Scheduler`，执行：
- `scripts/run_feishu_sync.ps1`

注意：
- Windows 的“每 5 分钟重复，直到晚上结束”通常在任务计划程序里设置重复间隔和持续时间
- 示例脚本目前先创建基础任务，重复规则建议在 UI 里补，或者后续再细化脚本

## 字段说明

结构化输出字段见：
- [schema.md](/Users/mac/Desktop/7654/openclaw-status-summary/references/schema.md)

## 常见问题

### 1. 为什么 `outputs` 为空

这是正常的。当前脚本会过滤模板、skills、配置、session、参考文档等噪音文件。  
如果最近没有真实业务产出文件，`outputs` 会是空数组，并在 `data_quality.warnings` 里给出提示。

### 2. 为什么没有任务

因为当前环境里可能没有：
- session 任务消息
- `HEARTBEAT.md` 任务
- `TODO.md` / `TASKS.md`

只要按支持格式写入，任务就会被识别。

### 3. 为什么时间字段写入飞书失败

飞书日期字段要求 Unix 时间戳。当前同步脚本已经处理了这个转换。

## 安全注意事项

- 不要把真实的 `app_secret` 提交到 GitHub
- 建议把 `.feishu_sync.env` 加入 `.gitignore`
- 如果密钥已经泄露，尽快在飞书开发者后台轮换

## 推荐发布方式

如果后面你要发布到 GitHub，建议保留：
- `README.md`
- `SKILL.md`
- `references/schema.md`
- `scripts/*.py`
- `scripts/run_feishu_sync.sh`

