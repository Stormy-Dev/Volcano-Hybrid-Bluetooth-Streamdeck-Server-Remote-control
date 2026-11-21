# volcano-remote

Remote control for the Volcano Hybrid via plain HTTP GET requests, so you can trigger it from a Stream Deck, a foot pedal, or anything else that can call a URL.

Keeps a persistent Bluetooth connection to the Volcano Hybrid and accepts commands at `http://127.0.0.1:8765/<command>`. The server is only reachable locally.

## Requirements

- Python 3.10+
- [`storzandbickel_ble`](https://pypi.org/project/storzandbickel-ble/)

## Running

On Windows, double-click `volcano_start.bat`. It starts the server in the background without a console window. Alternatively:

```
python volcano_server.py
```

Logs are written to `volcano_server.log` next to the script. Starting the server a second time does nothing if it is already running.

## Stream Deck

A ready-made Stream Deck folder is included in `stream-deck/VolcanoRemote.streamDeckAction`. Double-click it to import. It only uses built-in Stream Deck actions, so no plugins are needed. The layout is made for the Stream Deck XL.

Start the server once by hand. From then on, the "Start Server" button works too: on every start, the server writes a launcher to `C:\ProgramData\VolcanoRemote\volcano_start.bat` that points to the script's current location, and the button runs that launcher. If Windows is not installed on `C:`, adjust the button's path after importing.

## Commands

| Command | Description |
|---|---|
| `/heat-on` `/heat-off` `/heat-toggle` | Turn the heater on, off, or toggle it |
| `/pump-on` `/pump-off` `/pump-toggle` | Turn the pump on, off, or toggle it |
| `/pump-for/30` | Run the pump for 30 seconds, then switch it off automatically |
| `/temp/185` | Set the target temperature (40–230 °C) |
| `/temp-up` `/temp-down` | Change the target temperature by `TEMP_STEP` (or by a custom amount, e.g. `/temp-up/10`) |
| `/all-off` | Turn off heater and pump |
| `/status` | Current state as JSON |

Every command responds with the current state as JSON. If the Volcano is not connected, commands return 503 immediately while the server reconnects in the background.

Example:

```
curl http://127.0.0.1:8765/temp/185
```

## Configuration

Settings are at the top of `volcano_server.py`:

| Setting | Default | Description |
|---|---|---|
| `HOST` / `PORT` | `127.0.0.1` / `8765` | Address the server listens on |
| `DEVICE_NAME` | `S&B VOLCANO` | Bluetooth name of the device |
| `TEMP_STEP` | `5` | °C per step for `/temp-up` and `/temp-down` |
| `PUMP_AUTO_OFF` | `90` | Pump turns off after this many seconds when started via `/pump-on` or `/pump-toggle` (`None` = never) |
| `PUMP_FOR_MAX` | `120` | Upper limit in seconds for `/pump-for` |
| `RECONNECT_EVERY` | `20` | Seconds between background connection checks |
| `CONNECT_TIMEOUT` | `20` | Seconds before a connection attempt is given up |
| `COMMAND_TIMEOUT` | `10` | Seconds before a single Bluetooth command is given up |
| `BLOCK_BROWSER_REQUESTS` | `True` | Reject requests that a website triggered in your browser |
| `LAUNCHER` | `C:\ProgramData\VolcanoRemote\volcano_start.bat` | Launcher for the Stream Deck button, Windows only (`None` = don't create one) |