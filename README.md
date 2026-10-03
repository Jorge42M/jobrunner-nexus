# Nexus (JobRunner)

Nexus es un servicio ligero para Linux que **recibe comandos, los ejecuta como
trabajos en procesos separados, supervisa su estado y permite cancelarlos**.
Está escrito en Python 3 usando solo la biblioteca estándar y guarda todo en
SQLite.

> **Versión actual:** `v0.1.0` — Avance 1 (Hito 1): núcleo local.
> La operación remota (LAN/VPN) llegará en el Hito 3.

## ¿Qué puede hacer hoy?

| Funcionalidad                              | Comando                      |
| :----------------------------------------- | :--------------------------- |
| Enviar un trabajo y obtener un ID único    | `./nexus submit sleep 10`    |
| Ejecutarlo como proceso separado           | (automático, con `fork/exec`) |
| Consultar su estado y su bitácora          | `./nexus status 1`           |
| Listar trabajos (todos o por estado)       | `./nexus list --state RUNNING` |
| Solicitar su cancelación (SIGTERM→SIGKILL) | `./nexus cancel 1`           |
| Obtener su código de salida                | `./nexus wait 1`             |
| Ver su salida estándar y de error          | `./nexus output 1`           |
| Rechazar comandos inválidos sin caerse     | `./nexus submit "echo 'mal"` |

## Requisitos

- Linux (probado en Ubuntu sobre WSL2).
- Python 3.8 o superior (`python3 --version`).
- Git.
- **No** hace falta instalar paquetes extra ni ser root.

## Construcción

```bash
git clone https://github.com/Jorge42M/jobrunner-nexus.git
cd jobrunner-nexus
./build.sh
```

`build.sh` revisa la versión de Python, que exista `sqlite3` y compila todo
`src/` tratando las advertencias como errores.

## Ejecución

Se usan **dos terminales**.

Terminal 1 — el servicio (se queda corriendo):

```bash
./nexus serve
```

Terminal 2 — el cliente:

```bash
./nexus submit echo hola mundo   # -> Trabajo enviado. ID: 1
./nexus wait 1                   # -> SUCCEEDED, código de salida 0
./nexus output 1                 # -> hola mundo
./nexus submit sleep 60          # -> ID: 2
./nexus cancel 2                 # -> se envía SIGTERM
./nexus list                     # tabla con todos los trabajos
./nexus status 2                 # detalle + bitácora de eventos
```

Para detener el servicio: `Ctrl+C` en la terminal 1 (envía `SIGINT`).

Opciones útiles de `serve`: `--max-concurrent N` (trabajos a la vez, por defecto
2) y `--kill-grace S` (segundos entre `SIGTERM` y `SIGKILL`, por defecto 3).
Los datos se guardan en `nexus-data/` (base de datos, socket y salidas).

## Pruebas y verificación

```bash
./verif/verify.sh
```

Construye, ejecuta las 21 pruebas automatizadas y hace una demostración real
con el servicio. La salida se guarda en `verif/evidencia/ultima_verificacion.txt`.

## Estructura del repositorio

```
jobrunner-nexus/
├── nexus                  # atajo para ejecutar el programa (./nexus ...)
├── build.sh               # construcción
├── src/nexus/             # código fuente
│   ├── cli.py             #   cliente de línea de comandos
│   ├── protocol.py        #   mensajes JSON por socket Unix
│   ├── server.py          #   servicio: socket, señales, despacho
│   ├── runner.py          #   procesos hijos, cola, cancelación
│   ├── store.py           #   persistencia SQLite + bitácora
│   └── states.py          #   modelo de estados
├── verif/
│   ├── verify.sh          # script de verificación (un solo comando)
│   ├── tests/             # pruebas automatizadas (unittest)
│   ├── casos_de_prueba.md
│   ├── matriz_trazabilidad.md
│   └── evidencia/         # salidas guardadas de la verificación
├── docs/
│   ├── arquitectura.md
│   ├── modelo_estados.md
│   ├── procesos_senales_codigos.md
│   ├── adr/               # decisiones de arquitectura (ADR-001 a ADR-004)
│   └── registro_uso_ia.md
├── project-management/
│   ├── matriz_de_roles.md
│   └── cronograma_riesgos.md
└── CHANGELOG.md
```

## Documentación

- [Arquitectura inicial](docs/arquitectura.md)
- [Modelo de estados](docs/modelo_estados.md)
- [Procesos, señales y códigos de salida](docs/procesos_senales_codigos.md)
- [Decisiones de arquitectura (ADR)](docs/adr/README.md)
- [Casos de prueba](verif/casos_de_prueba.md) y [matriz de trazabilidad](verif/matriz_trazabilidad.md)
- [Registro de uso de IA](docs/registro_uso_ia.md)
- [Matriz de roles](project-management/matriz_de_roles.md) y [cronograma y riesgos](project-management/cronograma_riesgos.md)

## Integrantes

- **Desarrollador principal:** Jorge Iván Mariscal Oliva (Ingeniería en Computación)
- **Contacto:** jorge.mariscal4235@alumnos.udg.mx
- **Modalidad:** trabajo individual

## Estado del proyecto

- **Fase actual:** Hito 1 — núcleo local (v0.1.0).
- **Siguiente:** Hito 2 — concurrencia y persistencia atómica bajo carga.
- Seguimiento en los [Issues](https://github.com/Jorge42M/jobrunner-nexus/issues).
