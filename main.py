import sys
import os
import gettext
import shutil
import subprocess
import locale
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw
from app_window import AppWindow

class TaskApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id="io.github.ktkr3d.systemd-user-task-manager", **kwargs)
        self.setup_i18n()

    def setup_i18n(self):
        domain = "systemd-user-task-manager"
        # 1. For development (within the source tree)
        locale_dir = os.path.join(os.path.dirname(__file__), 'locale')
        
        # 2. For installed environments (e.g., /app/share/locale)
        if not os.path.exists(locale_dir):
            locale_dir = os.path.join(sys.prefix, 'share', 'locale')

        gettext.bindtextdomain(domain, locale_dir)
        gettext.textdomain(domain)
        gettext.install(domain, locale_dir) # Register _() globally

    def do_activate(self):
        win = AppWindow(application=self)
        win.present()
def main():
    app = TaskApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
