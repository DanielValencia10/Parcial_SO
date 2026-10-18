# Simulación Paralela de Difusión de Calor

## Estructura


## Cómo ejecutarlo

Desde esta carpeta, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Interfaz gráfica:

```powershell
python -m gui.app
```

Análisis de rendimiento (guarda PNG y CSV en `graficas/`):

```powershell
python -m graficas
```

Carreras repetidas para el informe (guarda CSV y Excel en `resultados/`; el Excel necesita `pip install openpyxl`):

```powershell
python benchmark_carrera.py
```
