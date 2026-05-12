import os
import subprocess
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        locale_dir = os.path.join(self.root, 'locale')
        domain = "systemd-user-task-manager"
        
        if not os.path.exists(locale_dir):
            return

        for lang_file in os.listdir(locale_dir):
            if lang_file.endswith('.po'):
                lang = lang_file[:-3]  # '.po' を除く
                src = os.path.join(locale_dir, lang_file)
                dest_dir = os.path.join(locale_dir, lang, 'LC_MESSAGES')
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, f'{domain}.mo')
                
                print(f"Compiling translation: {src} -> {dest}")
                try:
                    # msgfmtコマンドを実行
                    subprocess.run(['msgfmt', src, '-o', dest], check=True)
                except FileNotFoundError:
                    print("Warning: 'msgfmt' command not found. Translations will not be compiled.")
                    break
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling {src}: {e}")
                    continue

        # FlatpakやLinuxの標準的なディレクトリ構造にファイルを配置するための設定
        # キーはプロジェクトルートからの相対パス、値はインストール先（/app/ または /usr/）からの相対パス
        shared_data = build_data.get('shared-data', {})
        # コンパイルされた翻訳ファイルも含める
        if os.path.exists(locale_dir):
            for root, _, files in os.walk(locale_dir):
                for file in files:
                    if file.endswith('.mo'):
                        src_path = os.path.relpath(os.path.join(root, file), self.root)
                        # locale/... を share/locale/... に配置するように指定
                        shared_data[src_path] = os.path.join("share", src_path)

        build_data['shared-data'] = shared_data