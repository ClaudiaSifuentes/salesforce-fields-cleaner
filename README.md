# Limpiar JSON de metadata de campos

Este repositorio contiene utilidades para simplificar los JSONs de metadatos de campos (por ejemplo, los describe/export desde Salesforce), comparar versiones y producir reportes listos para revisión (JSON y CSV).

Resumen rápido
- Limpia describe JSONs y extrae los atributos relevantes por campo: `name`, `label`, `type`, `picklistValues`, `referenceTo`, `precision`, `scale`, `length`, `custom`.
- Compara una versión "baseline" contra una nueva versión simplificada y genera `report_objects/report-<Object>.json` con `summary`, `added_fields`, `removed_fields`, `modified_fields` y `text_report`.
- El pipeline (`pipeline_main.py`) ahora ejecuta automáticamente el agregador `scripts/export_reports_csv.py` al final para escribir dos CSVs: `report_objects/reports_summary.csv` (adds/removes) y `report_objects/reports_modified.csv` (modifications).

Propósito y flujo de trabajo (contexto de uso)
Este proyecto está pensado para soportar la gobernanza de campos en procesos de migración. La responsable de migración (tú) necesita mantener un consolidado en Excel con el catálogo de campos de los objetos del modelo, pero distintos equipos realizan cambios continuamente. Antes tenías que buscar manualmente en Object Manager y comparar, lo cual es lento y propenso a errores.

El flujo que automatiza el proyecto es:
- `incoming`: se descargan los describe JSONs desde el sandbox (por ejemplo mediante la herramienta `download_campos.py`).
- `simplified`: cada describe se normaliza y se extraen sólo los atributos relevantes en `simplified-<Object>.json`.
- `baseline`: existe una versión fija (estructurada) llamada `baseline-<Object>.json` que representa la última versión aprobada.
- `diff`: el sistema compara `baseline` vs `simplified` y genera `report_objects/report-<Object>.json` con los campos añadidos, eliminados y modificados (a nivel de atributo, incluyendo picklists y referencias).
- `CSV`: al final se agregan todos los `report-*.json` en dos CSVs pensados para Excel: uno con campos añadidos/eliminados (fácil de incorporar al consolidado) y otro con campos modificados (para revisar y actualizar el consolidado).
- `backup + promote`: una vez completada la comparación, la versión antigua de `baseline` se copia a `backup_objects/` con timestamp para mantener un histórico y el `simplified` recién generado se promueve a `baseline` para la siguiente iteración.

Gracias a este flujo puedes detectar automáticamente qué cambió (añadidos/removidos/modificados) y actualizar tu consolidado con filas CSV listas para Excel, reduciendo búsquedas manuales y errores.

Estructura esperada
- `scripts/`  utilidades:
  - `clean_campos.py`  convierte un JSON raw a su versión simplificada.
  - `diff_campos.py`  compara dos JSON simplificados y crea `report-<Object>.json`.
  - `export_reports_csv.py`  agrega todos los `report-*.json` en un par de CSVs legibles por Excel.
- `incoming_objects/`  archivos raw (`incoming-<object>.json`).
- `simplified_objects/`  simplificados (`simplified-<object>.json`).
- `baseline_objects/`  baseline para comparar (`baseline-<object>.json`).
- `report_objects/`  reportes JSON y CSVs.
- `backup_objects/`  backups automáticos del baseline con timestamp.

Uso básico (PowerShell)

1) Limpiar un JSON raw manualmente

```powershell
python .\scripts\clean_campos.py .\incoming_objects\incoming-Account.json .\simplified_objects\simplified-Account.json
```

2) Ejecutar pipeline completo (limpiar  diff  promover  exportar CSVs)

```powershell
python .\pipeline_main.py
```

Opciones útiles
- `--skip-download`: omite la etapa de descarga (útil si ya colocaste los `incoming-*.json`).
- `--map <path>`: usar un `objects_map.json` con la lista de objetos a procesar.
- `--report <path>`: cuando procesas un solo raw, escribir el JSON de reporte en la ruta indicada.
- `--keep-temp`: conservar archivos temporales.

Qué produce el pipeline
- Por objeto: `report_objects/report-<Object>.json` (detallado por campo).
- Al final: dos CSVs agregados en `report_objects/`:
  - `reports_summary.csv`  filas para `added` y `removed` y sus opciones de picklist.
  - `reports_modified.csv`  filas para `modified` atributos y filas por opción `picklist_value_modified`.

Notas sobre comparaciones de picklists
- La comparación de opciones de picklist se realiza por `label` (identidad basada en etiqueta). Si la `value` o `active` cambian pero la `label` es la misma, el dif mostrará `picklist_value_modified`.
- Si prefieres una comparación más tolerante (normalizar espacios, mayúsculas, puntuación), puedo añadir una normalización opcional en `diff_campos.py`.

CSV y revisión
- Los CSVs están pensados para revisión en Excel: una fila por cambio de campo o por opción de picklist afectada.
- `reports_modified.csv` incluye columnas para `old` y `new` (en algunos casos como picklist-option-modified se serializan pequeños JSONs con `label`, `value`, `active`).

Requisitos
- Python 3.8+ (solo librería estándar)

Ejemplos rápidos

```powershell
# Ejecutar pipeline (sin descargar)
python .\pipeline_main.py --skip-download --map objects_map.json

# Ejecutar limpieza manual para un objeto y luego diff manual
python .\scripts\clean_campos.py .\incoming_objects\incoming-Contact.json .\simplified_objects\simplified-Contact.json
python .\scripts\diff_campos.py .\baseline_objects\baseline-Contact.json .\simplified_objects\simplified-Contact.json .\report_objects\report-Contact.json

# Ejecutar el exportador directamente
python .\scripts\export_reports_csv.py --reports-dir .\report_objects --simplified-dir .\simplified_objects --baseline-dir .\baseline_objects --out .\report_objects\reports_summary.csv --out-modified .\report_objects\reports_modified.csv
```

¿Quieres que añada ejemplos de `objects_map.json`, instrucciones CI (GitHub Actions), o que active la normalización de labels por defecto?
