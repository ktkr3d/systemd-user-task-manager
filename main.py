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

def install_desktop_entry():
    """インストールされた.desktopファイルとアイコンをユーザーのローカルディレクトリに配置します。"""
    app_id = "com.example.systemd-task-manager"
    base_dir = os.path.dirname(__file__)
    
    # 1. .desktop ファイルのインストール
    desktop_file = "com.example.systemd-task-manager.desktop"
    desktop_src = os.path.join(base_dir, desktop_file)
    desktop_dest_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(desktop_dest_dir, exist_ok=True)
    if os.path.exists(desktop_src):
        shutil.copy2(desktop_src, os.path.join(desktop_dest_dir, desktop_file))
        print(f"Installed desktop entry to {desktop_dest_dir}")

    # 2. アイコンファイルのインストール
    icon_file = f"{app_id}.svg"
    icon_src = os.path.join(base_dir, icon_file)
    icon_dest_dir = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
    os.makedirs(icon_dest_dir, exist_ok=True)
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(icon_dest_dir, icon_file))
        print(f"Installed icon to {icon_dest_dir}")
        
        # アイコンキャッシュの更新
        icon_base_path = os.path.expanduser("~/.local/share/icons/hicolor")
        subprocess.run(["gtk4-update-icon-cache", "-f", "-t", icon_base_path], check=False)

def main():
    app = TaskApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
