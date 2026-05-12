import os
import subprocess
from setuptools import setup, Command
from setuptools.command.build import build as _build

class BuildMo(Command):
    """POファイルをMOファイルにコンパイルするカスタムコマンドです。"""
    description = 'compile .po files to .mo files'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        locale_dir = os.path.join(os.path.dirname(__file__), 'locale')
        domain = "systemd-user-task-manager"
        
        for lang_file in os.listdir(locale_dir):
            if lang_file.endswith('.po'):
                lang = lang_file[:-3]  # '.po' を除く
                src = os.path.join(locale_dir, lang_file)
                dest_dir = os.path.join(locale_dir, lang, 'LC_MESSAGES')
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, f'{domain}.mo')
                
                print(f"Compiling {src} -> {dest}")
                try:
                    subprocess.run(['msgfmt', src, '-o', dest], check=True)
                except FileNotFoundError:
                    print("Error: 'msgfmt' コマンドが見つかりません。'gettext' パッケージをインストールしてください。")
                    return

class Build(_build):
    """標準のbuildコマンドを拡張してbuild_moを含めます。"""
    sub_commands = [('build_mo', lambda self: True)] + _build.sub_commands

setup(
    name='systemd-user-task-manager',
    version='0.1.0',
    cmdclass={
        'build_mo': BuildMo,
        'build': Build,
    },
)