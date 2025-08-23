#!/bin/bash
set -e

: "${XB_BIN_DIR:=$HOME/xbeach_bin}"
mkdir -p "$XB_BIN_DIR"

XB_BIN="$XB_BIN_DIR/xbeach"

if [ -f "$XB_BIN" ]; then
    echo "✅ XBeach déjà compilé : $XB_BIN"
    exit 0
fi

echo "Clonage et compilation de XBeach..."

if [ ! -d "$XB_BIN" ]; then
    git clone https://github.com/openearth/xbeach.git "$XB_BIN"
fi

cd "$XB_BIN"
autoreconf --install
./configure
make

echo "✅ XBeach compilé avec succès dans $XB_BIN"
