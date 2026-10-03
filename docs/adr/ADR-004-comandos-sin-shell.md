# ADR-004: Ejecutar los comandos sin shell

- **Estado:** Aceptada
- **Fecha:** 2026-10-02
- **Issue:** #9

## Contexto

El usuario envía el comando como texto (`"ls -l /tmp"`). Hay que convertirlo en
un proceso. La forma más fácil, `shell=True`, le pasa el texto a `/bin/sh -c`,
que interpreta `;`, `|`, `>`, `$(...)`, etc.

## Alternativas

| Opción | A favor | En contra |
| :----- | :------ | :-------- |
| `shell=True` | Soporta tuberías y redirecciones | **Inyección de comandos**: `echo hola; rm -rf ~` ejecuta ambos. Además el PID es el de la shell, no el del programa. Errores de sintaxis se descubren tarde. |
| **`shlex.split` + `shell=False`** | Lo que se escribe es exactamente lo que se ejecuta; se valida antes de aceptar el trabajo; "comando no encontrado" se detecta en el `exec` (127) | No hay `|`, `>`, `&&` salvo pidiéndolos explícitamente con `sh -c '...'`. |

## Decisión

`runner.parse_command` usa `shlex.split` (mismas reglas de comillas que la
terminal) y rechaza: texto vacío, comillas sin cerrar, bytes nulos y comandos
de más de 4096 caracteres. Luego `Popen(args)` con `shell=False`.

## Consecuencias

- Comandos mal formados se rechazan **antes** de crear el trabajo y el servicio
  sigue funcionando (requisito "manejar comandos inválidos").
- Si se necesita una tubería, se envía de forma explícita:
  `./nexus submit sh -c 'ls | wc -l'`.

## Riesgos

- Aun sin shell, el trabajo corre con los permisos del usuario del servicio.
  Por eso el servicio nunca debe correr como root (mínimo privilegio).

## Evidencia

- TC-009 (comando inexistente → 127) y TC-010 (comandos inválidos rechazados):
  `verif/tests/test_runner.py`.
