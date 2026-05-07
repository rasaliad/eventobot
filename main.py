"""EventoBot — Telegram bot for event attendance management."""

import configparser
import logging
import os
import sys

from telegram import BotCommand
from telegram.ext import Application

from bot.firebird_client import FirebirdClient
from bot.handlers import register_handlers
from bot.notifications import check_boleta_notifications, check_percentage_notifications
from bot.rdc_client import RDCClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
# Our modules log at INFO, everything else at WARNING
logging.getLogger("__main__").setLevel(logging.INFO)
logging.getLogger("bot").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    """Set bot commands menu after startup."""
    await app.bot.delete_my_commands()
    commands = [
        BotCommand("start", "Iniciar / Start"),
        BotCommand("totales", "Asistencia total / Total attendance"),
        BotCommand("detalles", "Asistencia detallada / Detailed attendance"),
        BotCommand("boleta", "Consultar boleta / Ticket lookup"),
        BotCommand("reportes", "Descargar reporte / Download report"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Bot commands registered")


def main():
    # Load config
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), "config.ini")

    if os.path.exists(config_path):
        config.read(config_path)

    token = os.environ.get("BOT_TOKEN") or config.get("bot", "token", fallback="")
    rdc_host = os.environ.get("RDC_HOST") or config.get("rdc", "host", fallback="localhost")
    rdc_port = int(os.environ.get("RDC_PORT") or config.get("rdc", "port", fallback="17179"))

    if not token or token == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN not configured. Set it in config.ini or as environment variable.")
        sys.exit(1)

    # Firebird direct connection (for notifications)
    fb_database = config.get("firebird", "database", fallback="")
    fb_user = config.get("firebird", "user", fallback="SYSDBA")
    fb_password = config.get("firebird", "password", fallback="masterkey")
    fb_client_library = config.get("firebird", "client_library", fallback="")

    # Notification settings
    alert_interval = int(config.get("notifications", "alert_interval_seconds", fallback="10"))
    pct_interval = int(config.get("notifications", "percentage_interval_seconds", fallback="120"))
    pct_step = int(config.get("notifications", "percentage_step", fallback="10"))

    rdc = RDCClient(host=rdc_host, port=rdc_port)

    app = Application.builder().token(token).post_init(post_init).build()
    app.bot_data["rdc"] = rdc
    app.bot_data["pct_step"] = pct_step

    # Setup Firebird if configured
    if fb_database:
        fb = FirebirdClient(database=fb_database, user=fb_user, password=fb_password,
                            client_library=fb_client_library)
        app.bot_data["firebird"] = fb
        logger.info("Firebird configured: %s", fb_database)

        # Background jobs — separate intervals
        job_queue = app.job_queue
        job_queue.run_repeating(
            check_boleta_notifications,
            interval=alert_interval,
            first=10,
            name="boleta_notifications",
        )
        job_queue.run_repeating(
            check_percentage_notifications,
            interval=pct_interval,
            first=60,
            name="percentage_notifications",
        )
        logger.info("Alerts every %ds, percentage every %ds (step %d%%)",
                    alert_interval, pct_interval, pct_step)
    else:
        logger.warning("Firebird not configured — notifications disabled")

    register_handlers(app)

    logger.info("Starting EventoBot (RDC: %s:%d)", rdc_host, rdc_port)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
