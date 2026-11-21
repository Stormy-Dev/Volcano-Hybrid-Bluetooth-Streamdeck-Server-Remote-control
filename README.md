# volcano-remote

[![Download ZIP](https://img.shields.io/badge/Download-ZIP-e8762b?style=for-the-badge)](https://github.com/Stormy-Dev/Volcano-Hybrid-Bluetooth-Streamdeck-Server-Remote-control/archive/refs/heads/main.zip)

Remote control for the Volcano Hybrid via plain HTTP GET requests, so you can trigger it from a Stream Deck, a Stream Deck Pedal, or anything else that can call a URL.

Keeps a persistent Bluetooth connection to the Volcano Hybrid and accepts commands at `http://127.0.0.1:8765/<command>`. The server is only reachable locally.

## Installation (Windows)

1. Download the ZIP above and unzip it to a folder that stays where it is.
2. Double-click `install.bat`. It uses an existing Python 3.14 or 3.15 or installs Python 3.14 through the official Python install manager, sets up a virtual environment in `.venv`, installs the dependencies and starts the server.
3. Import the Stream Deck buttons by double-clicking one or both of these:
   - `stream-deck/VolcanoRemote.streamDeckAction` for the Stream Deck XL
   - `stream-deck/VolcanoStreamdeckPedals.streamDeckProfile` for the Stream Deck Pedal

Requires a PC with Bluetooth LE.

The first connection after starting takes a few seconds. Windows reads the Volcano's Bluetooth services once and keeps them cached, so later connections are faster.

### What goes where

| Item | Location | Purpose |
| ---- | -------- | ------- |
| `.venv` | Next to `install.bat` | Private Python environment with all dependencies. Don't move or delete it; running `install.bat` again recreates it if it breaks. |
| `volcano_start.bat` | Next to `install.bat` | Starts the server in the background without a console window. |
| `volcano_server.log` | Next to `volcano_server.py` | Log file. Look here first if something doesn't work. |
| `volcano_start.bat` | `C:\ProgramData\VolcanoRemote\` | Launcher for the Stream Deck "Start Server" button. The server rewrites it on every start so it always points to the folder the server currently lives in. |

`C:\ProgramData` is hidden in Explorer by default; type the path into the address bar to open it.

### Starting, stopping, restarting

- **Start:** press the "Start Server" button on the Stream Deck, or double-click `volcano_start.bat`. Starting it a second time does nothing if it is already running.
- **Stop:** run `taskkill /F /IM pythonw.exe` in a command prompt. This stops every Python program running without a window.
- **Restart** (e.g. after editing `volcano_server.py`): stop it, then start it again.
- **Folder moved?** Double-click `volcano_start.bat` in the new folder once. That rewrites the launcher, and the Stream Deck button works again.
- **Start with Windows (optional):** press Win + R, enter `shell:startup` and put a shortcut to `volcano_start.bat` into that folder.

Running `install.bat` again is safe; it only repairs `.venv` and the dependencies and leaves your settings in `volcano_server.py` alone.

### Manual installation

Requires Python 3.14 or newer and uses [`storzandbickel-ble`](https://pypi.org/project/storzandbickel-ble/).

```
pip install -r requirements.txt
python volcano_server.py
```

Starting the server a second time does nothing if it is already running.

## Stream Deck

Both files only use built-in Stream Deck actions, so no plugins are needed. All labels are Stream Deck titles, so you can change or translate them in the Stream Deck app. The icons in `volcano_icons/` contain no text.

**Stream Deck XL** (`VolcanoRemote.streamDeckAction`): a ready-made folder with heater, pump, temperature presets, temperature up/down, all-off, status and a "Start Server" button.

**Stream Deck Pedal** (`VolcanoStreamdeckPedals.streamDeckProfile`): left pedal toggles the heater, middle pedal toggles the pump, right pedal runs the pump for 7 seconds.

The "Start Server" button works once the server has been started by hand: on every start, the server writes a launcher to `C:\ProgramData\VolcanoRemote\volcano_start.bat`, and the button runs that launcher. If Windows is not installed on `C:`, adjust the button's path after importing.

## Commands

| Command                               | Description                                                                              |
| ------------------------------------- | ---------------------------------------------------------------------------------------- |
| `/heat-on` `/heat-off` `/heat-toggle` | Turn the heater on, off, or toggle it                                                    |
| `/pump-on` `/pump-off` `/pump-toggle` | Turn the pump on, off, or toggle it                                                      |
| `/pump-for/30`                        | Run the pump for 30 seconds, then switch it off automatically                            |
| `/temp/185`                           | Set the target temperature (40–230 °C)                                                   |
| `/temp-up` `/temp-down`               | Change the target temperature by `TEMP_STEP` (or by a custom amount, e.g. `/temp-up/10`) |
| `/all-off`                            | Turn off heater and pump                                                                 |
| `/status`                             | Current state as JSON, read fresh from the Volcano                                       |

Every command responds with the state as JSON. `/status` reads it from the Volcano; the other commands return what the server knows after sending the command, so they respond without an extra Bluetooth round trip. If the Volcano is not connected, commands return 503 immediately while the server reconnects in the background.

Example:

```
curl http://127.0.0.1:8765/temp/185
```

### Why the buttons respond quickly

Reading values from the Volcano over Bluetooth takes about 0.1 s per value on Windows, so the server avoids reads on button presses:

- It remembers whether pump and heater are on, because it switched them itself. Toggles send the command right away.
- In the background it checks pump and heater every `POLL_EVERY` seconds, so changes made on the device itself are picked up.
- For `SETTLE` seconds after a command it ignores the Volcano's own reports, because the device reports a new state with a delay. Without this, quickly pressing pump on and then off would switch the pump on twice.

## Configuration

Settings are at the top of `volcano_server.py`:

| Setting                  | Default                                          | Description                                                                                           |
| ------------------------ | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `HOST` / `PORT`          | `127.0.0.1` / `8765`                             | Address the server listens on                                                                         |
| `DEVICE_NAME`            | `S&B VOLCANO`                                    | Bluetooth name of the device (the Hybrid advertises as `S&B VOLCANO H`; partial match is enough)      |
| `TEMP_STEP`              | `5`                                              | °C per step for `/temp-up` and `/temp-down`                                                           |
| `PUMP_AUTO_OFF`          | `90`                                             | Pump turns off after this many seconds when started via `/pump-on` or `/pump-toggle` (`None` = never) |
| `PUMP_FOR_MAX`           | `120`                                            | Upper limit in seconds for `/pump-for`                                                                |
| `RECONNECT_EVERY`        | `20`                                             | Seconds between background connection checks                                                          |
| `SCAN_TIME`              | `20`                                             | Maximum seconds to search for the Volcano; the search stops as soon as it is found                    |
| `CONNECT_TIMEOUT`        | `40`                                             | Seconds before connecting (after the Volcano was found) is given up                                   |
| `COMMAND_TIMEOUT`        | `10`                                             | Seconds before a single Bluetooth command is given up                                                 |
| `POLL_EVERY`             | `5`                                              | Seconds between background checks of pump and heater state                                           |
| `STATE_TRUST`            | `10`                                             | Seconds a known pump/heater state is used for toggles without asking the Volcano again                |
| `SETTLE`                 | `3`                                              | Seconds after a command in which the Volcano's own state reports are ignored                          |
| `BLOCK_BROWSER_REQUESTS` | `True`                                           | Reject requests that a website triggered in your browser                                              |
| `LAUNCHER`               | `C:\ProgramData\VolcanoRemote\volcano_start.bat` | Launcher for the Stream Deck button, Windows only (`None` = don't create one)                         |

## Troubleshooting

**`/status` says "Volcano is not connected".** Wait about a minute after starting; the server retries every `RECONNECT_EVERY` seconds. The Volcano accepts only one Bluetooth connection at a time, so close the Storz & Bickel app on your phone and any browser tab with the web app. If the Bluetooth icon on the Volcano stops blinking and stays lit while the server is still not connected, something else holds the connection, often an old copy of the server still running in the background. Stop it with `taskkill /F /IM pythonw.exe` and start again.

**Check the log.** `volcano_server.log` shows each connection attempt. After a successful one it shows a line like:

```
Found after 0.4 s, connected after 3.2 s (Windows cache: yes)
```

`Volcano not reachable (DeviceNotFoundError ...)` or `device not found` means the PC did not see the Volcano at all: check Bluetooth on both devices and the distance. A timeout means the Volcano was found but connecting took too long; raise `CONNECT_TIMEOUT`.

**More detail.** Change `level=logging.INFO` to `level=logging.DEBUG` near the top of `volcano_server.py` and restart the server. Switch it back afterwards, because the log grows quickly.

**`/favicon.ico -> 403` in the log** is just a browser asking for an icon and can be ignored.

## License

MIT, see [LICENSE](LICENSE).

This is an unofficial project and is not affiliated with or endorsed by Storz & Bickel. Volcano and Volcano Hybrid are trademarks of their respective owner.
