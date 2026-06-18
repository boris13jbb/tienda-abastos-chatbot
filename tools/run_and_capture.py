"""Script temporal para ejecutar el servidor y capturar errores en archivo."""
import os
import sys
import traceback
from pathlib import Path

# Raíz del proyecto para importar main
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

log_path = Path(__file__).resolve().parent / "startup_log.txt"

def write_log(msg):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

try:
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("Iniciando...\n")
    write_log("Importando main...")
    import main
    write_log("main importado OK")
    write_log("Iniciando uvicorn...")
    import uvicorn
    from app.config.settings import settings
    write_log("Host: %s, Port: %s" % (settings.HOST, settings.PORT))
    os.chdir(_ROOT)
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
except Exception as e:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("ERROR: %s\n%s" % (e, traceback.format_exc()))
    raise
