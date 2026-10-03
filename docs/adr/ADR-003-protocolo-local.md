# ADR-003: Comunicación local por socket Unix con JSON delimitado por líneas

- **Estado:** Aceptada para la operación local (la parte remota se decide en el Hito 3)
- **Fecha:** 2026-10-02
- **Issue:** #3

## Contexto

El cliente (`./nexus submit ...`) y el servicio (`./nexus serve`) son procesos
distintos y necesitan comunicarse (IPC). En el Hito 3 el mismo protocolo debe
funcionar por red, tolerando fragmentación y desconexiones.

## Alternativas

| Opción | A favor | En contra |
| :----- | :------ | :-------- |
| Que el cliente escriba directo en SQLite y el servicio lea | Sin protocolo | No hay respuesta inmediata ni validación central; no sirve para remoto. |
| Tuberías con nombre (FIFO) | Simples | Una sola dirección; difícil tener varios clientes y respuestas. |
| HTTP (`http.server`) | Conocido | Más pesado; se pide un protocolo propio. |
| **Socket Unix + una línea JSON por mensaje** | Bidireccional, varios clientes, permisos de archivo, se cambia a TCP casi sin tocar el formato | Hay que delimitar mensajes uno mismo. |

## Decisión

- Socket `AF_UNIX`/`SOCK_STREAM` en `nexus-data/nexus.sock` con permisos `0600`
  (solo el dueño puede conectarse).
- Cada mensaje es un objeto JSON en **una línea** terminada en `\n`. TCP y los
  sockets de flujo no respetan "mensajes": pueden entregar pedazos. El `\n`
  marca el final, así que el receptor lee hasta encontrarlo (`readline`).
- Límite de 64 KiB por mensaje; si no termina en `\n`, se considera incompleto.
- Respuesta siempre con `"ok": true/false`; los errores nunca tiran el servicio.
- Operaciones: `ping`, `submit`, `status`, `list`, `cancel`, `output`.

## Consecuencias

- Para el Hito 3 basta cambiar `AF_UNIX` por `AF_INET` y agregar autenticación.
- Una conexión por petición: simple, pero más costosa que mantenerla abierta.

## Riesgos

- Sin autenticación: hoy la protección es el permiso del archivo del socket.
  En red será obligatorio autenticar (Hito 3).

## Evidencia

- TC-014 (flujo completo por socket), TC-015 (JSON inválido no tumba el
  servicio): `verif/tests/test_service.py`.
