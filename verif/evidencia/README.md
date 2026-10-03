# Evidencia de la versión demostrada

| Archivo | Qué es |
| :------ | :----- |
| `ultima_verificacion.txt` | Salida completa de `./verif/verify.sh` (construcción + 21 pruebas + demostración con el servicio real). Se sobrescribe cada vez que se ejecuta el script. |

La versión demostrada en la Technical Review 1 es la etiqueta `v0.1.0`.
Para reproducirla desde cero:

```bash
git clone https://github.com/Jorge42M/jobrunner-nexus.git
cd jobrunner-nexus
git checkout v0.1.0
./verif/verify.sh
```

Para conservar una corrida concreta (por ejemplo, la del día de la
presentación), se copia con fecha:

```bash
cp verif/evidencia/ultima_verificacion.txt verif/evidencia/verificacion_2026-10-06.txt
```
