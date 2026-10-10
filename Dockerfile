FROM python:3.12-slim

# Tesseract: el programa que lee los textos de la pantalla (con idioma español)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# La bitácora se escribe en /srv/logs (se monta como carpeta del servidor)
RUN mkdir -p /srv/logs

EXPOSE 8000
CMD ["uvicorn", "app.main:crear_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
