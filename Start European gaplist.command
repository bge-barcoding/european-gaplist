#!/bin/bash
# Double-click this file (macOS) to open the European gaplist notebook.
# A Terminal window opens and stays open while you work; close it when done.
cd "$(dirname "$0")"
export PATH="$HOME/.pixi/bin:$PATH"
if ! command -v pixi >/dev/null 2>&1; then
    echo "pixi is not installed yet. See docs/getting-started.md, 'One-time setup'."
    read -r -p "Press Enter to close this window."
    exit 1
fi
echo "Starting the European gaplist notebook. It opens in your web browser."
echo "Keep this window open while you work; close it when you are done."
pixi run lab
