"""Bilingual translations (Spanish / English)."""

# Language codes: 1 = Spanish, 2 = English

_STRINGS = {
    "NoAutorizado": {
        1: "Hola {p1}, no estas autorizado al uso de este Bot, favor contactar a GAD Intermec para que activen tu usuario.",
        2: "Hi {p1}, you are not authorized to use this Bot, please contact GAD Intermec to activate your user.",
    },
    "NoExisteFuncion": {
        1: "No existen funciones",
        2: "There are no events",
    },
    "EnviarIdFuncion": {
        1: "<b>Favor enviar el ID de la funcion que desea seleccionar</b>",
        2: "<b>Please send the Event ID you want to select</b>",
    },
    "NoBoletaInvalido": {
        1: "Numero boleta erroneo",
        2: "Invalid Ticket number",
    },
    "NoFuncionSeleccionada": {
        1: "No hay una Funcion seleccionada",
        2: "There is no Event selected",
    },
    "BoletaNoExiste": {
        1: "Boleta: <b>{p1}</b> no existe para la funcion <b>{p2}</b>",
        2: "Ticket: <b>{p1}</b> does not exist for the event <b>{p2}</b>",
    },
    "Funcion:": {
        1: "Funcion: <b>{p1}</b>",
        2: "Event: <b>{p1}</b>",
    },
    "Boleta:": {
        1: "Boleta: <b>{p1}</b>",
        2: "Ticket: <b>{p1}</b>",
    },
    "Area1:": {
        1: "Area: <b>{p1}</b>",
        2: "Section: <b>{p1}</b>",
    },
    "Area2:": {
        1: "Area: <b>{p1}</b>/<b>{p2}</b>",
        2: "Section: <b>{p1}</b>/<b>{p2}</b>",
    },
    "Comentario:": {
        1: "Comentario:<b> {p1}</b>",
        2: "Comments:<b> {p1}</b>",
    },
    "FilaAsiento:": {
        1: "Fila: <b>{p1}</b> Asiento: <b>{p2}</b>",
        2: "Row: <b>{p1}</b> Seat: <b>{p2}</b>",
    },
    "Entro:": {
        1: "Fecha entrada: <b>{p1}</b>",
        2: "Entry Date: <b>{p1}</b>",
    },
    "NoEntro:": {
        1: "<b>NO HA ENTRADO</b>",
        2: "<b>HAS NOT ENTERED</b>",
    },
    "FuncionSel": {
        1: "Funcion: <b>{p1}</b> seleccionada",
        2: "Event: <b>{p1}</b> selected",
    },
    "FuncionNE": {
        1: "Funcion: <b>{p1}</b> no existe.",
        2: "Event: <b>{p1}</b> does not exist.",
    },
    "SelectButton": {
        1: "Seleccionar opcion de los botones mas abajo.",
        2: "Select option from the buttons below.",
    },
    "bFunciones": {1: "Funciones", 2: "Events"},
    "bAsistenciaTot": {1: "Totales", 2: "Totals"},
    "bAsistenciaDet": {1: "Detalles", 2: "Details"},
    "bBoletas": {1: "Reportes", 2: "Reports"},
    "gResumenEvento": {1: "Resumen", 2: "Summary"},
    "bQuien": {1: "Quien", 2: "Who"},
    "bBoleta": {1: "Boleta", 2: "Ticket"},
    "bGrafTot": {1: "Graf.Totales", 2: "Chart.Totals"},
    "bGrafDet": {1: "Graf.Detalles", 2: "Chart.Details"},
    "EstasAqui": {
        1: "Estas en la funcion <b>{p1}</b>",
        2: "You are in the event <b>{p1}</b>",
    },
    "Boletas": {1: "Reportes", 2: "Reports"},
    "ReporteFuncionSi": {
        1: "Reporte de la funcion <b>{p1}</b>",
        2: "Event <b>{p1}</b> report",
    },
    "ReporteFuncionNo": {
        1: "Reporte de la funcion <b>{p1}</b> aun no esta generado.",
        2: "Event <b>{p1}</b> report not yet generated",
    },
    "ImagenCargada": {1: "Imagen Cargada", 2: "Uploaded Image"},
    # Attendance headers
    "DescripcionHeader": {1: "Descripcion", 2: "Description"},
    "CantidadHeader": {1: "Cantidad", 2: "Quantity"},
    "AreaHeader": {1: "AREA", 2: "SECTION"},
    "DisponibleHeader": {1: "Disponible", 2: "Available"},
    "AsistenciaHeader": {1: "Asistencia", 2: "Assistance"},
    "RestanHeader": {1: "Restan", 2: "Remain"},
    # Who scanned
    "Uso24hTitle": {1: "USO ULTIMAS 24 HORAS", 2: "LAST 24 HOURS USAGE"},
    "UsuariosHeader": {1: "USUARIOS", 2: "USERS"},
    "UltimaVezHeader": {1: "Ultima Vez", 2: "Last Time"},
    "VecesHeader": {1: "Veces", 2: "Times"},
}


def t(key: str, lang: int = 1, p1: str = "", p2: str = "", p3: str = "") -> str:
    """Translate a key to the given language, substituting parameters."""
    strings = _STRINGS.get(key)
    if strings is None:
        return f"ERROR: {key}"
    template = strings.get(lang, strings.get(1, f"ERROR: {key}"))
    return template.format(p1=p1, p2=p2, p3=p3)
