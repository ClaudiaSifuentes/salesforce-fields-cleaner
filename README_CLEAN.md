# Limpiar JSON de metadata de campos

Este pequeño script simplifica un JSON exportado de metadatos (por ejemplo, la respuesta SOAP/REST de Salesforce) quedándose solo con los campos y sus atributos relevantes.

Qué extrae por campo:
- `name` (API name)
- `label` (etiqueta)
- `type` (tipo de dato)
- `picklistValues` (lista de objetos con `label` y `value`)
- `referenceTo` (lista de objetos referenciados)

Uso (PowerShell - Windows):

```powershell
# Desde la carpeta que contiene este archivo y `campos_account.json`:
python .\clean_campos.py .\campos_account.json

# O especificando un archivo de salida:
python .\clean_campos.py .\campos_account.json .\campos_account_simplified.json
```

Salida:
- Archivo JSON con la estructura: `{ "fields": [ { name, label, type, picklistValues, referenceTo }, ... ] }`.

Notas:
- El script intenta encontrar `fields` en la raíz o en `result.fields` (basado en la extracción original).
- `picklistValues` se normaliza a una lista de objetos `{label,value}` cuando existan.

En este repositorio
- El `README.md` principal contiene la descripción del proyecto y ejemplos de uso.
- Usa `pipeline_main.py` para ejecutar el flujo: limpiar un JSON raw y compararlo automáticamente con el baseline `campos_account_simplified_v2.json`.

Si vas a subir esto a GitHub, te sugiero el siguiente repositorio:

- **Nombre:** `salesforce-fields-cleaner`
- **Descripción corta:** "Herramienta para simplificar y comparar metadatas de campos de Salesforce"

**Pipeline**

Se incluye un pipeline simple para procesar un JSON nuevo (sin limpiar), generar la versión simplificada y compararla contra un baseline.

Ejemplo (PowerShell):

```powershell
# Ejecuta pipeline: limpia el archivo nuevo, compara con el baseline y muestra el resultado
python .\pipeline_main.py .\nuevo_campos_raw.json .\campos_account_simplified_v2.json --report .\campos_diff_report.json

# Si no pasas el baseline, el pipeline intentará usar `campos_account_simplified_v2.json` o `campos_account.json` en la misma carpeta.

# Mantener archivos temporales (útil para depuración):
python .\pipeline_main.py .\nuevo_campos_raw.json --keep-temp
```

El pipeline utiliza `clean_campos.py` y `diff_campos.py` internamente. El reporte JSON (si lo pides) contiene `added_fields`, `removed_fields` y `modified_fields` con detalles a nivel de atributo y picklist.
