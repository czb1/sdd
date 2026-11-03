# Phase 1: 版本检查（指令文件）

> 本文件为可配置步骤 `version_check` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=version_check` 条目时被 Read。

**执行位置**：构建执行计划之后立即执行，作为流程的第一个动作（Phase 2 之前）。不要单独提前执行——它已在计划内。

执行命令：

```bash
python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'check','--json'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
```

**If the JSON output shows `"upgrade_available": true`**, you **MUST** use **AskUserQuestion tool** with the EXACT structure below. Do NOT modify the options, labels, or descriptions — use them exactly as specified:

```
AskUserQuestion({
  questions: [{
    question: "CoreSpec 有新版本可更新。本地版本: <local_version_update_time>, 远端最新发布: <remote_version_update_time>。请选择操作：",
    header: "版本升级",
    options: [
      { label: "Upgrade", description: "下载并安装新版本。Linux 上会在当前终端前台执行安装器；Windows 上立即在后台新窗口执行，重启后生效。" },
      { label: "Skip 24h", description: "跳过本次升级提示，24小时内不再提醒" },
      { label: "Continue", description: "忽略升级，继续执行当前流程" }
    ]
  }]
})
```

Based on user's choice:
- If Upgrade: run the command below. On Linux this BLOCKS the agent until the installer finishes — the user will see the full installer output in the current terminal. On Windows the installer runs in a separate console window.
  ```bash
  python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'upgrade'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
  ```
  **You MUST show the command output to the user** and give feedback based on the JSON result:
  - If output contains `"success": true` (installer finished): tell the user the upgrade completed. Say "升级完成，请重启 CodeAgent 以加载最新版本。" (Linux) or "升级程序已在后台新窗口启动，安装完成后请重启 CodeAgent。" (Windows).
  - If output contains `"success": false` (download failed, or installer exited non-zero on Linux): tell the user the upgrade failed and show the `"error"` field from the output, e.g. "升级失败：<error 内容>。可稍后重试或手动执行升级。"
- If Skip: run the command below, replacing `<REMOTE_TIME>` with the `remote_version_update_time` value from the check output, then proceed to next step:
  ```bash
  python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'skip','--hours','24','--create-time','<REMOTE_TIME>'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
  ```
- If Continue: proceed to next step directly

**If the JSON output shows `"upgrade_available": false`**, or the command fails, proceed to next step directly.

**IMPORTANT**: The workflow ALWAYS continues to next step after this step, regardless of which option the user chose. Do NOT stop or wait for restart.
