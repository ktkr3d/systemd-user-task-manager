import os
import subprocess
import re
import datetime
from gi.repository import Gio, GLib

class SystemdManager:
    UNIT_PATH = os.path.expanduser("~/.config/systemd/user/")
    PREFIX = "user-task-"

    def __init__(self):
        os.makedirs(self.UNIT_PATH, exist_ok=True)
        # --userに相当するセッションバスを取得
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # systemdのManagerプロキシを作成
        self.proxy = Gio.DBusProxy.new_sync(
            self.bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.systemd1",
            "/org/freedesktop/systemd1",
            "org.freedesktop.systemd1.Manager",
            None
        )

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

        # D-Bus経由で操作
        self.proxy.Reload()
        # EnableUnitFiles(names, runtime, force)
        self.proxy.EnableUnitFiles([service_name], False, True)
        self.proxy.EnableUnitFiles([timer_name], False, True)
        # タイマーを開始
        self.proxy.StartUnit(timer_name, "replace")

    def _get_unit_properties(self, unit_name):
        """D-Bus経由でユニットのプロパティを取得します。"""
        try:
            # GetUnitはユニットがロードされていない場合に例外を投げます
            path = self.proxy.GetUnit(unit_name)
            
            # Unitインターフェースのプロパティを取得
            unit_props = self.bus.call_sync(
                "org.freedesktop.systemd1",
                path,
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", ["org.freedesktop.systemd1.Unit"]),
                None, Gio.DBusCallFlags.NONE, -1, None
            ).unpack()[0]
            
            # タイマーまたはサービス固有のプロパティを取得
            iface = "org.freedesktop.systemd1.Timer" if unit_name.endswith(".timer") else "org.freedesktop.systemd1.Service"
            spec_props = self.bus.call_sync(
                "org.freedesktop.systemd1",
                path,
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", [iface]),
                None, Gio.DBusCallFlags.NONE, -1, None
            ).unpack()[0]
            
            unit_props.update(spec_props)
            return unit_props
        except Exception:
            return {}

    def delete_task(self, task_id):
        task_id = self._sanitize_id(task_id)
        service_name = f"{self.PREFIX}{task_id}.service"
        timer_name = f"{self.PREFIX}{task_id}.timer"
        
        try:
            self.proxy.StopUnit(timer_name, "replace")
            self.proxy.StopUnit(service_name, "replace")
        except Exception:
            pass

        self.proxy.DisableUnitFiles([timer_name, service_name], False)
        
        for ext in [".service", ".timer"]:
            path = os.path.join(self.UNIT_PATH, f"{self.PREFIX}{task_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
        
        self.proxy.Reload()

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
                service_unit = f"{self.PREFIX}{task_id}.service"

                t_props = self._get_unit_properties(timer_unit)
                s_props = self._get_unit_properties(service_unit)

                stats = {"last": "なし", "next": "なし", "enabled": False}

                # 有効化状態の確認 (ロードされていない場合も考慮してManagerから取得を試みる)
                try:
                    state = self.proxy.GetUnitFileState(timer_unit)
                    if state == "enabled":
                        stats["enabled"] = True
                except Exception:
                    if t_props.get("UnitFileState") == "enabled":
                        stats["enabled"] = True

                # 前回実行時刻の取得 (D-Busからはマイクロ秒単位の数値が返ります)
                last_usec = t_props.get("LastTriggerUSecRealtime", 0)
                if not last_usec:
                    # タイマーの記録がない場合、サービスの開始/終了時刻をフォールバックとして使用
                    last_usec = s_props.get("ExecMainExitTimestampRealtime", 0) or \
                                s_props.get("ActiveEnterTimestampRealtime", 0) or \
                                s_props.get("InactiveEnterTimestampRealtime", 0)

                stats["last"] = self._format_usec(last_usec) or "なし"

                # 次回実行予定
                next_usec = t_props.get("NextElapseUSecRealtime", 0)
                stats["next"] = self._format_usec(next_usec) or "なし"

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

    def _format_usec(self, usec):
        if not usec or usec <= 0 or usec >= 18446744073709551615:
            return None
        dt = datetime.datetime.fromtimestamp(usec / 1000000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def toggle_task(self, task_id, enabled):
        task_id = self._sanitize_id(task_id)
        service_name = f"{self.PREFIX}{task_id}.service"
        timer_name = f"{self.PREFIX}{task_id}.timer"
        if enabled:
            self.proxy.EnableUnitFiles([service_name], False, True)
            self.proxy.EnableUnitFiles([timer_name], False, True)
            self.proxy.StartUnit(timer_name, "replace")
        else:
            try:
                self.proxy.StopUnit(timer_name, "replace")
                self.proxy.StopUnit(service_name, "replace")
            except Exception:
                pass
            self.proxy.DisableUnitFiles([timer_name, service_name], False)

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
        except FileNotFoundError:
            return False, "systemd-analyze コマンドが見つかりません"
        except subprocess.CalledProcessError as e:
            # エラーメッセージを整形（プレフィックスを除去）
            error_msg = e.stderr.splitlines()[0] if e.stderr else "無効な形式です"
            if ":" in error_msg:
                error_msg = error_msg.split(":", 1)[-1].strip()
            return False, error_msg
        return False, "検証できませんでした"
