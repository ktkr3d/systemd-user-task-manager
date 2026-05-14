# Systemd User Task Manager

Systemdのユーザサービス、ユーザタイマーを管理するアプリケーション

## インストールと実行

1. 前提パッケージ
    ```bash
    sudo pacman -S python-gobject libadwaita
    ```
    ```bash
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
    flatpak run io.github.ktkr3d.systemd-user-task-manager
    ```
    またはアプリケーションメニューから起動

## アンインストール

1. Flatpakパッケージの削除
    ```bash
    flatpak uninstall --user io.github.ktkr3d.systemd-user-task-manager
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
3. 前提Flatpakパッケージ
    ```bash
    # SDKのインストール（ビルド用）
    flatpak install flathub org.gnome.Sdk//50
    # プラットフォームのインストール（実行用）
    flatpak install flathub org.gnome.Platform//50
    ```
4. クローン
    ```bash
    git clone https://github.com/ktkr3d/systemd-user-task-manager.git
    ```
5. ビルドとFlatpakパッケージの生成

    ```bash
    # 1. まずリポジトリ(repo)としてエクスポートしながらビルド
    flatpak-builder --repo=repo --force-clean build-dir io.github.ktkr3d.systemd-user-task-manager.yaml

    # 2. リポジトリから単一の .flatpak ファイルを生成
    flatpak build-bundle repo systemd-user-task-manager.flatpak io.github.ktkr3d.systemd-user-task-manager
    ```

## クリーン

1. クリーン
    ```bash
    flatpak-builder --force-clean build-dir io.github.ktkr3d.systemd-user-task-manager.yaml
    ```
2. パッケージ削除
    ```bash
    rm systemd-user-task-manager.flatpak
    ```
