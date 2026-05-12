# Systemd User Task Manager

Systemdのユーザサービス、ユーザタイマーを管理するアプリケーション

## インストールと実行

1. 前提パッケージ
    ```bash
    sudo pacman -S python-gobject libadwaita
    ```
2. ダウンロード
   https://github.com/ktkr3d/systemd-user-task-manager/releases
3. インストール
    ```bash
    python3 -m pip install --user dist/*.whl
    ```
4. 実行
    ```bash
    systemd-user-task-manager
    ```

## ビ配布用パッケージのビルド

1. 前提パッケージ
    ```bash
    sudo pacman -S python-gobject libadwaita
    ```
2. 開発パッケージ
    ```bash
    sudo pacman -S python-hatch
    ```
3. flatpak
    ```bash
    # SDKのインストール（ビルド用）
    flatpak install flathub org.gnome.Sdk//46
    # プラットフォームのインストール（実行用）
    flatpak install flathub org.gnome.Platform//46
    ```
4. クローン
    ```bash
    git clone https://github.com/ktkr3d/systemd-user-task-manager.git
    ```
5. ビルド
    ```bash
    flatpak-builder --user --install --force-clean build-dir com.example.systemd-task-manager.yaml
    ```
6. アプリケーションの実行
    ```bash
    flatpak run com.example.systemd-task-manager
    ```
7. 配布用リポジトリの作成とバンドル化

    ```bash
    # 1. まずリポジトリ(repo)としてエクスポートしながらビルド
    flatpak-builder --repo=repo --force-clean build-dir com.example.systemd-task-manager.yaml

    # 2. リポジトリから単一の .flatpak ファイルを生成
    flatpak build-bundle repo systemd-user-task-manager.flatpak com.example.systemd-task-manager
    ```
