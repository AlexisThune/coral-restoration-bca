#!/bin/bash
set -e

# Répertoires source et installation
: "${XB_SRC_DIR:=$HOME/xbeach_src}"
: "${XB_BIN_DIR:=$HOME/xbeach_bin}"

# Vérifie si déjà compilé et installé
if [ -x "$XB_BIN_DIR/bin/xbeach" ]; then
    echo "✅ XBeach déjà compilé : $XB_BIN_DIR/bin/xbeach"
    exit 0
fi

# Clonage du repo si pas encore fait
if [ ! -d "$XB_SRC_DIR" ]; then
    git clone https://github.com/openearth/xbeach.git "$XB_SRC_DIR"
fi

cd "$XB_SRC_DIR"

# Nettoyage si compilation précédente
make distclean || true

# Génération des scripts configure
./autogen.sh

# Configuration avec flags d'optimisation
FCFLAGS="-mtune=corei7-avx -funroll-loops --param max-unroll-times=4 \
-ffree-line-length-none -O3 -ffast-math" \
./configure --with-netcdf --with-mpi --prefix="$XB_BIN_DIR"

# Compilation et installation
make -j"$(nproc)"
make install

echo "✅ XBeach compilé et installé dans $XB_BIN_DIR/bin/xbeach"