# Step 1: 版本检查（指令文件）

> 本文件为可配置步骤 `version_check` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=version_check` 条目时被 Read。

**执行位置**：主流程第一阶段 Step 0（构建执行计划）之后立即执行，作为第一阶段的第二个动作。不要单独提前执行——它已在计划内。

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
      { label: "Upgrade", description: "下载并安装新版本（立即在后台执行，重启后生效）" },
      { label: "Skip 24h", description: "跳过本次升级提示，24小时内不再提醒" },
      { label: "Continue", description: "忽略升级，继续执行当前流程" }
    ]
  }]
})
```

Based on user's choice:
- If Upgrade: run the command below. The installer runs in background. Then **IMMEDIATELY proceed to next step** — do NOT wait for the installer to finish, do NOT ask the user to restart now. Simply note: "升级已在后台启动，安装完成后请重启 CodeAgent。"
  ```bash
  python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'upgrade'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
  ```
- If Skip: run the command below, replacing `<REMOTE_TIME>` with the `remote_version_update_time` value from the check output, then proceed to next step:
  ```bash
  python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'skip','--hours','24','--create-time','<REMOTE_TIME>'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
  ```
- If Continue: proceed to next step directly

**If the JSON output shows `"upgrade_available": false`**, or the command fails, proceed to next step directly.

**IMPORTANT**: The workflow ALWAYS continues to next step after this step, regardless of which option the user chose. Do NOT stop or wait for restart.
