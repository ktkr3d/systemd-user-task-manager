import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw
from app_window import AppWindow

class TaskApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.systemd-task-manager")

    def do_activate(self):
        win = AppWindow(application=self)
        win.present()

if __name__ == "__main__":
    app = TaskApp()
    app.run(sys.argv)
