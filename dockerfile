FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

# Installer dépendances
RUN apt-get update && apt-get install -y \
    gfortran-8 gcc-8 make wget git automake autoconf libtool \
    subversion python3 python3-pip libhdf5-dev libnetcdf-dev libopenmpi-dev openmpi-bin \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && pip3 install mako \
    && rm -rf /var/lib/apt/lists/*

# Configurer gcc/gfortran
RUN update-alternatives --install /usr/bin/gfortran gfortran /usr/bin/gfortran-8 100 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 100 \
    && update-alternatives --set gfortran /usr/bin/gfortran-8 \
    && update-alternatives --set gcc /usr/bin/gcc-8

WORKDIR /opt

# Cloner XBeach
RUN git clone https://github.com/openearth/xbeach.git

# Patch mnemoniciso.F90
RUN sed -i 's/character(kind=c_char, len=\([^)]*\))/character(kind=c_char), dimension(\1)/g' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90 \
    && sed -i 's/dimension(20), dimension(maxrank)/dimension(20, maxrank)/' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90

WORKDIR /opt/xbeach

# Compiler XBeach en statique
RUN ./autogen.sh && ./configure FFLAGS="-static-libgfortran -static-libgcc" LDFLAGS="-static-libgfortran -static-libgcc"
RUN make clean
RUN make

# Créer dossier de sortie et copier binaire
RUN mkdir -p /opt/xbeach_output
RUN cp /usr/local/bin/xbeach /opt/xbeach_output/

# Rendre exécutable
RUN chmod +x /opt/xbeach_output/xbeach

WORKDIR /opt/xbeach_output
