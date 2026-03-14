# OpenClaw Status Summary

从 OpenClaw 本地运行数据生成多 Agent 摘要，并同步到飞书多维表格。

它会汇总这些信息：
- agent 状态
- session 活跃度
- 任务数据
- 风险和卡点
- 摘要快照

## 你会用到的文件

- [配置模板](/Users/mac/Desktop/7654/openclaw-status-summary/.feishu_sync.env.example)
- [摘要采集脚本](/Users/mac/Desktop/7654/openclaw-status-summary/scripts/collect_openclaw_summary.py)
- [飞书同步脚本](/Users/mac/Desktop/7654/openclaw-status-summary/scripts/sync_feishu_bitable.py)
- [一键同步脚本 macOS/Linux](/Users/mac/Desktop/7654/openclaw-status-summary/scripts/run_feishu_sync.sh)
- [一键同步脚本 Windows PowerShell](/Users/mac/Desktop/7654/openclaw-status-summary/scripts/run_feishu_sync.ps1)
- [一键同步脚本 Windows CMD](/Users/mac/Desktop/7654/openclaw-status-summary/scripts/run_feishu_sync.bat)
- [字段结构说明](/Users/mac/Desktop/7654/openclaw-status-summary/references/schema.md)

## 前置条件

- 本机已安装 OpenClaw
- 本机存在 `~/.openclaw/openclaw.json`
- 已创建飞书应用，并拿到：
  - `app_id`
  - `app_secret`
  - `app_token`
- 飞书多维表已准备好  
  默认使用 4 张表：
  - `Agents`
  - `Tasks`
  - `Risks`
  - `Snapshots`

## 配置

先复制模板文件：

```bash
cp .feishu_sync.env.example .feishu_sync.env
```

然后编辑 [`.feishu_sync.env`](/Users/mac/Desktop/7654/openclaw-status-summary/.feishu_sync.env)：

```env
APP_ID=your_app_id
APP_SECRET=your_app_secret
APP_TOKEN=your_bitable_app_token
```

## 使用方法

### 1. 只生成本地摘要

```bash
python3 scripts/collect_openclaw_summary.py
```

输出包含：
- `summary_text`
- `summary_json`

### 2. 同步到飞书

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

如果你想直接运行底层脚本：

```bash
python3 scripts/sync_feishu_bitable.py \
  --app-id "$APP_ID" \
  --app-secret "$APP_SECRET" \
  --app-token "$APP_TOKEN"
```

## 任务来源

当前支持 3 类任务来源。

### Session 任务消息

支持识别：
- `ASSIGNED: ...`
- `Task ID: ...`
- `Task Stuck Alert`
- `PERSISTENT Stuck Task Alert`

### `HEARTBEAT.md`

示例：

```md
- [ ] Check inbox priority:high schedule:daily
- [ ] Review landing page copy id:copy-review status:scheduled
```

### `TODO.md` / `TASKS.md`

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

这个项目不强绑定某一种定时器。你可以用任意外部调度器，只要它最终执行下面这个入口即可：

macOS / Linux:

```bash
./scripts/run_feishu_sync.sh
```

Windows:

```powershell
.\scripts\run_feishu_sync.ps1
```

## 每 5 分钟同步的示例

### macOS

可参考：
- [openclaw-feishu-sync.plist](/Users/mac/Desktop/7654/openclaw-status-summary/deploy/macos/openclaw-feishu-sync.plist)

### Linux

可参考：
- [openclaw-feishu-sync.cron.example](/Users/mac/Desktop/7654/openclaw-status-summary/deploy/linux/openclaw-feishu-sync.cron.example)

典型 cron 规则：

```cron
*/5 8-23 * * * /path/to/openclaw-status-summary/scripts/run_feishu_sync.sh
```

### Windows

可参考：
- [openclaw-feishu-sync-task.ps1](/Users/mac/Desktop/7654/openclaw-status-summary/deploy/windows/openclaw-feishu-sync-task.ps1)

Windows 通常使用 `Task Scheduler`，让它执行：

```powershell
.\scripts\run_feishu_sync.ps1
```

## 常见问题

### 为什么 `outputs` 为空

这是正常的。脚本会过滤模板、skills、配置、session、参考文档等噪音文件。  
如果最近没有真实业务产出文件，`outputs` 会是空数组，并在 `data_quality.warnings` 里给出提示。

### 为什么没有任务

因为当前环境里可能没有：
- session 任务消息
- `HEARTBEAT.md` 任务
- `TODO.md` / `TASKS.md`

只要按支持格式写入，任务就会被识别。

### 为什么时间字段写入飞书失败

飞书日期字段要求 Unix 时间戳。同步脚本已经处理了这个转换。

真实配置放在 `.feishu_sync.env`
