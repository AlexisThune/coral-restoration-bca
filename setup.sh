#!/bin/bash
set -e

# Répertoire d'installation de XBeach
: "${XB_PREFIX:=$HOME/xbeach_install}"
mkdir -p "$XB_PREFIX"

# Vérifie si déjà compilé
if [ -x "$XB_PREFIX/bin/xbeach" ]; then
    echo "✅ XBeach déjà compilé : $XB_PREFIX/bin/xbeach"
    exit 0
fi

echo "📦 Installation des dépendances système..."
sudo apt-get update
sudo apt-get install -y autoconf automake libtool gfortran \
    libnetcdf-dev libnetcdff-dev libopenmpi-dev openmpi-bin build-essential

echo "📦 Installation des dépendances Python..."
pip install mako

# Clonage du repo si pas encore fait
if [ ! -d "$HOME/xbeach_src" ]; then
    git clone https://github.com/openearth/xbeach.git "$HOME/xbeach_src"
fi

cd "$HOME/xbeach_src"

# Nettoyage si compilation précédente
make distclean || true

# Génération des scripts configure
./autogen.sh

# Configuration avec flags d'optimisation
FCFLAGS="-mtune=corei7-avx -funroll-loops --param max-unroll-times=4 \
-ffree-line-length-none -O3 -ffast-math" \
./configure --with-netcdf --with-mpi --prefix="$XB_PREFIX"

# Compilation et installation
make -j"$(nproc)"
make install

echo "✅ XBeach compilé et installé dans $XB_PREFIX"
