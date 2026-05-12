import os
import subprocess
import re

class SystemdManager:
    UNIT_PATH = os.path.expanduser("~/.config/systemd/user/")
    PREFIX = "user-task-"

    def __init__(self):
        os.makedirs(self.UNIT_PATH, exist_ok=True)

    def _run_systemctl(self, *args):
        subprocess.run(["systemctl", "--user"] + list(args), check=False)

    def _sanitize_id(self, task_id):
        # 空白や記号をハイフンに置換し、英数字・ハイフン・アンダースコアのみを許容する
        return re.sub(r'[^a-zA-Z0-9_-]', '-', task_id)

    def save_task(self, task_id, command, schedule, persistent):
        task_id = self._sanitize_id(task_id)
        service_name = f"{self.PREFIX}{task_id}.service"
        timer_name = f"{self.PREFIX}{task_id}.timer"

        service_content = f"[Unit]\nDescription=Task {task_id}\n\n[Service]\nType=oneshot\nExecStart={command}\n\n[Install]\nWantedBy=default.target\n"

        if schedule.startswith("startup"):
            delay_val = "0"
            if ":" in schedule:
                delay_val = schedule.split(":")[1]
            timer_body = f"OnBootSec={delay_val}min"
        else:
            timer_body = f"OnCalendar={schedule}\nPersistent={'true' if persistent else 'false'}"

        timer_content = f"[Unit]\nDescription=Timer for {task_id}\n\n[Timer]\n{timer_body}\n\n[Install]\nWantedBy=timers.target\n"

        with open(os.path.join(self.UNIT_PATH, service_name), "w") as f:
            f.write(service_content)
        with open(os.path.join(self.UNIT_PATH, timer_name), "w") as f:
            f.write(timer_content)

        self._run_systemctl("daemon-reload")
        self._run_systemctl("enable", "--now", service_name, timer_name)

    def delete_task(self, task_id):
        task_id = self._sanitize_id(task_id)
        service_name = f"{self.PREFIX}{task_id}.service"
        timer_name = f"{self.PREFIX}{task_id}.timer"
        self._run_systemctl("disable", "--now", service_name, timer_name)
        
        for ext in [".service", ".timer"]:
            path = os.path.join(self.UNIT_PATH, f"{self.PREFIX}{task_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
        
        self._run_systemctl("daemon-reload")

    def list_tasks(self):
        tasks = []
        if not os.path.exists(self.UNIT_PATH):
            return tasks
            
        for filename in os.listdir(self.UNIT_PATH):
            if filename.startswith(self.PREFIX) and filename.endswith(".timer"):
                task_id = filename[len(self.PREFIX):-6]
                # タイマーファイルからスケジュールを簡易パース
                schedule = ""
                persistent = False
                with open(os.path.join(self.UNIT_PATH, filename), "r") as f:
                    for line in f:
                        if line.startswith("OnCalendar="):
                            schedule = line.split("=")[1].strip()
                        elif line.startswith("OnBootSec="):
                            val = line.split("=")[1].strip()
                            # 数値部分のみを抽出して 'startup:X' 形式にする
                            match = re.search(r'(\d+)', val)
                            delay = match.group(1) if match else "0"
                            schedule = f"startup:{delay}"
                        elif line.startswith("Persistent="):
                            persistent = line.split("=")[1].strip().lower() == "true"
                
                # サービスファイルからコマンドを取得
                command = ""
                service_file = filename.replace(".timer", ".service")
                service_path = os.path.join(self.UNIT_PATH, service_file)
                if os.path.exists(service_path):
                    with open(service_path, "r") as f:
                        for line in f:
                            if line.startswith("ExecStart="):
                                command = line.split("=")[1].strip()

                # ユニットの状態を取得 (前回・次回の実行時刻)
                timer_unit = f"{self.PREFIX}{task_id}.timer"
                show_res = subprocess.run(
                    ["systemctl", "--user", "show", timer_unit, "--property=LastTriggerUSecRealtime,NextElapseUSecRealtime,UnitFileState"],
                    capture_output=True, text=True
                )
                
                stats = {"last": "なし", "next": "なし", "enabled": False}
                for line in show_res.stdout.splitlines():
                    if "=" in line:
                        key, val = line.split("=", 1)
                        val = val.strip()
                        if key == "UnitFileState":
                            stats["enabled"] = val.startswith("enabled")
                        elif val and val != "0":
                            if key == "LastTriggerUSecRealtime": stats["last"] = val
                            if key == "NextElapseUSecRealtime": stats["next"] = val

                tasks.append({
                    "id": task_id, 
                    "schedule": schedule, 
                    "command": command,
                    "last": stats["last"], 
                    "next": stats["next"],
                    "enabled": stats["enabled"],
                    "persistent": persistent
                })
        return tasks

    def toggle_task(self, task_id, enabled):
        task_id = self._sanitize_id(task_id)
        service_name = f"{self.PREFIX}{task_id}.service"
        timer_name = f"{self.PREFIX}{task_id}.timer"
        action = "enable" if enabled else "disable"
        self._run_systemctl(action, "--now", service_name, timer_name)

    def validate_calendar(self, schedule):
        """systemd-analyze calendarを使用してスケジュールを検証する"""
        if not schedule:
            return False, "スケジュールを入力してください"
        if schedule.startswith("startup"):
            delay = "0"
            if ":" in schedule:
                delay = schedule.split(":")[1]
            return True, f"システム起動の {delay} 分後に実行"

        try:
            res = subprocess.run(
                ["systemd-analyze", "calendar", schedule],
                capture_output=True, text=True, check=True
            )
            for line in res.stdout.splitlines():
                if "Next elapse:" in line:
                    return True, line.split(":", 1)[1].strip()
        except subprocess.CalledProcessError as e:
            # エラーメッセージを整形（プレフィックスを除去）
            error_msg = e.stderr.splitlines()[0] if e.stderr else "無効な形式です"
            if ":" in error_msg:
                error_msg = error_msg.split(":", 1)[-1].strip()
            return False, error_msg
        return False, "検証できませんでした"
