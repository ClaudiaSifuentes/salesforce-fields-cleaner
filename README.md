# Limpiar JSON de metadata de campos

Este repositorio contiene herramientas para simplificar JSONs de metadatos de campos (por ejemplo, exportaciones desde Salesforce) y comparar versiones para detectar cambios en campos, picklists y referencias.

Qué hace
- Extrae y normaliza los atributos relevantes por campo: `name`, `label`, `type`, `picklistValues`, `referenceTo`, `precision`, `scale`, `length`, `custom`, `inlineHelpText`, `soapType`.
- Compara dos versiones simplificadas y genera un reporte estructurado (JSON) que incluye además una versión legible en `text_report`.

Estructura del proyecto (carpetas y archivos esperados)
- `scripts/` — scripts de trabajo:
  - `clean_campos.py` — limpia un JSON raw y escribe el simplificado.
  - `diff_campos.py` — compara dos JSON simplificados y genera un reporte.
- `incoming_objects/` — archivos raw de entrada (`incoming-<object>.json`).
- `simplified_objects/` — resultados simplificados (`simplified-<object>.json`).
- `baseline_objects/` — baseline usados para comparar (`baseline-<object>.json`).
- `report_objects/` — reportes generados (`report-<object>.json`).
- `backup_objects/` — backups automáticos del baseline (`backup_YYYYMMDDThhmmss_baseline-<object>.json`).

Uso rápido (PowerShell)

1) Limpiar un JSON raw manualmente

```powershell
python .\scripts\clean_campos.py .\incoming_objects\incoming-account.json .\simplified_objects\simplified-account.json
```

2) Ejecutar pipeline (flujo completo)

El pipeline realiza el siguiente flujo por objeto:
- Determina el baseline a usar (`baseline_objects/baseline-<object>.json` si existe, o crea un baseline vacío si no hay ninguno).
- Limpia el `incoming` a un archivo temporal y ejecuta el diff contra el baseline.
- Escribe el resultado en `report_objects/report-<object>.json`. El JSON incluye `summary`, `added_fields`, `removed_fields`, `modified_fields` y la clave `text_report` con la versión legible.
- Si el diff indica que todo está correcto, el pipeline promueve el nuevo simplificado: hace un backup del baseline en `backup_objects/` y actualiza los archivos `baseline-...` y `simplified-...`.

Ejemplo (usar incoming por defecto):

```powershell
python .\pipeline_main.py
```

Ejemplo especificando un raw y ruta de reporte:

```powershell
python .\pipeline_main.py .\incoming_objects\otro_raw.json --report .\report_objects\report-account.json
```

Opciones útiles
- `--report <path>`: escribir el JSON de reporte en la ruta indicada (por defecto `report_objects/report-<object>.json`).
- `--keep-temp`: mantener archivos intermedios (por compatibilidad).

Salida del reporte
- El JSON generado contiene `summary`, `added_fields`, `removed_fields`, `modified_fields` y `text_report` (bloque de texto legible), para facilitar revisiones manuales.

Consideraciones
- Los backups del baseline se almacenan en `backup_objects/` con timestamp para preservar historial.
- Si trabajas en Windows/OneDrive ten en cuenta posibles bloqueos de archivos al hacer operaciones sobre `backup_objects/`.

Requisitos
- Python 3.8+ (solo librería estándar)

Ejemplos rápidos (PowerShell)

```powershell
# Limpiar manualmente
python .\scripts\clean_campos.py .\incoming_objects\incoming-account.json .\simplified_objects\simplified-account.json

# Ejecutar pipeline con incoming por defecto
python .\pipeline_main.py

# Ejecutar pipeline especificando raw y report
python .\pipeline_main.py .\incoming_objects\incoming-account.json --report .\report_objects\report-account.json
```

Si quieres que ajuste el nombre por defecto del reporte, agregue instrucciones para CI, o traduzca/expanda secciones, dímelo y lo actualizo.
