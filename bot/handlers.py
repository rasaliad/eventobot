"""Telegram bot handlers — migrated from BotTelegram.b4j.

Uses a fixed ReplyKeyboardMarkup (like the original B4J bot) so buttons
stay pinned at the bottom.  Data and charts are sent as new messages.
"""

from datetime import datetime
import logging
import os

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .i18n import t
from .rdc_client import RDCClient

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rdc(context: ContextTypes.DEFAULT_TYPE) -> RDCClient:
    return context.bot_data["rdc"]


def _to_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _lang(context: ContextTypes.DEFAULT_TYPE) -> int:
    return context.user_data.get("idioma", 1)


def _rol(context: ContextTypes.DEFAULT_TYPE) -> int:
    return context.user_data.get("rol_id", 0)


# Button labels — used to match incoming text
_BTN_TOTALES = {"Totales", "Totals"}
_BTN_DETALLES = {"Detalles", "Details"}
_BTN_QUIEN = {"Quien", "Who"}
_BTN_BOLETA = {"Boleta", "Ticket"}
_BTN_REPORTES = {"Reportes", "Reports"}


def _keyboard(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    """Build the fixed reply keyboard. 'Quien' row only for rol_id=1."""
    lang = _lang(context)
    row1 = [
        KeyboardButton(t("bAsistenciaTot", lang)),
        KeyboardButton(t("bAsistenciaDet", lang)),
    ]
    row2 = []
    if _rol(context) == 1:
        row2.append(KeyboardButton(t("bQuien", lang)))
    row2.append(KeyboardButton(t("bBoleta", lang)))
    row2.append(KeyboardButton(t("bBoletas", lang)))
    return ReplyKeyboardMarkup([row1, row2], resize_keyboard=True)


# ── Auth ─────────────────────────────────────────────────────────────────────

async def _authenticate(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        *, skip_log: bool = False) -> bool:
    """Call sl_usuario on every interaction. Set skip_log=True to avoid
    incrementing the usage counter (used by 'Quien')."""
    user = update.effective_user
    rdc = _rdc(context)
    first = user.first_name or ""
    last = user.last_name or ""
    username = user.username or ""

    if not skip_log:
        text = (update.message.text if update.message else "") or ""
        try:
            await rdc.execute_batch([("ins_usuario_log", [str(user.id), text])])
        except Exception:
            logger.warning("Failed to log user command", exc_info=True)

    try:
        res = await rdc.execute_query("sl_usuario", [str(user.id), first, last, username])
    except Exception:
        logger.error("RDC connection error", exc_info=True)
        if update.message:
            await update.message.reply_text("Error connecting to server. Try again later.")
        return False

    if res is None or not res.rows:
        return False

    row = res.rows[0]
    logger.info("sl_usuario columns: %s", res.columns)
    logger.info("sl_usuario row (%d cols): %s", len(row), row)
    ud = context.user_data
    ud["funcion_id"] = _to_int(row[4])
    ud["botones_on"] = _to_int(row[5])
    ud["estatus"] = _to_int(row[6])
    ud["cliente_id"] = _to_int(row[7])
    ud["funcion_name"] = str(row[8] or "")
    ud["evento_id"] = _to_int(row[9])
    ud["idioma"] = _to_int(row[10]) or 1
    ud["opcion"] = _to_int(row[11])
    ud["rol_id"] = _to_int(row[14]) if len(row) > 14 else 0
    return True


async def _check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      *, skip_log: bool = False) -> bool:
    """Authenticate and send denial message if not authorized. Returns True if OK."""
    if not await _authenticate(update, context, skip_log=skip_log):
        name = update.effective_user.full_name or ""
        await update.message.reply_text(
            t("NoAutorizado", _lang(context), p1=name), parse_mode=ParseMode.HTML)
        return False
    if context.user_data.get("estatus") != 1:
        name = update.effective_user.full_name or ""
        await update.message.reply_text(
            t("NoAutorizado", _lang(context), p1=name), parse_mode=ParseMode.HTML)
        return False
    return True


async def _update_user(user_id, first, last, username, funcion_id, botones, opcion, context):
    try:
        await _rdc(context).execute_batch([
            ("upd_usuario", [str(user_id), first, last, username,
                             funcion_id, botones, opcion, 0])
        ])
    except Exception:
        logger.warning("Failed to update user", exc_info=True)


# ── /start ───────────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    fid = context.user_data.get("funcion_id", 0)
    if fid == 0:
        await _show_funciones(update, context)
    else:
        fname = context.user_data.get("funcion_name", "")
        await update.message.reply_text(
            t("EstasAqui", _lang(context), p1=fname),
            parse_mode=ParseMode.HTML,
            reply_markup=_keyboard(context),
        )


# ── Funciones (inline keyboard for selection only) ───────────────────────────

async def _show_funciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rdc = _rdc(context)
    user = update.effective_user
    lang = _lang(context)
    res = await rdc.execute_query("funciones", [str(user.id)])

    if res is None or not res.rows:
        await update.message.reply_text(t("NoExisteFuncion", lang), parse_mode=ParseMode.HTML)
        return

    buttons = []
    for row in res.rows:
        fid = row[0]
        fname = str(row[1])
        buttons.append([InlineKeyboardButton(f"{fid} - {fname}", callback_data=f"sel_fn_{fid}")])

    await update.message.reply_text(
        t("EnviarIdFuncion", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def select_function_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fn_id = query.data.replace("sel_fn_", "")
    user = update.effective_user
    lang = _lang(context)
    res = await _rdc(context).execute_query("funcion", [str(user.id), int(fn_id), lang])

    if res is None or not res.rows:
        await query.edit_message_text(t("FuncionNE", lang, p1=fn_id), parse_mode=ParseMode.HTML)
        return

    row = res.rows[0]
    new_fid = _to_int(row[0])
    new_fname = str(row[1])

    if new_fid > 0:
        context.user_data["funcion_id"] = new_fid
        context.user_data["funcion_name"] = new_fname
        context.user_data["opcion"] = 0
        await _update_user(
            user.id, user.first_name or "", user.last_name or "",
            user.username or "", new_fid, context.user_data.get("botones_on", 0), 0, context)
        await query.edit_message_text(
            t("FuncionSel", lang, p1=new_fname), parse_mode=ParseMode.HTML)
        # Send keyboard
        await query.message.reply_text(
            t("SelectButton", lang), parse_mode=ParseMode.HTML,
            reply_markup=_keyboard(context))
    else:
        msg = str(row[1]) if row[1] else t("FuncionNE", lang, p1=fn_id)
        await query.edit_message_text(msg, parse_mode=ParseMode.HTML)


# ── Totales ──────────────────────────────────────────────────────────────────

async def _asistencia_total(context: ContextTypes.DEFAULT_TYPE):
    """Returns text message."""
    rdc = _rdc(context)
    lang = _lang(context)
    fid = context.user_data.get("funcion_id", 0)
    fname = context.user_data.get("funcion_name", "")
    try:
        res = await rdc.execute_query("asistencia_total", [fid, lang])
    except Exception:
        logger.error("Error querying asistencia_total", exc_info=True)
        res = None

    if res is None or not res.rows:
        return t("NoExisteFuncion", lang)

    lines = [f"<b>{fname}</b>", "<pre>____________________________"]
    lines.append("Descripcion|Cantidad|   %   " if lang == 1 else "Description|Quantity|   %   ")
    lines.append("___________|________|_______")
    for row in res.rows:
        lines.append(f"{row[0]} |{row[1]} |{row[2]}")
    lines.append("___________|________|_______</pre>")

    return "\n".join(lines)


async def _send_totales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await _asistencia_total(context)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── Detalles ─────────────────────────────────────────────────────────────────

async def _asistencia_detalle(context: ContextTypes.DEFAULT_TYPE):
    """Returns text message."""
    rdc = _rdc(context)
    lang = _lang(context)
    fid = context.user_data.get("funcion_id", 0)
    fname = context.user_data.get("funcion_name", "")
    try:
        res = await rdc.execute_query("asistencia_detalle", [fid])
    except Exception:
        logger.error("Error querying asistencia_detalle", exc_info=True)
        res = None

    if res is None or not res.rows:
        return t("NoExisteFuncion", lang)

    lines = [f"<b>{fname}</b>", "<pre>"]
    if lang == 1:
        lines += ["__________________________________",
                   "             |Dispo |Asis  |      ",
                   "     AREA    |nible |tencia|Restan",
                   "_____________|______|______|______"]
    else:
        lines += ["__________________________________",
                   "             |Avai  |Assis |      ",
                   "   SECTION   |lable |tance |Remain",
                   "_____________|______|______|______"]

    for row in res.rows:
        area = str(row[1] or "").strip()
        if area == "TOTAL":
            lines.append("_____________|______|______|______")
        lines.append(str(row[0]))

    lines.append("_____________|______|______|______</pre>")

    return "\n".join(lines)


async def _send_detalles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await _asistencia_detalle(context)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── Quien ────────────────────────────────────────────────────────────────────

async def _send_quien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rdc = _rdc(context)
    lang = _lang(context)
    fid = context.user_data.get("funcion_id", 0)
    try:
        res = await rdc.execute_query("usuarioUso", [fid])
    except Exception:
        logger.error("Error querying usuarioUso", exc_info=True)
        res = None

    if res is None or not res.rows:
        await update.message.reply_text(t("NoExisteFuncion", lang), parse_mode=ParseMode.HTML)
        return

    lines = [f"<b>{t('Uso24hTitle', lang)}</b>", "<pre>"]
    if lang == 1:
        lines += ["____________________________________",
                   "               |              |     ",
                   "   USUARIOS    |  Ultima Vez  |Veces",
                   "_______________|______________|_____"]
    else:
        lines += ["____________________________________",
                   "               |              |     ",
                   "     USERS     |  Last Time   |Times",
                   "_______________|______________|_____"]

    for row in res.rows:
        lines.append(str(row[0]))
    lines.append("_______________|______________|_____</pre>")
    lines.append(f"<i>{datetime.now().strftime('%H:%M:%S')}</i>")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Boleta ───────────────────────────────────────────────────────────────────

async def _consultar_boleta(barcode: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    rdc = _rdc(context)
    lang = _lang(context)
    fid = context.user_data.get("funcion_id", 0)
    fname = context.user_data.get("funcion_name", "")

    if fid == 0:
        return t("NoFuncionSeleccionada", lang)
    if not barcode.isdigit():
        return t("NoBoletaInvalido", lang)

    try:
        res = await rdc.execute_query("boleta", [fid, barcode])
    except Exception:
        logger.error("Error querying boleta", exc_info=True)
        return "Error consulting ticket. Try again later."
    if res is None or not res.rows:
        return t("BoletaNoExiste", lang, p1=barcode, p2=fname)

    row = res.rows[0]
    lines = [t("Funcion:", lang, p1=fname), t("Boleta:", lang, p1=str(row[0]))]

    area_orig = str(row[3] or "")
    area_asig = str(row[4] or "")
    if area_orig == area_asig:
        lines.append(t("Area1:", lang, p1=area_orig))
    else:
        lines.append(t("Area2:", lang, p1=area_orig, p2=area_asig))

    comentario = str(row[5] or "").strip()
    if comentario:
        lines.append(t("Comentario:", lang, p1=comentario))

    asiento = _to_int(row[7])
    if asiento > 0:
        lines.append(t("FilaAsiento:", lang, p1=str(row[6]), p2=str(row[7])))

    if _to_int(row[8]) > 0:
        lines.append(t("Entro:", lang, p1=str(row[2])))
    else:
        lines.append(t("NoEntro:", lang))

    return "\n".join(lines)


# ── Reportes ─────────────────────────────────────────────────────────────────

async def _send_reportes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    fname = context.user_data.get("funcion_name", "")
    if not fname:
        await update.message.reply_text(t("NoFuncionSeleccionada", lang), parse_mode=ParseMode.HTML)
        return

    prefix = fname.split(" ")[0].strip() if " " in fname else fname.strip()
    zip_path = os.path.join("documents", prefix, f"{fname}.zip")

    if os.path.isfile(zip_path):
        await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
        await update.message.reply_document(
            document=open(zip_path, "rb"),
            caption=t("ReporteFuncionSi", lang, p1=fname),
            parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            t("ReporteFuncionNo", lang, p1=fname), parse_mode=ParseMode.HTML)


# ── Command handlers (from /command menu) ────────────────────────────────────

async def totales_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    await _send_totales(update, context)


async def detalles_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    await _send_detalles(update, context)


async def boleta_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    if context.args:
        msg = await _consultar_boleta(context.args[0], context)
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    else:
        context.user_data["opcion"] = 9
        lang = _lang(context)
        await update.message.reply_text(
            t("EnviarIdFuncion", lang).replace("funcion", "boleta").replace("Event ID", "Ticket barcode"),
            parse_mode=ParseMode.HTML)


async def reportes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    await _send_reportes(update, context)


# ── Text handler (keyboard buttons + barcode/function ID input) ──────────────

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # "Quien" button — skip_log to avoid incrementing counter
    is_quien = text in _BTN_QUIEN
    if is_quien:
        if not await _check_auth(update, context, skip_log=True):
            return
        if _rol(context) != 1:
            return
        await _send_quien(update, context)
        return

    # All other interactions: normal auth
    if not await _check_auth(update, context):
        return

    lang = _lang(context)
    fid = context.user_data.get("funcion_id", 0)

    # No function selected yet → show function list
    if fid == 0:
        await _show_funciones(update, context)
        return

    # Keyboard button: Totales
    if text in _BTN_TOTALES:
        await _send_totales(update, context)
        return

    # Keyboard button: Detalles
    if text in _BTN_DETALLES:
        await _send_detalles(update, context)
        return

    # Keyboard button: Boleta — enter barcode mode
    if text in _BTN_BOLETA:
        context.user_data["opcion"] = 9
        await update.message.reply_text(
            t("EnviarIdFuncion", lang).replace("funcion", "boleta").replace("Event ID", "Ticket barcode"),
            parse_mode=ParseMode.HTML)
        return

    # Keyboard button: Reportes
    if text in _BTN_REPORTES:
        await _send_reportes(update, context)
        return

    # Waiting for a barcode
    opcion = context.user_data.get("opcion", 0)
    if opcion == 9 and text.isdigit() and len(text) >= 14:
        msg = await _consultar_boleta(text, context)
        context.user_data["opcion"] = 0
        user = update.effective_user
        await _update_user(
            user.id, user.first_name or "", user.last_name or "",
            user.username or "", fid, context.user_data.get("botones_on", 0), 0, context)
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    # Numeric input < 5 chars = function ID
    if text.isdigit() and len(text) < 5:
        user = update.effective_user
        res = await _rdc(context).execute_query("funcion", [str(user.id), int(text), lang])
        if res and res.rows:
            row = res.rows[0]
            new_fid = _to_int(row[0])
            new_fname = str(row[1])
            if new_fid > 0:
                context.user_data["funcion_id"] = new_fid
                context.user_data["funcion_name"] = new_fname
                context.user_data["opcion"] = 0
                await _update_user(
                    user.id, user.first_name or "", user.last_name or "",
                    user.username or "", new_fid, context.user_data.get("botones_on", 0), 0, context)
                await update.message.reply_text(
                    t("FuncionSel", lang, p1=new_fname), parse_mode=ParseMode.HTML,
                    reply_markup=_keyboard(context))
                return
            else:
                await update.message.reply_text(
                    new_fname or t("FuncionNE", lang, p1=text), parse_mode=ParseMode.HTML)
                return

    # Barcode (>= 14 digits)
    if text.isdigit() and len(text) >= 14:
        msg = await _consultar_boleta(text, context)
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    # Default
    fname = context.user_data.get("funcion_name", "")
    await update.message.reply_text(
        t("EstasAqui", lang, p1=fname), parse_mode=ParseMode.HTML)


# ── Register handlers ────────────────────────────────────────────────────────

def register_handlers(app):
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("totales", totales_handler))
    app.add_handler(CommandHandler("detalles", detalles_handler))
    app.add_handler(CommandHandler("boleta", boleta_command_handler))
    app.add_handler(CommandHandler("reportes", reportes_handler))

    # Inline callback only for function selection
    app.add_handler(CallbackQueryHandler(select_function_callback, pattern=r"^sel_fn_"))

    # Text messages (keyboard buttons, barcodes, function IDs)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
