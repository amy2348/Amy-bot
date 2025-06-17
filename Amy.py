import os
import requests
from bs4 import BeautifulSoup
import random
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from io import BytesIO
import pypandoc

# Frases literarias por autor
author_quotes = {
    "gabriel garcia marquez": [
        "“No hay medicina que cure lo que no cura la felicidad.”",
        "“El problema del matrimonio es que se acaba todas las noches después de hacer el amor, y hay que volver a reconstruirlo todas las mañanas antes del desayuno.”"
    ],
    "isabel allende": [
        "“La memoria es frágil y el transcurso de una vida es muy breve.”",
        "“Aprendí que no se puede dar marcha atrás, que la esencia de la vida es ir hacia adelante.”"
    ],
    "jorge luis borges": [
        "“Uno no es lo que es por lo que escribe, sino por lo que ha leído.”",
        "“Siempre imaginé que el Paraíso sería algún tipo de biblioteca.”"
    ]
}

def get_quote(query):
    query = query.lower()
    for author in author_quotes:
        if author in query:
            return random.choice(author_quotes[author])
    return random.choice(sum(author_quotes.values(), []))

def get_book_info(title):
    url = f"https://openlibrary.org/search.json?q={title.replace(' ', '+')}"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        if data["docs"]:
            doc = data["docs"][0]
            cover_id = doc.get("cover_i")
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
            author = doc.get("author_name", ["Desconocido"])[0]
            year = doc.get("first_publish_year", "Desconocido")
            title = doc.get("title", title)
            summary = f"📖 *{title}* de *{author}* ({year})\nUna obra que no deberías perderte."
            return cover_url, summary
    return None, f"📖 Una lectura interesante que despertará tu imaginación."

def get_pdfdrive_download_link(query):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = f"https://www.pdfdrive.com/search?q={query.replace(' ', '+')}"
    search_res = session.get(search_url, headers=headers)
    if search_res.status_code != 200:
        return None

    soup = BeautifulSoup(search_res.text, "html.parser")
    first_result = soup.find("div", class_="file-right")
    if not first_result:
        return None

    link = first_result.find("a")
    if not link:
        return None

    book_page_url = "https://www.pdfdrive.com" + link['href']
    book_page_res = session.get(book_page_url, headers=headers)
    if book_page_res.status_code != 200:
        return None

    book_soup = BeautifulSoup(book_page_res.text, "html.parser")
    download_button = book_soup.find("a", id="downloadButton")
    if not download_button:
        return None

    direct_link = download_button['href']
    if not direct_link.startswith("http"):
        direct_link = "https://www.pdfdrive.com" + direct_link

    return direct_link

def download_file(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return BytesIO(res.content)
    return None

def convert_pdf_to_epub(pdf_bytes_io):
    pdf_bytes_io.seek(0)
    with open("/tmp/temp.pdf", "wb") as f:
        f.write(pdf_bytes_io.read())
    output = "/tmp/temp.epub"
    try:
        pypandoc.convert_file("/tmp/temp.pdf", 'epub', outputfile=output)
        with open(output, "rb") as f:
            epub_bytes = f.read()
        return BytesIO(epub_bytes)
    except Exception as e:
        print("Error conversión PDF->EPUB:", e)
        return None

async def send_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await update.message.reply_text(f"🔎 Buscando *{query}*...", parse_mode="Markdown")

    cover_url, summary = get_book_info(query)
    if cover_url:
        img_res = requests.get(cover_url)
        if img_res.status_code == 200:
            await update.message.reply_photo(photo=BytesIO(img_res.content))

    await update.message.reply_text(summary, parse_mode="Markdown")
    await update.message.reply_text(get_quote(query))

    pdf_link = get_pdfdrive_download_link(query)
    if not pdf_link:
        await update.message.reply_text("❌ No encontré el libro en PDFDrive. Intenta otro
