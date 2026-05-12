import sys
import os
import gettext
import locale
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw
from app_window import AppWindow

class TaskApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.systemd-task-manager")
        self.setup_i18n()

    def setup_i18n(self):
        domain = "systemd-user-task-manager"
        locale_dir = os.path.join(os.path.dirname(__file__), 'locale')
        
        gettext.bindtextdomain(domain, locale_dir)
        gettext.textdomain(domain)
        gettext.install(domain, locale_dir) # _() をグローバルに登録

    def do_activate(self):
        win = AppWindow(application=self)
        win.present()

def main():
    app = TaskApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
