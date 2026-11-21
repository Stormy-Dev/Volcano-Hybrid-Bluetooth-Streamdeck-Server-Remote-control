# volcano-remote

Remote control for the Volcano Hybrid via plain HTTP GET requests, so you can trigger it from a Stream Deck, a foot pedal, or anything else that can call a URL.

Keeps a persistent Bluetooth connection to the Volcano Hybrid and accepts commands at `http://127.0.0.1:8765/<command>`. The server is only reachable locally.

## Requirements

- Python 3.10+
- [`storzandbickel_ble`](https://pypi.org/project/storzandbickel-ble/)

## Running

```
python volcano_server.py
```

On Windows you can use `pythonw volcano_server.py` to run it without a console window. Logs are written to `volcano_server.log` next to the script.

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
