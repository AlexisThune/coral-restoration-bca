#!/bin/bash
set -e

: "${XB_BIN_DIR:=$HOME/xbeach_bin}"
mkdir -p "$XB_BIN_DIR"

XB_SRC="$XB_BIN_DIR/xbeach"
XB_BIN="$XB_SRC/src/xbeach"

if [ -f "$XB_BIN" ]; then
    echo "✅ XBeach déjà compilé : $XB_BIN"
    exit 0
fi

echo "Clonage et compilation de XBeach..."

if [ ! -d "$XB_SRC" ]; then
    git clone https://github.com/openearth/xbeach.git "$XB_SRC"
fi

cd "$XB_SRC"
make config=gnuplot netcdf=1 mpi=1

echo "✅ XBeach compilé avec succès dans $XB_BIN"
