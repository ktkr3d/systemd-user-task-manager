#!/bin/bash
# Automatically compiles .po files to .mo whenever they are saved.
# Requirements: sudo pacman -S inotify-tools

DOMAIN="systemd-user-task-manager"
LOCALE_DIR="locale"

echo "Watching $LOCALE_DIR for changes in .po files..."

inotifywait -m -e close_write -r "$LOCALE_DIR" --format '%w%f' | while read FILE
do
    if [[ "$FILE" == *.po && "$FILE" != *".pot" ]]; then
        LANG_NAME=$(basename "$FILE" .po)
        DEST_DIR="$LOCALE_DIR/$LANG_NAME/LC_MESSAGES"
        mkdir -p "$DEST_DIR"
        echo "Compiling $FILE -> $DEST_DIR/$DOMAIN.mo"
        msgfmt "$FILE" -o "$DEST_DIR/$DOMAIN.mo"
    fi
done