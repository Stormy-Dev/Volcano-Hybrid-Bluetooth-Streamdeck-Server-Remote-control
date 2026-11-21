remote control volcano hybrid via silent get request via stream deck/pedal or other things:)
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
