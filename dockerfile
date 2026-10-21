FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

# 1. Installer les dépendances système de base + gdal
RUN apt-get update && apt-get install -y \
    gfortran-8 gcc-8 make wget git automake autoconf libtool \
    subversion python3 python3-pip libhdf5-dev libnetcdf-dev libopenmpi-dev openmpi-bin \
    libgdal-dev gdal-bin \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Configurer gcc/gfortran
RUN update-alternatives --install /usr/bin/gfortran gfortran /usr/bin/gfortran-8 100 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 100 \
    && update-alternatives --set gfortran /usr/bin/gfortran-8 \
    && update-alternatives --set gcc /usr/bin/gcc-8

WORKDIR /opt/app

# 2. Installer les dépendances Python (dont mako et rasterio) AVANT de compiler XBeach
COPY requirements.txt .
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
RUN pip3 install --no-cache-dir -r requirements.txt

# 3. Cloner et compiler XBeach (qui a maintenant accès à mako)
WORKDIR /opt
RUN git clone https://github.com/openearth/xbeach.git
RUN sed -i 's/character(kind=c_char, len=\([^)]*\))/character(kind=c_char), dimension(\1)/g' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90 \
    && sed -i 's/dimension(20), dimension(maxrank)/dimension(20, maxrank)/' /opt/xbeach/src/xbeachlibrary/mnemoniciso.F90

WORKDIR /opt/xbeach
RUN ./autogen.sh && ./configure
RUN make clean && make
RUN mkdir -p /opt/xbeach_output && cp /opt/xbeach/src/xbeach/xbeach /opt/xbeach_output/

# 4. Finaliser l'application
WORKDIR /opt/app
COPY . /opt/app

EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]