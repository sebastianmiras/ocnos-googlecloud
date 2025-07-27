# 1. Base image
FROM python:3.11-slim

# 2. Metadata
LABEL maintainer="sebsatian.miras@gcloud.ua.es"
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 3. Crea un directorio de trabajo
WORKDIR /app

# 4. Copia tus requirements y los instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia el resto del código
COPY . .

# 6. Expón el puerto
EXPOSE 8080

# 7. Comando de arranque
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
