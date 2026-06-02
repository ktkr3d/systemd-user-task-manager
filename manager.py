import os
import subprocess
import re
import datetime
from gi.repository import Gio, GLib

__version__ = "0.2.0"

class SystemdManager:
    UNIT_PATH = os.path.expanduser("~/.config/systemd/user/")
    PREFIX = "user-task-"

    def __init__(self):
        os.makedirs(self.UNIT_PATH, exist_ok=True)
        # Get the session bus corresponding to --user
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # Create the systemd Manager proxy
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
        # Replace spaces and symbols with hyphens, allowing only alphanumeric characters, hyphens, and underscores
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

        # Operate via D-Bus
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
        # Start the timer
        self.proxy.call_sync(
            "StartUnit",
            GLib.Variant("(ss)", (timer_name, "replace")),
            Gio.DBusCallFlags.NONE, -1, None
        )

    def _get_unit_properties(self, unit_name):
        """Gets unit properties via D-Bus."""
        try:
            # Using LoadUnit reads the unit from disk and retrieves the path even if it's not loaded
            path_variant = self.proxy.call_sync(
                "LoadUnit",
                GLib.Variant("(s)", (unit_name,)),
                Gio.DBusCallFlags.NONE, -1, None
            )
            path = path_variant.unpack()[0]
            
            all_props = {}
            # Interfaces to retrieve (Unit basic info + Timer/Service specific info)
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
                        # Since result is in (a{sv},) tuple format, extract the dictionary and unpack each value
                        props_dict = result.unpack()[0]
                        for k, v in props_dict.items():
                            # Recursively unpack as Variants might be nested
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
                # Simple parsing of the schedule from the timer file
                schedule = ""
                persistent = False
                with open(os.path.join(self.UNIT_PATH, filename), "r") as f:
                    for line in f:
                        if line.startswith("OnCalendar="):
                            schedule = line.split("=")[1].strip()
                        elif line.startswith("OnBootSec="):
                            val = line.split("=")[1].strip()
                            # Extract only the numerical part and format as 'startup:X'
                            match = re.search(r'(\d+)', val)
                            delay = match.group(1) if match else "0"
                            schedule = f"startup:{delay}"
                        elif line.startswith("Persistent="):
                            persistent = line.split("=")[1].strip().lower() == "true"
                
                # Get command from the service file
                command = ""
                service_file = filename.replace(".timer", ".service")
                service_path = os.path.join(self.UNIT_PATH, service_file)
                if os.path.exists(service_path):
                    with open(service_path, "r") as f:
                        for line in f:
                            if line.startswith("ExecStart="):
                                command = line.split("=")[1].strip()

                # Get unit status (last/next execution time)
                timer_unit = f"{self.PREFIX}{task_id}.timer"
                service_unit = f"{self.PREFIX}{task_id}.service"

                t_props = self._get_unit_properties(timer_unit)
                s_props = self._get_unit_properties(service_unit)

                stats = {"last": "None", "next": "None", "enabled": False}

                # Check enablement status (try retrieving from Manager considering it might not be loaded)
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

                # Get last execution time (D-Bus returns values in microseconds)
                # Check LastTriggerUSecRealtime or LastTriggerUSec (monotonic)
                last_usec = t_props.get("LastTriggerUSecRealtime") or t_props.get("LastTriggerUSec", 0)
                if not last_usec:
                    # If no timer record exists, use service start/stop timestamps as fallback
                    last_usec = s_props.get("ExecMainExitTimestampRealtime", 0) or \
                                s_props.get("ActiveEnterTimestampRealtime", 0) or \
                                s_props.get("InactiveEnterTimestampRealtime", 0)

                stats["last"] = self._format_usec(last_usec) or "None"

                # Next scheduled execution
                next_usec = t_props.get("NextElapseUSecRealtime") or t_props.get("NextElapseUSec", 0)
                stats["next"] = self._format_usec(next_usec) or "None"

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
        """Validate schedule using systemd-analyze calendar"""
        schedule = schedule.strip()
        if not schedule:
            return False, _("Please enter a schedule"), "error"
        if schedule.startswith("startup"):
            delay = "0"
            if ":" in schedule:
                delay = schedule.split(":")[1]
            return True, _("Run {} minutes after system boot").format(delay), "ok" # OnBootSec cannot be validated with ParseCalendar, so we'll just accept it here

        try:
            # まずはD-Bus経由で試行
            result = self.proxy.call_sync(
                "ParseCalendar",
                GLib.Variant("(s)", (schedule,)),
                Gio.DBusCallFlags.NONE, -1, None
            )
            next_usec, _ = result.unpack()
            if 0 < next_usec < 18446744073709551615:
                dt = datetime.datetime.fromtimestamp(next_usec / 1000000)
                return True, dt.strftime("%Y-%m-%d %H:%M:%S"), "ok"
        except Exception:
            pass

        # D-Busが失敗した場合はコマンドラインツールでフォールバック
        cmd = ["systemd-analyze", "calendar", schedule]
        
        # Flatpak環境の場合はホストのコマンド実行を試みる
        if os.path.exists("/.flatpak-info"):
            cmd = ["flatpak-spawn", "--host"] + cmd

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if "Next elapse:" in line:
                        return True, line.replace("Next elapse:", "").strip(), "ok"
            
            err_msg = proc.stderr.strip()
            # Flatpakの権限不足エラーを検知
            if "org.freedesktop.Flatpak" in err_msg:
                return False, _("Validation unavailable: Flatpak permission 'talk-name=org.freedesktop.Flatpak' is required to use host tools."), "unavailable"
            
            if err_msg:
                return False, err_msg.split('\n')[-1], "error"
            return False, _("Invalid schedule format"), "error"
        except FileNotFoundError:
            # systemd-analyze が見つからない場合
            return False, _("Validation unavailable: 'systemd-analyze' command not found."), "unavailable"
        except Exception as e:
            return False, str(e), "error"
