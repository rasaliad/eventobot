"""
Client for B4J RDC (Remote Database Connector) server.

The RDC server uses B4XSerializator binary protocol over HTTP.
All payloads are zlib-compressed. Values are little-endian.
"""

import struct
import zlib
from typing import Any

import httpx

# ── B4X Serialization type tags ──────────────────────────────────────────────

T_NULL = 0x00
T_STRING = 0x01
T_SHORT = 0x02
T_INT = 0x03
T_LONG = 0x04
T_FLOAT = 0x05
T_DOUBLE = 0x06
T_BOOLEAN = 0x07
T_BYTE = 0x0A
T_CHAR = 0x0E
T_MAP = 0x14
T_LIST = 0x15
T_NSARRAY = 0x16
T_NSDATA = 0x17
T_TYPE = 0x18


# ── Explicit type wrappers (for when Python types are ambiguous) ─────────────

class B4XFloat:
    """Wraps a value to force serialization as B4X Float (32-bit)."""
    __slots__ = ("value",)
    def __init__(self, value: float):
        self.value = float(value)


class B4XArray:
    """Wraps a list to force serialization as B4X Object[] (T_NSARRAY)."""
    __slots__ = ("items",)
    def __init__(self, items: list):
        self.items = items


# ── Serializer ───────────────────────────────────────────────────────────────

def _write_map_contents(buf: bytearray, d: dict) -> None:
    """Write map count + key/value pairs WITHOUT the T_MAP tag byte."""
    buf.extend(struct.pack("<i", len(d)))
    for k, v in d.items():
        _write_value(buf, k)
        _write_value(buf, v)


def _write_value(buf: bytearray, value: Any) -> None:
    if value is None:
        buf.append(T_NULL)
    elif isinstance(value, B4XFloat):
        buf.append(T_FLOAT)
        buf.extend(struct.pack("<f", value.value))
    elif isinstance(value, B4XArray):
        buf.append(T_NSARRAY)
        buf.extend(struct.pack("<i", len(value.items)))
        for item in value.items:
            _write_value(buf, item)
    elif isinstance(value, B4XType):
        buf.append(T_TYPE)
        _write_value(buf, value.class_name)
        # writeType calls writeMap directly (no T_MAP tag), just count + entries
        _write_map_contents(buf, value.fields)
    elif isinstance(value, bool):
        buf.append(T_BOOLEAN)
        buf.append(1 if value else 0)
    elif isinstance(value, int):
        if -2147483648 <= value <= 2147483647:
            buf.append(T_INT)
            buf.extend(struct.pack("<i", value))
        else:
            buf.append(T_LONG)
            buf.extend(struct.pack("<q", value))
    elif isinstance(value, float):
        buf.append(T_DOUBLE)
        buf.extend(struct.pack("<d", value))
    elif isinstance(value, str):
        encoded = value.encode("utf-8")
        buf.append(T_STRING)
        buf.extend(struct.pack("<i", len(encoded)))
        buf.extend(encoded)
    elif isinstance(value, bytes):
        buf.append(T_NSDATA)
        buf.extend(struct.pack("<i", len(value)))
        buf.extend(value)
    elif isinstance(value, dict):
        buf.append(T_MAP)
        buf.extend(struct.pack("<i", len(value)))
        for k, v in value.items():
            _write_value(buf, k)
            _write_value(buf, v)
    elif isinstance(value, list):
        buf.append(T_LIST)
        buf.extend(struct.pack("<i", len(value)))
        for item in value:
            _write_value(buf, item)
    else:
        raise TypeError(f"Cannot serialize {type(value)}: {value!r}")


def serialize(value: Any) -> bytes:
    buf = bytearray()
    _write_value(buf, value)
    return zlib.compress(bytes(buf))


# ── Deserializer ─────────────────────────────────────────────────────────────

class B4XType:
    """Represents a B4X custom Type (struct)."""
    __slots__ = ("class_name", "fields")

    def __init__(self, class_name: str, fields: dict):
        self.class_name = class_name
        self.fields = fields

    def __repr__(self):
        return f"B4XType({self.class_name!r}, {self.fields!r})"

    def __getitem__(self, key):
        return self.fields[key]

    def get(self, key, default=None):
        return self.fields.get(key, default)


class _Reader:
    __slots__ = ("data", "pos")

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_bytes(self, n: int) -> bytes:
        result = self.data[self.pos : self.pos + n]
        self.pos += n
        return result

    def read_byte(self) -> int:
        val = self.data[self.pos]
        self.pos += 1
        return val

    def _read_map_contents(self) -> dict:
        """Read map count + key/value pairs WITHOUT consuming a tag byte."""
        count = struct.unpack("<i", self.read_bytes(4))[0]
        result = {}
        for _ in range(count):
            key = self.read_value()
            val = self.read_value()
            result[key] = val
        return result

    def read_value(self) -> Any:
        tag = self.read_byte()

        if tag == T_NULL:
            return None
        elif tag == T_STRING:
            length = struct.unpack("<i", self.read_bytes(4))[0]
            return self.read_bytes(length).decode("utf-8")
        elif tag == T_SHORT:
            return struct.unpack("<h", self.read_bytes(2))[0]
        elif tag == T_INT:
            return struct.unpack("<i", self.read_bytes(4))[0]
        elif tag == T_LONG:
            return struct.unpack("<q", self.read_bytes(8))[0]
        elif tag == T_FLOAT:
            return struct.unpack("<f", self.read_bytes(4))[0]
        elif tag == T_DOUBLE:
            return struct.unpack("<d", self.read_bytes(8))[0]
        elif tag == T_BOOLEAN:
            return self.read_byte() != 0
        elif tag == T_BYTE:
            return self.read_byte()
        elif tag == T_CHAR:
            return chr(struct.unpack("<H", self.read_bytes(2))[0])
        elif tag == T_MAP:
            count = struct.unpack("<i", self.read_bytes(4))[0]
            result = {}
            for _ in range(count):
                key = self.read_value()
                val = self.read_value()
                result[key] = val
            return result
        elif tag == T_LIST:
            count = struct.unpack("<i", self.read_bytes(4))[0]
            return [self.read_value() for _ in range(count)]
        elif tag == T_NSARRAY:
            count = struct.unpack("<i", self.read_bytes(4))[0]
            return [self.read_value() for _ in range(count)]
        elif tag == T_NSDATA:
            length = struct.unpack("<i", self.read_bytes(4))[0]
            return self.read_bytes(length)
        elif tag == T_TYPE:
            class_name = self.read_value()
            # readType calls readMap directly (no T_MAP tag), just count + entries
            fields = self._read_map_contents()
            return B4XType(class_name, fields)
        else:
            raise ValueError(f"Unknown B4X type tag: 0x{tag:02x} at pos {self.pos - 1}")


def deserialize(data: bytes) -> Any:
    raw = zlib.decompress(data)
    reader = _Reader(raw)
    return reader.read_value()


# ── DBResult helper ──────────────────────────────────────────────────────────

class DBResult:
    """Parsed result from an RDC query."""
    __slots__ = ("columns", "rows", "tag")

    def __init__(self, columns: dict, rows: list, tag=None):
        self.columns = columns  # {col_name: col_index}
        self.rows = rows        # list of lists
        self.tag = tag

    @classmethod
    def from_b4x(cls, obj) -> "DBResult":
        if obj is None:
            return None
        if isinstance(obj, B4XType):
            fields = obj.fields
        elif isinstance(obj, dict):
            fields = obj
        else:
            return None

        columns = fields.get("Columns", {})
        rows = fields.get("Rows", [])
        tag = fields.get("Tag")
        return cls(columns=columns, rows=rows, tag=tag)


# ── RDC Client ───────────────────────────────────────────────────────────────

class RDCClient:
    """HTTP client for B4J RDC server."""

    def __init__(self, host: str = "localhost", port: int = 17179):
        self.base_url = f"http://{host}:{port}/rdc"
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    def _build_command(self, name: str, params: list) -> dict:
        """Build an RDC command payload."""
        cmd = B4XType(
            "b4j.example.main$_dbcommand",
            {"IsInitialized": True, "Name": name, "Parameters": B4XArray(params)},
        )
        return {
            "command": cmd,
            "limit": 0,
            "version": B4XFloat(2.0),
        }

    async def execute_query(self, command_name: str, params: list) -> DBResult | None:
        """Execute a query and return a DBResult."""
        payload = self._build_command(command_name, params)
        body = serialize(payload)

        resp = await self._client.post(
            self.base_url,
            params={"method": "query2"},
            content=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

        result = deserialize(resp.content)
        return DBResult.from_b4x(result)

    async def execute_batch(self, commands: list[tuple[str, list]]) -> int:
        """Execute a batch of commands (INSERT/UPDATE). Returns affected count."""
        cmd_list = []
        for name, params in commands:
            cmd_list.append(
                B4XType(
                    "b4j.example.main$_dbcommand",
                    {"IsInitialized": True, "Name": name, "Parameters": B4XArray(params)},
                )
            )

        payload = {
            "commands": cmd_list,
            "version": B4XFloat(2.0),
        }
        body = serialize(payload)

        resp = await self._client.post(
            self.base_url,
            params={"method": "batch2"},
            content=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

        result = deserialize(resp.content)
        if isinstance(result, (int, float)):
            return int(result)
        return 0
