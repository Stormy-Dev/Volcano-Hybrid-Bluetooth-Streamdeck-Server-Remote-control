# volcano_server.py
# Hält eine dauerhafte Bluetooth-Verbindung zum Volcano Hybrid und nimmt
# Befehle über http://127.0.0.1:8765/<befehl> entgegen (nur lokal erreichbar).
#
# Befehle:
#   /heat-on  /heat-off  /heat-toggle
#   /pump-on  /pump-off  /pump-toggle
#   /pump-for/30          Pumpe 30 Sekunden an, dann automatisch aus
#   /temp/185             Zieltemperatur setzen (40–230 °C)
#   /temp-up  /temp-down  Zieltemperatur um TEMP_STEP ändern (oder /temp-up/10)
#   /all-off              Heizung und Pumpe aus
#   /status               aktuellen Zustand als JSON

import asyncio
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlsplit

from storzandbickel_ble import StorzBickelClient

# ---------- Einstellungen ----------
HOST = "127.0.0.1"
PORT = 8765
DEVICE_NAME = "S&B VOLCANO"
TEMP_STEP = 5            # °C pro Druck bei temp-up / temp-down
PUMP_AUTO_OFF = 90       # Sekunden; Pumpe geht spätestens danach aus (None = nie)
PUMP_FOR_MAX = 120       # Obergrenze für /pump-for/<sekunden>
RECONNECT_EVERY = 20     # Sekunden zwischen Verbindungs-Checks im Hintergrund
# -----------------------------------

LOG_FILE = Path(__file__).with_name("volcano_server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
    + ([logging.StreamHandler()] if sys.stderr else []),  # pyw hat keine Konsole
)
log = logging.getLogger("volcano")


class Volcano:
    def __init__(self) -> None:
        self.client = StorzBickelClient()
        self.dev = None
        self.lock = asyncio.Lock()
        self.pump_timer: asyncio.Task | None = None

    async def _ensure(self):
        if self.dev is not None and self.dev.is_connected:
            return self.dev
        if self.dev is not None:
            try:
                await self.dev.disconnect()
            except Exception:
                pass
            self.dev = None
        log.info("Verbinde mit %s ...", DEVICE_NAME)
        self.dev = await self.client.connect_by_name(DEVICE_NAME)
        await self.dev.update_state()
        log.info("Verbunden.")
        return self.dev

    async def run(self, fn):
        """Führt fn(device) aus; bei Fehler einmal neu verbinden und wiederholen."""
        async with self.lock:
            for attempt in (1, 2):
                try:
                    dev = await self._ensure()
                    return await fn(dev)
                except Exception as e:
                    log.warning("Versuch %d fehlgeschlagen: %r", attempt, e)
                    if self.dev is not None:
                        try:
                            await self.dev.disconnect()
                        except Exception:
                            pass
                    self.dev = None
                    if attempt == 2:
                        raise

    # ---------- Pumpe ----------
    def _cancel_pump_timer(self) -> None:
        if self.pump_timer and not self.pump_timer.done():
            self.pump_timer.cancel()
        self.pump_timer = None

    def _start_pump_timer(self, seconds: float | None) -> None:
        self._cancel_pump_timer()
        if seconds:
            self.pump_timer = asyncio.create_task(self._pump_off_later(seconds))

    async def _pump_off_later(self, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
            await self.run(lambda d: d.turn_pump_off())
            log.info("Pumpe nach %.0f s automatisch aus.", seconds)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Automatisches Pumpe-aus fehlgeschlagen")

    async def pump_on(self, seconds: float | None = PUMP_AUTO_OFF) -> None:
        await self.run(lambda d: d.turn_pump_on())
        self._start_pump_timer(seconds)

    async def pump_off(self) -> None:
        self._cancel_pump_timer()
        await self.run(lambda d: d.turn_pump_off())

    async def pump_toggle(self) -> None:
        async def is_on(d):
            return d.state.pump_on
        await (self.pump_off() if await self.run(is_on) else self.pump_on())

    # ---------- Heizung ----------
    async def heat_toggle(self) -> None:
        async def f(d):
            await (d.turn_heater_off() if d.state.heater_on else d.turn_heater_on())
        await self.run(f)

    async def temp_set(self, value: float) -> None:
        value = max(40.0, min(230.0, value))
        await self.run(lambda d: d.set_target_temperature(value))

    async def temp_delta(self, delta: float) -> None:
        async def f(d):
            t = d.state.target_temperature
            if t is None:
                await d.update_state()
                t = d.state.target_temperature or 180.0
            await d.set_target_temperature(max(40.0, min(230.0, t + delta)))
        await self.run(f)

    async def all_off(self) -> None:
        self._cancel_pump_timer()
        async def f(d):
            await d.turn_pump_off()
            await d.turn_heater_off()
        await self.run(f)

    async def status(self) -> dict:
        async def f(d):
            s = d.state
            return {
                "ok": True,
                "connected": d.is_connected,
                "heater_on": s.heater_on,
                "pump_on": s.pump_on,
                "current_temperature": s.current_temperature,
                "target_temperature": s.target_temperature,
            }
        return await self.run(f)

    async def keepalive(self) -> None:
        """Hält die Verbindung im Hintergrund aufrecht, damit Tasten sofort reagieren."""
        while True:
            try:
                async with self.lock:
                    await self._ensure()
            except Exception as e:
                log.info("Volcano nicht erreichbar (%r) – neuer Versuch später.", e)
                self.dev = None
            await asyncio.sleep(RECONNECT_EVERY)


VOLCANO: Volcano


def _num(arg: str | None, default: float) -> float:
    return float(arg.replace(",", ".")) if arg else default


async def dispatch(path: str) -> tuple[int, dict]:
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return 200, {"ok": True, "info": "Volcano-Server läuft. Siehe Kopf von volcano_server.py für Befehle."}
    cmd, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else None)
    v = VOLCANO

    match cmd:
        case "heat-on":
            await v.run(lambda d: d.turn_heater_on())
        case "heat-off":
            await v.run(lambda d: d.turn_heater_off())
        case "heat-toggle":
            await v.heat_toggle()
        case "pump-on":
            await v.pump_on()
        case "pump-off":
            await v.pump_off()
        case "pump-toggle":
            await v.pump_toggle()
        case "pump-for":
            secs = max(1.0, min(_num(arg, 30), PUMP_FOR_MAX))
            await v.pump_on(secs)
        case "temp":
            if arg is None:
                return 400, {"ok": False, "error": "Temperatur fehlt, z. B. /temp/185"}
            await v.temp_set(_num(arg, 180))
        case "temp-up":
            await v.temp_delta(_num(arg, TEMP_STEP))
        case "temp-down":
            await v.temp_delta(-_num(arg, TEMP_STEP))
        case "all-off":
            await v.all_off()
        case "status":
            pass
        case "favicon.ico":
            return 404, {"ok": False}
        case _:
            return 404, {"ok": False, "error": f"Unbekannter Befehl: {cmd}"}

    log.info("Befehl ausgeführt: %s", path)
    return 200, await v.status()


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), 5)
        while True:  # Header überspringen
            line = await asyncio.wait_for(reader.readline(), 5)
            if line in (b"\r\n", b"\n", b""):
                break
        fields = request_line.decode(errors="ignore").split()
        path = urlsplit(fields[1]).path if len(fields) >= 2 else "/"
        status, body = await dispatch(path)
    except Exception as e:
        log.exception("Fehler bei Anfrage")
        status, body = 500, {"ok": False, "error": repr(e)}

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    head = (
        f"HTTP/1.1 {status} {'OK' if status == 200 else 'Error'}\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(data)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    try:
        writer.write(head + data)
        await writer.drain()
    finally:
        writer.close()


async def main() -> None:
    global VOLCANO
    VOLCANO = Volcano()
    server = await asyncio.start_server(handle, HOST, PORT)
    log.info("Volcano-Server läuft auf http://%s:%d", HOST, PORT)
    asyncio.create_task(VOLCANO.keepalive())
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
