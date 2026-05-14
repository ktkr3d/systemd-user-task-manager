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
        self.proxy.call_sync(
            "Reload",
            GLib.Variant("()", ()),
            Gio.DBusCallFlags.NONE, -1, None
        )
        # EnableUnitFiles(names, runtime, force)
        self.proxy.call_sync(
            "EnableUnitFiles",
            GLib.Variant("(asbb)", ([service_name], False, True)),
            Gio.DBusCallFlags.NONE, -1, None
        )
        self.proxy.call_sync(
            "EnableUnitFiles",
            GLib.Variant("(asbb)", ([timer_name], False, True)),
            Gio.DBusCallFlags.NONE, -1, None
        )
        # タイマーを開始
        self.proxy.call_sync(
            "StartUnit",
            GLib.Variant("(ss)", (timer_name, "replace")),
            Gio.DBusCallFlags.NONE, -1, None
        )

    def _get_unit_properties(self, unit_name):
        """D-Bus経由でユニットのプロパティを取得します。"""
        try:
            # LoadUnitを使用することで、ユニットがロードされていない場合でもディスクから読み込んでパスを取得します
            path_variant = self.proxy.call_sync(
                "LoadUnit",
                GLib.Variant("(s)", (unit_name,)),
                Gio.DBusCallFlags.NONE, -1, None
            )
            path = path_variant.unpack()[0]
            
            all_props = {}
            # 取得対象のインターフェース（Unit基本情報 + タイマー/サービス固有情報）
            ifaces = ["org.freedesktop.systemd1.Unit"]
            if unit_name.endswith(".timer"):
                ifaces.append("org.freedesktop.systemd1.Timer")
            else:
                ifaces.append("org.freedesktop.systemd1.Service")

            for iface in ifaces:
                try:
                    result = self.bus.call_sync(
                        "org.freedesktop.systemd1",
                        path,
                        "org.freedesktop.DBus.Properties",
                        "GetAll",
                        GLib.Variant("(s)", (iface,)),
                        GLib.VariantType.new("(a{sv})"),
                        Gio.DBusCallFlags.NONE, -1, None
                    )
                    if result:
                        # resultは (a{sv},) というタプル形式なので、辞書を取り出して各値をunpackする
                        props_dict = result.unpack()[0]
                        for k, v in props_dict.items():
                            # Variantが入れ子になっている場合があるため、再帰的にunpackする
                            val = v
                            while isinstance(val, GLib.Variant):
                                val = val.unpack()
                            all_props[k] = val
                except Exception as e:
                    print(f"Error getting properties for {iface}: {e}")
                    continue
            
            return all_props
        except Exception:
            return {}

    def delete_task(self, task_id):
        task_id = self._sanitize_id(task_id)
        service_name = f"{self.PREFIX}{task_id}.service"
        timer_name = f"{self.PREFIX}{task_id}.timer"
        
        try:
            self.proxy.call_sync(
                "StopUnit",
                GLib.Variant("(ss)", (timer_name, "replace")),
                Gio.DBusCallFlags.NONE, -1, None
            )
            self.proxy.call_sync(
                "StopUnit",
                GLib.Variant("(ss)", (service_name, "replace")),
                Gio.DBusCallFlags.NONE, -1, None
            )
        except Exception:
            pass

        self.proxy.call_sync(
            "DisableUnitFiles",
            GLib.Variant("(asb)", ([timer_name, service_name], False)),
            Gio.DBusCallFlags.NONE, -1, None
        )

        for ext in [".service", ".timer"]:
            path = os.path.join(self.UNIT_PATH, f"{self.PREFIX}{task_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
        
        self.proxy.call_sync(
            "Reload",
            GLib.Variant("()", ()),
            Gio.DBusCallFlags.NONE, -1, None
        )

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
                # GetUnitFileState(name) -> (state)
                try:
                    state_variant = self.proxy.call_sync(
                        "GetUnitFileState",
                        GLib.Variant("(s)", (timer_unit,)),
                        Gio.DBusCallFlags.NONE, -1, None
                    )
                    state = state_variant.unpack()[0]
                    if state == "enabled":
                        stats["enabled"] = True
                except Exception:
                    if t_props.get("UnitFileState") == "enabled":
                        stats["enabled"] = True

                # 前回実行時刻の取得 (D-Busからはマイクロ秒単位の数値が返ります)
                # LastTriggerUSecRealtime または LastTriggerUSec (monotonic) を確認
                last_usec = t_props.get("LastTriggerUSecRealtime") or t_props.get("LastTriggerUSec", 0)
                if not last_usec:
                    # タイマーの記録がない場合、サービスの開始/終了時刻をフォールバックとして使用
                    last_usec = s_props.get("ExecMainExitTimestampRealtime", 0) or \
                                s_props.get("ActiveEnterTimestampRealtime", 0) or \
                                s_props.get("InactiveEnterTimestampRealtime", 0)

                stats["last"] = self._format_usec(last_usec) or "なし"

                # 次回実行予定
                next_usec = t_props.get("NextElapseUSecRealtime") or t_props.get("NextElapseUSec", 0)
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
            self.proxy.call_sync(
                "EnableUnitFiles",
                GLib.Variant("(asbb)", ([service_name], False, True)),
                Gio.DBusCallFlags.NONE, -1, None
            )
            self.proxy.call_sync(
                "EnableUnitFiles",
                GLib.Variant("(asbb)", ([timer_name], False, True)),
                Gio.DBusCallFlags.NONE, -1, None
            )
            self.proxy.call_sync(
                "StartUnit",
                GLib.Variant("(ss)", (timer_name, "replace")),
                Gio.DBusCallFlags.NONE, -1, None
            )
        else:
            try:
                self.proxy.call_sync(
                    "StopUnit",
                    GLib.Variant("(ss)", (timer_name, "replace")),
                    Gio.DBusCallFlags.NONE, -1, None
                )
                self.proxy.call_sync(
                    "StopUnit",
                    GLib.Variant("(ss)", (service_name, "replace")),
                    Gio.DBusCallFlags.NONE, -1, None
                )
            except Exception:
                pass
            self.proxy.call_sync(
                "DisableUnitFiles",
                GLib.Variant("(asb)", ([timer_name, service_name], False)),
                Gio.DBusCallFlags.NONE, -1, None
            )

    def validate_calendar(self, schedule):
        """systemd-analyze calendarを使用してスケジュールを検証する"""
        if not schedule:
            return False, "スケジュールを入力してください"
        if schedule.startswith("startup"):
            delay = "0"
            if ":" in schedule:
                delay = schedule.split(":")[1]
            return True, f"システム起動の {delay} 分後に実行" # OnBootSecはParseCalendarで検証できないため、ここでは簡易的にOKとする

        try:
            # D-Bus経由でParseCalendarを呼び出す
            # ParseCalendar(calendar_string) -> (uint64_t next_usec, uint64_t accuracy_usec)
            result = self.bus.call_sync(
                "org.freedesktop.systemd1",
                "/org/freedesktop/systemd1",
                "org.freedesktop.systemd1.Manager",
                "ParseCalendar",
                GLib.Variant("(s)", (schedule,)),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            # 戻り値は (uint64, uint64) のタプル
            next_usec, _ = result.unpack()
            
            if next_usec > 0:
                # systemdのD-Busはエポックからのマイクロ秒を返す
                # datetime.fromtimestampは秒を期待するので、変換
                dt = datetime.datetime.fromtimestamp(next_usec / 1000000)
                return True, dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return False, "無効な形式、または将来の時刻がありません"
        except GLib.Error as e:
            # D-Busエラーを捕捉し、エラーメッセージを返す
            # 例: "Invalid calendar specification"
            return False, e.message
        except Exception as e:
            return False, f"検証中に予期せぬエラーが発生しました: {e}"
