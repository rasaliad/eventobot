"""Background notification tasks."""

import logging

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def check_boleta_notifications(context: ContextTypes.DEFAULT_TYPE):
    """Poll for boletas that entered and notify users.
    Groups by boleta — one DB query per boleta, sends to all users watching it."""
    fb = context.bot_data.get("firebird")
    if not fb:
        return

    try:
        grouped = fb.get_pending_boleta_notifications()
    except Exception:
        logger.error("Error polling boleta notifications", exc_info=True)
        return

    if not grouped:
        return

    for (boleta, funcion_id), usuario_ids in grouped.items():
        # One query per boleta, shared across all users
        try:
            detail = fb.get_boleta_detail(funcion_id, boleta)
        except Exception:
            logger.warning("Error getting boleta detail for %s", boleta, exc_info=True)
            detail = None

        # Build base message (shared detail, one query)
        base_lines = []
        if detail:
            area_orig = str(detail.get("area_original") or "")
            area_asig = str(detail.get("asignada_a") or "")
            if area_orig and area_orig == area_asig:
                base_lines.append(f"Area: <b>{area_orig}</b>")
            elif area_orig and area_asig:
                base_lines.append(f"Area: <b>{area_orig}</b> / <b>{area_asig}</b>")
            elif area_orig:
                base_lines.append(f"Area: <b>{area_orig}</b>")

            comentario = str(detail.get("comentario") or "").strip()
            if comentario:
                base_lines.append(f"Comentario: <b>{comentario}</b>")

            fila = detail.get("fila")
            asiento = detail.get("asiento")
            if fila and asiento and int(asiento or 0) > 0:
                base_lines.append(f"Fila: <b>{fila}</b> Asiento: <b>{asiento}</b>")

            lector = detail.get("lector_id")
            if lector:
                base_lines.append(f"Lector: <b>{lector}</b>")

            fecha = str(detail.get("fecha_lectura") or "").strip()
            if fecha:
                base_lines.append(f"Entrada: <b>{fecha}</b>")

        base_detail = "\n".join(base_lines)

        # Send personalized message to each user (with their personal comment)
        notified_ids = []
        for usuario_id, comentario_personal in usuario_ids:
            if comentario_personal:
                header = f"\U0001f3ab <b>{comentario_personal}</b> ha entrado!"
            else:
                header = f"\U0001f3ab <b>Boleta {boleta}</b> ha entrado!"

            parts = [header]
            if base_detail:
                parts.append(base_detail)
            parts.append(f"Boleta: <code>{boleta}</code>")
            msg = "\n".join(parts)

            try:
                await context.bot.send_message(
                    chat_id=int(usuario_id), text=msg, parse_mode=ParseMode.HTML)
                notified_ids.append(usuario_id)
            except Exception:
                logger.warning("Failed to notify user %s for boleta %s",
                              usuario_id, boleta, exc_info=True)

        # Mark all notified in one transaction
        if notified_ids:
            try:
                fb.mark_notified_bulk(boleta, funcion_id, notified_ids)
                logger.info("Notified %d users for boleta %s", len(notified_ids), boleta)
            except Exception:
                logger.error("Error marking notified for boleta %s", boleta, exc_info=True)


async def check_percentage_notifications(context: ContextTypes.DEFAULT_TYPE):
    """Check if attendance crossed a percentage milestone and send chart."""
    fb = context.bot_data.get("firebird")
    rdc = context.bot_data.get("rdc")
    if not fb or not rdc:
        return

    step = context.bot_data.get("pct_step", 10)

    try:
        funciones = fb.get_active_funciones()
    except Exception:
        logger.error("Error getting active funciones", exc_info=True)
        return

    for funcion_id, descripcion in funciones:
        try:
            disponible, entradas, pct = fb.get_attendance_percentage(funcion_id)
        except Exception:
            logger.error("Error getting attendance for funcion %s", funcion_id, exc_info=True)
            continue

        if disponible == 0:
            continue

        # Track last notified milestone per function
        milestones = context.bot_data.setdefault("pct_milestones", {})
        last_milestone = milestones.get(funcion_id, 0)

        # Calculate current milestone (10, 20, 30, ...)
        current_milestone = int(pct // step) * step

        if current_milestone > last_milestone and current_milestone > 0:
            milestones[funcion_id] = current_milestone
            logger.info("Funcion %s reached %d%% (was %d%%)",
                       funcion_id, current_milestone, last_milestone)

            # Get users to notify
            try:
                users = fb.get_users_for_chart_notification(funcion_id)
            except Exception:
                logger.error("Error getting chart notification users", exc_info=True)
                continue

            if not users:
                continue

            # Generate chart
            chart_img = None
            try:
                from .charts import generate_chart
                lang = 1
                res_det = await rdc.execute_query("asistencia_detalle", [funcion_id])
                res_tot = await rdc.execute_query("asistencia_total", [funcion_id, lang])

                entered_val = 0
                remaining_val = 0
                if res_tot and res_tot.rows:
                    for row in res_tot.rows:
                        desc = str(row[0]).strip().upper()
                        val_str = str(row[1]).strip().replace(",", "")
                        try:
                            val = int(float(val_str))
                        except (ValueError, TypeError):
                            val = 0
                        if "ENTRADA" in desc or "ENTER" in desc:
                            entered_val = val
                        elif "RESTA" in desc or "REMAIN" in desc:
                            remaining_val = val

                if res_det and res_det.rows:
                    chart_img = generate_chart(
                        str(descripcion), res_det.rows, entered_val, remaining_val, lang)
            except Exception:
                logger.warning("Failed to generate chart for notification", exc_info=True)

            # Send to each user
            for (user_id,) in users:
                try:
                    milestone_msg = f"\U0001f4ca <b>{descripcion}</b> alcanzo <b>{current_milestone}%</b> de asistencia!"
                    if chart_img:
                        await context.bot.send_photo(
                            chat_id=int(user_id), photo=chart_img,
                            caption=milestone_msg, parse_mode=ParseMode.HTML,
                            read_timeout=60, write_timeout=60)
                    else:
                        await context.bot.send_message(
                            chat_id=int(user_id), text=milestone_msg,
                            parse_mode=ParseMode.HTML)
                    logger.info("Sent %d%% chart to user %s", current_milestone, user_id)
                except Exception:
                    logger.warning("Failed to send chart to user %s", user_id, exc_info=True)
