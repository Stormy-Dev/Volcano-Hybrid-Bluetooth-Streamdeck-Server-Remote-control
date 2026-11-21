# volcano_server.py
# Keeps a persistent Bluetooth connection to the Volcano Hybrid and accepts
# commands at http://127.0.0.1:8765/<command> (only reachable locally).
#
# Commands:
#   /heat-on  /heat-off  /heat-toggle
#   /pump-on  /pump-off  /pump-toggle
#   /pump-for/30          run the pump for 30 seconds, then switch it off
#   /temp/185             set the target temperature (40–230 °C)
#   /temp-up  /temp-down  change the target temperature by TEMP_STEP (or /temp-up/10)
#   /all-off              heater and pump off
#   /status               current state as JSON

import asyncio
import json
import logging
import math
import sys
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from storzandbickel_ble import StorzBickelClient

# ---------- Settings ----------
HOST = "127.0.0.1"
PORT = 8765
DEVICE_NAME = "S&B VOLCANO"
TEMP_STEP = 5            # °C per press for temp-up / temp-down
PUMP_AUTO_OFF = 90       # seconds; pump is switched off after this at the latest (None = never)
PUMP_FOR_MAX = 120       # upper limit for /pump-for/<seconds>
RECONNECT_EVERY = 20     # seconds between connection checks in the background
CONNECT_TIMEOUT = 20     # seconds before a connection attempt is given up
COMMAND_TIMEOUT = 10     # seconds before a single Bluetooth command is given up
BLOCK_BROWSER_REQUESTS = True  # reject requests that a website triggered in your browser
# ------------------------------

TEMP_MIN, TEMP_MAX = 40.0, 230.0
PUMP_OFF_RETRIES = 10    # attempts for the automatic pump-off if the connection is down
MAX_HEADERS = 100

# Host and Origin values a legitimate local request can carry.
ALLOWED_HOSTS = {f"{h}:{PORT}" for h in {HOST, "127.0.0.1", "localhost"}}
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}

LOG_FILE = Path(__file__).with_name("volcano_server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
    + ([logging.StreamHandler()] if sys.stderr else []),  # pythonw has no console
)
log = logging.getLogger("volcano")


class HttpError(Exception):
    status = 500


class BadRequest(HttpError):
    status = 400


class Forbidden(HttpError):
    status = 403


class NotConnected(HttpError):
    status = 503

    def __init__(self) -> None:
        super().__init__("Volcano is not connected")


def _clamp_temp(value: float) -> float:
    return max(TEMP_MIN, min(TEMP_MAX, value))


class Volcano:
    def __init__(self) -> None:
        self.client = StorzBickelClient()
        self.dev = None
        self.lock = asyncio.Lock()
        self.pump_timer: asyncio.Task | None = None
        self._wake = asyncio.Event()  # tells keepalive() to reconnect right away

    # ---------- Connection ----------
    async def _connect(self) -> None:
        log.info("Connecting to %s ...", DEVICE_NAME)
        dev = await asyncio.wait_for(
            self.client.connect_by_name(DEVICE_NAME), CONNECT_TIMEOUT
        )
        if dev is None:
            raise ConnectionError("device not found")
        try:
            await asyncio.wait_for(dev.update_state(), COMMAND_TIMEOUT)
        except BaseException:
            await self._drop(dev)
            raise
        self.dev = dev
        log.info("Connected.")

    async def _drop(self, dev) -> None:
        if self.dev is dev:
            self.dev = None
        try:
            await asyncio.wait_for(dev.disconnect(), 5)
        except Exception:
            pass

    def _connected_dev(self):
        dev = self.dev
        if dev is None or not dev.is_connected:
            self._wake.set()
            raise NotConnected()
        return dev

    async def run(self, fn):
        """Runs fn(device). Fails immediately if the Volcano is not connected;
        reconnecting is left to keepalive() so button presses never pile up."""
        self._connected_dev()
        async with self.lock:
            dev = self._connected_dev()  # may have changed while waiting for the lock
            try:
                return await asyncio.wait_for(fn(dev), COMMAND_TIMEOUT)
            except Exception as e:
                log.warning("Command failed, dropping connection: %r", e)
                await self._drop(dev)
                self._wake.set()
                raise

    async def keepalive(self) -> None:
        """Keeps the connection up in the background so buttons respond instantly."""
        while True:
            self._wake.clear()
            dev = self.dev
            if dev is not None and not dev.is_connected:
                log.info("Connection lost.")
                await self._drop(dev)
            if self.dev is None:
                try:
                    await self._connect()
                except Exception as e:
                    log.info("Volcano not reachable (%r), retrying later.", e)
            try:
                await asyncio.wait_for(self._wake.wait(), RECONNECT_EVERY)
            except asyncio.TimeoutError:
                pass

    # ---------- Pump ----------
    def _cancel_pump_timer(self) -> None:
        if self.pump_timer and not self.pump_timer.done():
            self.pump_timer.cancel()
        self.pump_timer = None

    def _start_pump_timer(self, seconds: float | None) -> None:
        self._cancel_pump_timer()
        if seconds:
            self.pump_timer = asyncio.create_task(self._pump_off_later(seconds))

    async def _pump_off_later(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
        for _ in range(PUMP_OFF_RETRIES):
            try:
                await self.run(lambda d: d.turn_pump_off())
                log.info("Pump switched off automatically after %.0f s.", seconds)
                return
            except Exception as e:
                log.warning("Automatic pump-off failed (%r), retrying.", e)
                await asyncio.sleep(3)
        log.error("Automatic pump-off gave up. The pump may still be running.")

    async def pump_on(self, seconds: float | None = PUMP_AUTO_OFF) -> None:
        await self.run(lambda d: d.turn_pump_on())
        self._start_pump_timer(seconds)

    async def pump_off(self) -> None:
        self._cancel_pump_timer()
        await self.run(lambda d: d.turn_pump_off())

    async def pump_toggle(self) -> None:
        async def is_on(d):
            await d.update_state()  # the pump may have been switched on the device itself
            return d.state.pump_on
        await (self.pump_off() if await self.run(is_on) else self.pump_on())

    # ---------- Heater ----------
    async def heat_toggle(self) -> None:
        async def f(d):
            await d.update_state()
            await (d.turn_heater_off() if d.state.heater_on else d.turn_heater_on())
        await self.run(f)

    async def temp_set(self, value: float) -> None:
        value = _clamp_temp(value)
        await self.run(lambda d: d.set_target_temperature(value))

    async def temp_delta(self, delta: float) -> None:
        async def f(d):
            await d.update_state()
            t = d.state.target_temperature
            if t is None:
                t = 180.0
            await d.set_target_temperature(_clamp_temp(t + delta))
        await self.run(f)

    async def all_off(self) -> None:
        self._cancel_pump_timer()
        async def f(d):
            await d.turn_pump_off()
            await d.turn_heater_off()
        await self.run(f)

    async def status(self) -> dict:
        async def f(d):
            await d.update_state()
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


VOLCANO: Volcano


def _num(arg: str | None, default: float) -> float:
    if arg is None:
        return default
    try:
        value = float(arg.replace(",", "."))
    except ValueError:
        raise BadRequest(f"Not a number: {arg}") from None
    if not math.isfinite(value):
        raise BadRequest(f"Not a usable number: {arg}")
    return value


def check_request(headers: dict[str, str]) -> None:
    """Rejects requests that a website triggered in a browser on this machine.
    Binding to 127.0.0.1 alone does not prevent those. Tools like curl or the
    Stream Deck send none of the browser headers checked here."""
    if not BLOCK_BROWSER_REQUESTS:
        return
    host = headers.get("host")
    if host is not None and host.lower() not in ALLOWED_HOSTS:
        raise Forbidden(f"Unexpected Host header: {host}")
    origin = headers.get("origin")
    if origin is not None and origin.lower() not in ALLOWED_ORIGINS:
        raise Forbidden(f"Cross-origin request from {origin}")
    site = headers.get("sec-fetch-site")
    if site is not None and site.lower() not in ("none", "same-origin"):
        raise Forbidden(f"Cross-site browser request ({site})")


async def dispatch(path: str) -> tuple[int, dict]:
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return 200, {"ok": True, "info": "Volcano server is running. See the top of volcano_server.py for commands."}
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
                raise BadRequest("Temperature missing, e.g. /temp/185")
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
            return 404, {"ok": False, "error": f"Unknown command: {cmd}"}

    log.info("Command executed: %s", path)
    return 200, await v.status()


async def read_request(reader: asyncio.StreamReader) -> tuple[str, dict[str, str]]:
    request_line = await asyncio.wait_for(reader.readline(), 5)
    headers: dict[str, str] = {}
    for _ in range(MAX_HEADERS):
        line = await asyncio.wait_for(reader.readline(), 5)
        if line in (b"\r\n", b"\n", b""):
            break
        name, sep, value = line.decode("latin-1").partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    fields = request_line.decode("latin-1").split()
    path = urlsplit(fields[1]).path if len(fields) >= 2 else "/"
    return path, headers


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    path = "?"
    try:
        path, headers = await read_request(reader)
        check_request(headers)
        status, body = await dispatch(path)
    except HttpError as e:
        log.info("%s -> %d %s", path, e.status, e)
        status, body = e.status, {"ok": False, "error": str(e)}
    except Exception as e:
        log.exception("Error while handling %s", path)
        status, body = 500, {"ok": False, "error": repr(e)}

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    head = (
        f"HTTP/1.1 {status} {HTTPStatus(status).phrase}\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(data)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    try:
        writer.write(head + data)
        await writer.drain()
    except ConnectionError:
        pass
    finally:
        writer.close()


async def main() -> None:
    global VOLCANO
    VOLCANO = Volcano()
    server = await asyncio.start_server(handle, HOST, PORT)
    log.info("Volcano server running at http://%s:%d", HOST, PORT)
    keepalive = asyncio.create_task(VOLCANO.keepalive())  # keep a reference so it is not garbage collected
    try:
        async with server:
            await server.serve_forever()
    finally:
        keepalive.cancel()


if __name__ == "__main__":
    asyncio.run(main())