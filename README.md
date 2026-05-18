# Systemd User Task Manager

An application to manage systemd user services and user timers.

## Installation and Running

1. Prerequisites
    ```bash
    sudo pacman -S python-gobject libadwaita
    ```
    ```bash
    flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
    flatpak install flathub org.gnome.Platform//50
    ```
2. Download the distribution package (Flatpak)
   https://github.com/ktkr3d/systemd-user-task-manager/releases
3. Installation
    ```bash
    flatpak install --user systemd-user-task-manager.flatpak
    ```
4. Running the application
    ```bash
    flatpak run io.github.ktkr3d.systemd-user-task-manager
    ```
    Or launch it from the application menu.

## Uninstallation

1. Remove the Flatpak package
    ```bash
    flatpak uninstall --user io.github.ktkr3d.systemd-user-task-manager
    ```
2. (Optional) Delete created systemd unit files
    ```bash
    rm ~/.config/systemd/user/user-task-*
    ```

## Building Distribution Packages

1. Prerequisites
    ```bash
    sudo pacman -S python-gobject libadwaita
    ```
2. Development packages
    ```bash
    sudo pacman -S python-hatch
    ```
3. Prerequisite Flatpak packages
    ```bash
    # Install SDK (for building)
    flatpak install flathub org.gnome.Sdk//50
    # Install Platform (for running)
    flatpak install flathub org.gnome.Platform//50
    ```
4. Clone
    ```bash
    git clone https://github.com/ktkr3d/systemd-user-task-manager.git
    ```
5. Build and generate Flatpak package

    ```bash
    # 1. Build while exporting as a repository (repo)
    flatpak-builder --repo=repo --force-clean build-dir io.github.ktkr3d.systemd-user-task-manager.yaml

    # 2. Generate a single .flatpak file from the repository
    flatpak build-bundle repo systemd-user-task-manager.flatpak io.github.ktkr3d.systemd-user-task-manager
    ```

## Clean

1. Clean
    ```bash
    flatpak-builder --force-clean build-dir io.github.ktkr3d.systemd-user-task-manager.yaml
    ```
2. Delete package
    ```bash
    rm systemd-user-task-manager.flatpak
    ```
