# hagarramos una imagen base de python 3.13 slim para tener un entorno ligero
FROM python:3.13-slim

# Evitar que Python genere archivos .pyc y forzar que imprima los logs inmediatamente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Crear y establecer la carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiar primero el requirements.txt para aprovechar la caché de Docker
COPY requirements.txt /app/

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del proyecto a la carpeta /app
COPY . /app/

#  Exponer el puerto 8000 (el puerto por defecto de Django)
EXPOSE 8000

# 8. Comando para ejecutar las migraciones y levantar el servidor
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]