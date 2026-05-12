# Systemd User Task Manager

Systemdのユーザサービス、ユーザタイマーを管理するアプリケーション

## インストールと実行

1. 前提パッケージ
    ```bash
    sudo pacman -S python-gobject libadwaita
    flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
    flatpak install flathub org.gnome.Platform//50
    ```
2. 配布用パッケージ（Flatpak）のダウンロード
   https://github.com/ktkr3d/systemd-user-task-manager/releases
3. インストール
    ```bash
    flatpak install --user systemd-user-task-manager.flatpak
    ```
4. アプリケーションの実行
    ```bash
    flatpak run com.example.systemd-task-manager
    ```

## アンインストール

1. Flatpakパッケージの削除
    ```bash
    flatpak uninstall --user com.example.systemd-task-manager
    ```
2. （任意）作成されたsystemdユニットファイルの削除
    ```bash
    rm ~/.config/systemd/user/user-task-*
    ```

## 配布用パッケージのビルド

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
