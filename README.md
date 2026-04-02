# EventoBot - Bot de Telegram para Eventos

Bot de Telegram para consulta de asistencia y datos de eventos en tiempo real.
Migrado de B4J a Python usando `python-telegram-bot`.

## Requisitos

- Python 3.11+
- Servidor RDC de B4J corriendo en `localhost:17179`
- Token de bot de Telegram

## Instalacion

```bash
pip install -r requirements.txt
```

## Configuracion

Editar `config.ini`:

```ini
[bot]
token = TU_TOKEN_AQUI
name = eventobot

[rdc]
host = localhost
port = 17179
```

O usar variables de entorno: `BOT_TOKEN`, `RDC_HOST`, `RDC_PORT`.

## Ejecutar

```bash
python main.py
```

## Comandos del Bot

| Comando | Descripcion |
|---------|-------------|
| `/start` | Iniciar el bot |
| `/funciones` | Listar funciones/eventos disponibles |
| `/totales` | Asistencia total con porcentajes |
| `/detalles` | Asistencia detallada por area/seccion |
| `/quien` | Quien escaneo en las ultimas 24 horas |
| `/boleta <codigo>` | Consultar boleta por codigo de barras |
| `/reportes` | Descargar reporte ZIP de la funcion |

## Estructura

```
eventobot/
  main.py              # Entry point
  config.ini           # Configuracion
  requirements.txt     # Dependencias
  bot/
    __init__.py
    handlers.py        # Handlers de Telegram
    i18n.py            # Traducciones ES/EN
    rdc_client.py      # Cliente RDC (protocolo B4X)
```
