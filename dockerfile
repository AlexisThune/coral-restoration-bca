FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

# Installer dépendances et outils
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

# Cloner XBeach
WORKDIR /opt
RUN git clone https://github.com/openearth/xbeach.git

# Patch mnemoniciso.F90
RUN sed -i 's/character(kind=c_char, len=\([^)]*\))/character(kind=c_char), dimension(\1)/g' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90 \
    && sed -i 's/dimension(20), dimension(maxrank)/dimension(20, maxrank)/' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90

WORKDIR /opt/xbeach

# Compiler XBeach
RUN ./autogen.sh && ./configure
RUN make
RUN make install

# Créer un dossier de sortie pour binaire + libs
RUN mkdir -p /opt/xbeach_output

# Copier le binaire et les libs nécessaires
RUN cp /usr/local/bin/xbeach /opt/xbeach_output/ \
    && cp /usr/local/lib/libxbeach.so* /opt/xbeach_output/

# Changer droits pour exécuter tous les fichiers dans le dossier de sortie
RUN chmod -R +x /opt/xbeach_output

# Définir le dossier de sortie comme WORKDIR
WORKDIR /opt/xbeach_output