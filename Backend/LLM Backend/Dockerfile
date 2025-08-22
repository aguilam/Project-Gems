FROM python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \ 
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libblas-dev \
    liblapack-dev \
    liblcms2-dev \
    libtiff5-dev \
    gfortran \
    libfreetype6-dev \
    antiword \
    unrtf \
    poppler-utils \
    tesseract-ocr \
    ffmpeg \
    xpdf \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]