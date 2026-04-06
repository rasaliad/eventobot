"""Direct Firebird connection for notifications (not via RDC)."""

import logging
from firebird.driver import connect

logger = logging.getLogger(__name__)


class FirebirdClient:
    """Synchronous Firebird client for notification queries."""

    def __init__(self, database: str, user: str = "SYSDBA", password: str = "masterkey"):
        self.database = database
        self.user = user
        self.password = password

    def _connect(self):
        return connect(self.database, user=self.user, password=self.password)

    # ── Boleta monitoring ────────────────────────────────────────────────

    def boleta_exists(self, funcion_id: int, boleta: str) -> dict | None:
        """Check if boleta exists. Returns {boleta, entro} or None."""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT BOLETA, ENTRO FROM BOLETAS WHERE FUNCION_ID = ? AND BOLETA = ?",
                (funcion_id, boleta))
            row = cur.fetchone()
            if row:
                return {"boleta": row[0], "entro": row[1]}
            return None
        finally:
            con.close()

    def add_monitor(self, usuario_id: str, boleta: str, funcion_id: int,
                    comentario: str = "") -> bool:
        """Add boleta to user's monitor list. Returns False if already exists."""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT 1 FROM USUARIO_BOLETA WHERE USUARIO_ID = ? AND BOLETA = ? AND FUNCION_ID = ?",
                (usuario_id, boleta, funcion_id))
            if cur.fetchone():
                return False
            cur.execute(
                "INSERT INTO USUARIO_BOLETA (USUARIO_ID, BOLETA, FUNCION_ID, COMENTARIO_PERSONAL) "
                "VALUES (?, ?, ?, ?)",
                (usuario_id, boleta, funcion_id, comentario or None))
            con.commit()
            return True
        finally:
            con.close()

    def remove_monitor(self, usuario_id: str, boleta: str, funcion_id: int) -> bool:
        """Remove boleta from user's monitor list."""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "DELETE FROM USUARIO_BOLETA WHERE USUARIO_ID = ? AND BOLETA = ? AND FUNCION_ID = ?",
                (usuario_id, boleta, funcion_id))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def list_monitors(self, usuario_id: str, funcion_id: int) -> list:
        """List boletas being monitored by user. Returns [(boleta, notificado, comentario_personal), ...]"""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT BOLETA, NOTIFICADO, COMENTARIO_PERSONAL FROM USUARIO_BOLETA "
                "WHERE USUARIO_ID = ? AND FUNCION_ID = ? ORDER BY FECHA_REGISTRO",
                (usuario_id, funcion_id))
            return cur.fetchall()
        finally:
            con.close()

    # ── Notifications polling ────────────────────────────────────────────

    def get_pending_boleta_notifications(self) -> dict:
        """Get boletas that entered and need notification.
        Returns {(boleta, funcion_id): [(usuario_id, comentario_personal), ...]} — grouped by boleta."""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT BOLETA, FUNCION_ID, USUARIO_ID, COMENTARIO_PERSONAL "
                "FROM USUARIO_BOLETA WHERE NOTIFICADO = 1 "
                "ORDER BY BOLETA, FUNCION_ID")
            grouped = {}
            for boleta, funcion_id, usuario_id, comentario in cur.fetchall():
                key = (boleta, funcion_id)
                grouped.setdefault(key, []).append((usuario_id, comentario))
            return grouped
        finally:
            con.close()

    def get_boleta_detail(self, funcion_id: int, boleta: str) -> dict | None:
        """Get full boleta info for notification message."""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT BOLETA, CAST(FECHA_LECTURA AS VARCHAR(25)) AS FECHA_LECTURA, "
                "AREA_ORIGINAL, ASIGNADA_A, COMENTARIO, FILA, NUMEROASIENTO, LECTOR_ID "
                "FROM BOLETAS WHERE FUNCION_ID = ? AND BOLETA = ?",
                (funcion_id, boleta))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "boleta": row[0],
                "fecha_lectura": row[1],
                "area_original": row[2],
                "asignada_a": row[3],
                "comentario": row[4],
                "fila": row[5],
                "asiento": row[6],
                "lector_id": row[7],
            }
        finally:
            con.close()

    def mark_notified_bulk(self, boleta: str, funcion_id: int, usuario_ids: list):
        """Mark boleta notification as sent for multiple users in one transaction."""
        con = self._connect()
        try:
            cur = con.cursor()
            for uid in usuario_ids:
                cur.execute(
                    "UPDATE USUARIO_BOLETA SET NOTIFICADO = 2 "
                    "WHERE USUARIO_ID = ? AND BOLETA = ? AND FUNCION_ID = ?",
                    (uid, boleta, funcion_id))
            con.commit()
        finally:
            con.close()

    # ── Percentage notifications ─────────────────────────────────────────

    def get_attendance_percentage(self, funcion_id: int) -> tuple:
        """Returns (disponible, entradas, percentage)."""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM BOLETAS WHERE FUNCION_ID = ?", (funcion_id,))
            disponible = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM BOLETAS WHERE FUNCION_ID = ? AND ENTRO = 1", (funcion_id,))
            entradas = cur.fetchone()[0]
            pct = (entradas * 100 / disponible) if disponible > 0 else 0
            return disponible, entradas, pct
        finally:
            con.close()

    def get_users_for_chart_notification(self, funcion_id: int) -> list:
        """Get users that should receive chart notifications.
        Returns [(usuario_id,), ...]"""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT USUARIO_ID FROM USUARIOS "
                "WHERE ESTATUS = 1 AND NOTIFICAR_GRAFICO = 1 AND FUNCION_ID = ?",
                (funcion_id,))
            return cur.fetchall()
        finally:
            con.close()

    def get_active_funciones(self) -> list:
        """Get active function IDs. Returns [(funcion_id, descripcion), ...]"""
        con = self._connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT FUNCION_ID, DESCRIPCION_FUNCION FROM FUNCIONES WHERE ESTATUS = 'A'")
            return cur.fetchall()
        finally:
            con.close()
