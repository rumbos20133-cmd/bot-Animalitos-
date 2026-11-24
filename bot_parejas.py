import os
import threading
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

LOTERIAS = {
    "lottoactivo": "Lotto Activo",
    "lagranjita": "La Granjita",
    "guacharoactivo": "Guacharo Activo",
}
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIAS_DE_HISTORIAL = 60

# resultados[loteria] = lista de (fecha, [animalitos en orden del dia])
resultados = {}


# ---------- Mini servidor web (para que Render no apague el bot) ----------
class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", puerto), Ping).serve_forever()


# ---------- Lectura de datos de TuAzar ----------
def leer_dia(loteria, dia):
    """Intenta leer los animalitos de un dia. Devuelve una lista de nombres."""
    url = f"https://www.tuazar.com/loteria/{loteria}/resultados/{dia.year}/{dia.month:02d}/{dia.day:02d}/"
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        sopa = BeautifulSoup(r.text, "html.parser")
        nombres = []
        for img in sopa.find_all("img"):
            alt = (img.get("alt") or "").strip()
            if alt and len(alt) < 25 and "logo" not in alt.lower():
                nombres.append(alt.lower())
        return nombres
    except Exception:
        return []


def cargar_historial():
    hoy = date.today()
    for clave in LOTERIAS:
        lista = []
        for i in range(DIAS_DE_HISTORIAL):
            dia = hoy - timedelta(days=i)
            animales = leer_dia(clave, dia)
            if animales:
                lista.append((dia, animales))
            time.sleep(0.5)
        resultados[clave] = lista


# ---------- Estadisticas ----------
def mas_repetidos(clave, top=5):
    c = Counter()
    for _, animales in resultados.get(clave, []):
        c.update(animales)
    return c.most_common(top)


def parejas(clave, top=5):
    c = Counter()
    for _, animales in resultados.get(clave, []):
        unicos = sorted(set(animales))
        for i in range(len(unicos)):
            for j in range(i + 1, len(unicos)):
                c[(unicos[i], unicos[j])] += 1
    return c.most_common(top)


def por_dia_semana(clave, dia_semana, top=5):
    c = Counter()
    for dia, animales in resultados.get(clave, []):
        if dia.weekday() == dia_semana:
            c.update(animales)
    return c.most_common(top)


def tripletas(clave):
    top = [a for a, _ in mas_repetidos(clave, 3)]
    return top


# ---------- Comandos del bot ----------
AVISO = "\n\nSon estadisticas de lo que ya salio, no pronosticos. El sorteo es al azar."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola! Comandos:\n"
        "/masrepetidos - animalitos que mas salieron\n"
        "/parejas - los que salen juntos\n"
        "/hoy - lo que mas sale en el dia de hoy de la semana\n"
        "/tripleta - los 3 que mas han salido\n"
        "/prueba - revisar si el bot esta leyendo datos"
    )


async def prueba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "Dias leidos por loteria:\n"
    for clave, nombre in LOTERIAS.items():
        texto += f"{nombre}: {len(resultados.get(clave, []))} dias\n"
    await update.message.reply_text(texto)


async def masrepetidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "Mas repetidos (ultimos 60 dias):\n"
    for clave, nombre in LOTERIAS.items():
        items = mas_repetidos(clave)
        linea = ", ".join(f"{a} ({n})" for a, n in items) or "sin datos"
        texto += f"\n{nombre}: {linea}"
    await update.message.reply_text(texto + AVISO)


async def parejas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "Parejas que mas salen juntas el mismo dia:\n"
    for clave, nombre in LOTERIAS.items():
        items = parejas(clave)
        linea = ", ".join(f"{a}+{b} ({n})" for (a, b), n in items) or "sin datos"
        texto += f"\n{nombre}: {linea}"
    await update.message.reply_text(texto + AVISO)


async def hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dia = date.today().weekday()
    texto = f"Lo que mas ha salido los {DIAS[dia]}:\n"
    for clave, nombre in LOTERIAS.items():
        items = por_dia_semana(clave, dia)
        linea = ", ".join(f"{a} ({n})" for a, n in items) or "sin datos"
        texto += f"\n{nombre}: {linea}"
    await update.message.reply_text(texto + AVISO)


async def tripleta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "Tripletas con los 3 que mas han salido:\n"
    for clave, nombre in LOTERIAS.items():
        t = tripletas(clave)
        texto += f"\n{nombre}: {' - '.join(t) or 'sin datos'}"
    await update.message.reply_text(texto + AVISO)


if __name__ == "__main__":
    threading.Thread(target=servidor_web, daemon=True).start()
    threading.Thread(target=cargar_historial, daemon=True).start()

    application = ApplicationBuilder().token(os.environ["TOKEN"]).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("prueba", prueba))
    application.add_handler(CommandHandler("masrepetidos", masrepetidos))
    application.add_handler(CommandHandler("parejas", parejas_cmd))
    application.add_handler(CommandHandler("hoy", hoy))
    application.add_handler(CommandHandler("tripleta", tripleta))
    application.run_polling()
