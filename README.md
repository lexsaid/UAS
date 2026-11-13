Aqui se explicaran los pasos para inicializar el proyecto (en codificacion)

1ro que nada tienen que instalar docker (https://docs.docker.com/desktop/setup/install/windows-install/)

tienen que tener python preferente de la 3.13 o superior

para ejecutar el docker y ver lo que estan haciendo graficamente es con: docker compose up --build
y para que deje de ejecutar es con CTRL+C

cuando le muevan a sus models.py (que es la base de datos) en la terminal escriben:
"python manage.py makemigrations" que este hace es cargar como en fila las ediciones de la base de datos,
despues ejecutan:
"python manage.py migrate" que este ya hace los cambios a la base de datos

--- Area del comedor ---

Entrar en http://localhost:8000/comedor/
Usuario del comedor (se crea solo con "migrate"): comedor / comedor123
Para cambiarlo, definir COMEDOR_USUARIO y COMEDOR_PASSWORD antes de correr "migrate".

El modelo Comida (comedor/models.py) tiene: nombre, ingredientes, precio e imagen. Las comidas se guardan en el menu hasta que se editen o eliminen manualmente.
Los ingredientes se guardan uno por linea en el campo "ingredientes"; para usarlos como lista:
comida.ingredientes_lista (ejemplo en comedor/templates/comedor/lista.html).
Los clientes se identifican como usuarios normales de Django; el comedor es el unico usuario con is_staff=True.

Para usar el mismo diseno en otras apps: {% extends "base.html" %} (templates/base.html y static/css/base.css).
Las fotos subidas se guardan en media/ (no se sube a git). Hace falta Pillow (ya esta en requirements.txt).

Pruebas: python manage.py test comedor

--- Área de alumnos ---

Login: http://localhost:8000/alumnos/login/
Registro: http://localhost:8000/alumnos/registro/

Incluye registro, inicio de sesión, menú, carrito y pedidos con comprobante e historial.
El menú usa las comidas del comedor. Solo se pueden confirmar pedidos dentro del horario establecido; fuera de ese horario se bloquea el botón de confirmación y el carrito se conserva.
Para ampliar o modificar ese horario, entra en Configuración desde el menú desplegable del comedor y guarda las nuevas horas de inicio y fin.
La revisión de pedidos y los motivos de rechazo quedan pendientes de integrar.

nota: ya hay un usuario registrado que servira como pruebas correo: santiago@gmai.com y contraseña: santiago

Para iniciar con Docker:

```powershell
docker compose up --build -d
docker compose exec web python manage.py migrate
```

Para arranques posteriores: `docker compose up -d`.
