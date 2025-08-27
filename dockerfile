FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gfortran-8 gcc-8 make wget git automake autoconf libtool \
    subversion python3 python3-pip libhdf5-dev libnetcdf-dev libopenmpi-dev openmpi-bin \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && pip3 install mako \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/gfortran gfortran /usr/bin/gfortran-8 100 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 100 \
    && update-alternatives --set gfortran /usr/bin/gfortran-8 \
    && update-alternatives --set gcc /usr/bin/gcc-8

WORKDIR /opt
RUN git clone https://github.com/openearth/xbeach.git

# Patch mnemoniciso.F90
# 1. remplacer character(len=...) par tableau simple
RUN sed -i 's/character(kind=c_char, len=\([^)]*\))/character(kind=c_char), dimension(\1)/g' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90 \
    # 2. corriger la ligne spéciale "dimensions"
    && sed -i 's/dimension(20), dimension(maxrank)/dimension(20, maxrank)/' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90

WORKDIR /opt/xbeach

RUN ./autogen.sh && ./configure
RUN make
RUN make install
