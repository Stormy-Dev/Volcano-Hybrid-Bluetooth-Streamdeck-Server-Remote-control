# volcano-remote

Remote control for the Volcano Hybrid via plain HTTP GET requests, so you can trigger it from a Stream Deck, a foot pedal, or anything else that can call a URL.

Keeps a persistent Bluetooth connection to the Volcano Hybrid and accepts commands at `http://127.0.0.1:8765/<command>`. The server is only reachable locally.

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
