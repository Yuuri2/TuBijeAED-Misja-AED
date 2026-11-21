import os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# 1. Generowanie czystego wektorowego logotypu SVG (format otwarty!)
svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="800" height="260" viewBox="0 0 800 260" xmlns="http://www.w3.org/2000/svg">
  <rect width="800" height="260" fill="#FFFFFF" rx="16"/>
  <!-- Sygnet: Tarcza / Pin lokalizacji + Serce + Impuls -->
  <g transform="translate(40, 30)">
    <path d="M100 0 C45 0 0 45 0 100 C0 155 100 200 100 200 C100 200 200 155 200 100 C200 45 155 0 100 0 Z" fill="#006B3F"/>
    <path d="M100 158 C100 158 42 118 42 78 C42 56 59 40 79 40 C90 40 97 46 100 53 C103 46 110 40 121 40 C141 40 158 56 158 78 C158 118 100 158 100 158 Z" fill="#FFFFFF"/>
    <polyline points="68,86 86,86 94,66 104,106 112,86 132,86" fill="none" stroke="#D90429" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <!-- Typografia -->
  <text x="275" y="118" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="64" fill="#0B2545">OTWARTE <tspan fill="#006B3F">AED</tspan></text>
  <text x="278" y="162" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="22" fill="#D90429">Twoje dane ratują minuty.</text>
  <text x="278" y="194" font-family="Arial, Helvetica, sans-serif" font-weight="400" font-size="19" fill="#334155">Udostępnij lokalizację defibrylatora w dane.gov.pl</text>
</svg>
"""

with open("logotyp_otwarte_aed.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)

# 2. Generowanie PNG i JPG w wysokiej rozdzielczości (1600x520 px)
W, H = 1600, 520
img = Image.new("RGB", (W, H), "#FFFFFF")
draw = ImageDraw.Draw(img)

# Rysowanie sygnetu (zielony okrąg/pin z białym sercem i czerwonym impulsem)
draw.ellipse([80, 60, 440, 420], fill="#006B3F")
draw.polygon([(125, 330), (395, 330), (260, 475)], fill="#006B3F")
# Białe serce
draw.ellipse([165, 145, 265, 245], fill="#FFFFFF")
draw.ellipse([255, 145, 355, 245], fill="#FFFFFF")
draw.polygon([(168, 210), (352, 210), (260, 335)], fill="#FFFFFF")
# Czerwony impuls EKG
draw.line([(185, 225), (225, 225), (245, 180), (270, 270), (290, 225), (335, 225)], fill="#D90429", width=14)

try:
    font_big = ImageFont.truetype("arialbd.ttf", 115)
    font_sub = ImageFont.truetype("arialbd.ttf", 40)
    font_tag = ImageFont.truetype("arial.ttf", 34)
except:
    font_big = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    font_tag = ImageFont.load_default()

draw.text((520, 115), "OTWARTE", fill="#0B2545", font=font_big)
draw.text((1090, 115), "AED", fill="#006B3F", font=font_big)
draw.text((525, 265), "Twoje dane ratują minuty.", fill="#D90429", font=font_sub)
draw.text((525, 330), "Udostępnij defibrylator w portalu dane.gov.pl", fill="#334155", font=font_tag)

img.save("logotyp_otwarte_aed.png", "PNG")
img.save("logotyp_otwarte_aed.jpg", "JPEG", quality=95)

# 3. Generowanie logotypu w PDF
c_logo = canvas.Canvas("logotyp_otwarte_aed.pdf", pagesize=(800, 260))
c_logo.drawImage("logotyp_otwarte_aed.png", 0, 0, width=800, height=260)
c_logo.save()

# 4. Generowanie Księgi Znaku w PDF (zgodnej ze wszystkimi wymogami zadania)
c = canvas.Canvas("Ksiega_Znaku_Otwarte_AED.pdf", pagesize=A4)
width, height = A4

def header_footer(page_num, title_text):
    c.setFillColor(colors.HexColor("#0B2545"))
    c.rect(0, height - 60, width, 60, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 38, f"KSIĘGA ZNAKU • KAMPANIA „OTWARTE AED” | {title_text}")
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 9)
    c.drawString(40, 25, f"Misja AED – Dane na ratunek (dane.gov.pl) | Strona {page_num} z 4")

# STRONA 1: Koncepcja znaku (max 3-5 zdań) + Logotyp podstawowy
header_footer(1, "1. Koncepcja i znak podstawowy")
c.drawImage("logotyp_otwarte_aed.png", 40, height - 240, width=510, height=165)

c.setFillColor(colors.HexColor("#0B2545"))
c.setFont("Helvetica-Bold", 13)
c.drawString(40, height - 280, "Koncepcja znaku i cel kampanii promocyjnej:")

c.setFillColor(colors.HexColor("#1E293B"))
c.setFont("Helvetica", 11)
koncepcja = [
    "1. Znak kampanii „Otwarte AED” został zaprojektowany specjalnie dla dysponentów urządzeń (urzędów, firm i instytucji),",
    "   aby zachęcić ich do odpowiedzialnego publikowania danych o defibrylatorach w portalu dane.gov.pl.",
    "2. Sygnet łączy uniwersalny symbol lokalizacji (pin mapowy) z sercem oraz linią impulsu elektrycznego (EKG),",
    "   co jednoznacznie komunikuje ratowanie życia dzięki precyzyjnym danym przestrzennym.",
    "3. Zieleń nawiązuje do międzynarodowej normy ISO dla oznaczeń pierwszej pomocy i otwartości danych, natomiast",
    "   akcent ratowniczej czerwieni podkreśla pilność i wagę każdej minuty przy nagłym zatrzymaniu krążenia.",
    "4. Hasło „Twoje dane ratują minuty. Udostępnij defibrylator w portalu dane.gov.pl” buduje poczucie misji",
    "   społecznej i bezpośrednio wzywa zarządców budynków do rejestracji zbioru w oficjalnym rejestrze państwowym."
]
y = height - 305
for line in koncepcja:
    c.drawString(40, y, line)
    y -= 18

c.showPage()

# STRONA 2: Kolorystyka
header_footer(2, "2. Kolorystyka podstawowa")
c.setFillColor(colors.HexColor("#0B2545"))
c.setFont("Helvetica-Bold", 13)
c.drawString(40, height - 95, "Oficjalna paleta barw kampanii (HEX / RGB / CMYK):")

swatches = [
    ("#006B3F", "Zieleń Ratownicza (ISO AED)", "HEX: #006B3F | RGB: 0, 107, 63 | CMYK: 90, 25, 85, 15"),
    ("#0B2545", "Granat Instytucjonalny (dane.gov.pl)", "HEX: #0B2545 | RGB: 11, 37, 69 | CMYK: 95, 75, 35, 35"),
    ("#D90429", "Czerwień Impulsu Życia", "HEX: #D90429 | RGB: 217, 4, 41 | CMYK: 10, 98, 85, 2"),
    ("#FFFFFF", "Biel Tła (Wysoki Kontrast WCAG)", "HEX: #FFFFFF | RGB: 255, 255, 255 | CMYK: 0, 0, 0, 0")
]

y = height - 180
for hex_c, name, codes in swatches:
    c.setFillColor(colors.HexColor(hex_c))
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.rect(40, y, 80, 55, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(135, y + 32, name)
    c.setFont("Helvetica", 10)
    c.drawString(135, y + 12, codes)
    y -= 80

c.showPage()

# STRONA 3: Pole ochronne i minimalna wielkość
header_footer(3, "3. Pole ochronne i minimalna wielkość")
c.setFillColor(colors.HexColor("#0B2545"))
c.setFont("Helvetica-Bold", 13)
c.drawString(40, height - 95, "Pole ochronne znaku (margines bezpieczeństwa = 1x wysokość litery 'O'):")

# Rysunek pola ochronnego
c.setStrokeColor(colors.HexColor("#D90429"))
c.setDash(4, 4)
c.rect(70, height - 290, 450, 165, fill=0, stroke=1)
c.setDash()
c.drawImage("logotyp_otwarte_aed.png", 95, height - 270, width=400, height=125)

c.setFillColor(colors.HexColor("#1E293B"))
c.setFont("Helvetica", 10)
c.drawString(40, height - 320, "Przerywana czerwona linia wyznacza minimalne pole ochronne, w którym nie mogą pojawiać się inne teksty ani grafiki.")

c.setFillColor(colors.HexColor("#0B2545"))
c.setFont("Helvetica-Bold", 13)
c.drawString(40, height - 365, "Minimalna wielkość reprodukcji:")
c.setFillColor(colors.HexColor("#1E293B"))
c.setFont("Helvetica", 11)
c.drawString(40, height - 390, "• Wersja pełna z hasłem (druk): szerokość min. 45 mm")
c.drawString(40, height - 410, "• Wersja pełna z hasłem (ekran / web): szerokość min. 180 px")
c.drawString(40, height - 430, "• Sam sygnet (ikona / naklejka na kapsułę AED): min. 15 mm x 15 mm (48 px x 48 px)")

c.showPage()

# STRONA 4: Niedozwolone wykorzystywanie znaku
header_footer(4, "4. Niedozwolone modyfikacje znaku")
c.setFillColor(colors.HexColor("#0B2545"))
c.setFont("Helvetica-Bold", 13)
c.drawString(40, height - 95, "Zasady ochrony integralności znaku (czego nie wolno robić):")

rules = [
    "1. ZAKAZ zmiany proporcji znaku (rozciągania w pionie lub poziomie).",
    "2. ZAKAZ zmiany kolorystyki sygnetu i typografii na inne niż określone w Księdze Znaku.",
    "3. ZAKAZ obracania znaku pod kątem oraz nakładania cieni, gradientów i efektów 3D.",
    "4. ZAKAZ umieszczania znaku na niskokontrastowym lub wielobarwnym tle utrudniającym czytelność (wymóg WCAG).",
    "5. ZAKAZ używania znaku przez podmioty, które nie udostępniły zweryfikowanych danych o AED w dane.gov.pl."
]

y = height - 130
c.setFillColor(colors.HexColor("#1E293B"))
c.setFont("Helvetica", 11)
for r in rules:
    c.drawString(40, y, r)
    y -= 24

# Wizualizacja błędów (przekreślone ramki)
c.setStrokeColor(colors.HexColor("#D90429"))
c.setLineWidth(2)
# Przykład 1: Rozciągnięty
c.drawImage("logotyp_otwarte_aed.png", 50, height - 360, width=220, height=40)
c.line(50, height - 360, 270, height - 320)
c.line(50, height - 320, 270, height - 360)
c.setFont("Helvetica-Bold", 9)
c.setFillColor(colors.HexColor("#D90429"))
c.drawString(50, height - 375, "BŁĄD: Zaburzenie proporcji znaku")

# Przykład 2: Ciemne tło bez kontry
c.setFillColor(colors.HexColor("#1E293B"))
c.rect(310, height - 365, 220, 55, fill=1, stroke=0)
c.setFillColor(colors.HexColor("#0B2545"))
c.drawString(330, height - 340, "OTWARTE AED (brak kontrastu)")
c.line(310, height - 365, 530, height - 310)
c.line(310, height - 310, 530, height - 365)
c.setFillColor(colors.HexColor("#D90429"))
c.drawString(310, height - 375, "BŁĄD: Niski kontrast / nieczytelne tło")

c.save()
print("Gotowe! Wygenerowano logotyp (.svg, .png, .jpg, .pdf) oraz Ksiega_Znaku_Otwarte_AED.pdf")