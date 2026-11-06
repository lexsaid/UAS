Aqui se explicaran los pasos para inicializar el proyecto (en codificacion)

1ro que nada tienen que instalar docker (https://docs.docker.com/desktop/setup/install/windows-install/)

tienen que tener python preferente de la 3.13 o superior

para ejecutar el docker y ver lo que estan haciendo graficamente es con: docker compose up --build
y para que deje de ejecutar es con CTRL+C

cuando le muevan a sus models.py (que es la base de datos) en la terminal escriben:
"python manage.py makemigrations" que este hace es cargar como en fila las ediciones de la base de datos,
despues ejecutan:
"python manage.py migrate" que este ya hace los cambios a la base de datos
