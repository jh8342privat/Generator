import streamlit as st
import re
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
import os
import math
from copy import deepcopy
import xml.etree.ElementTree as ET
import fitz
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Konfiguration
MAX_WIDTH = 70
COLUMN_COUNT = 4
PADDING = 12
LINE_HEIGHT = 35
ICON_SIZE = 32
REC_SIZE = 10
FONT_PATH = "PTSansProCondRg.OTF"  # oder "arial.ttf"
FONT2 = "PTSansProXBd.OTF"
FONT_SIZE = 28
FONT_SIZE2 = 42
LOGO_PATH = "logos"  # Verzeichnis mit Logos als PNG
COL_WIDTH = 270

# Farben
COLOR_MAP = {
    "ja": "green",
    "nein": "red",
    "enthaltung": "orange",
    "nicht_abgestimmt": "grey"
}

parteien_reihenfolge = [
            "CDU", "CSU", "SPD", "Grune", "FDP",
            "Linke", "AfD", "fw", 'BSW', "Piratenpartei",
            "ODP", "Tierschutzpartei", "Volt", "Sonstige"
        ]

FRANKTIONSKÜRZEL = {
    "Fraktion der Progressiven Allianz der Sozialdemokraten im Europäischen Parlament": "S&D",
    "Fraktion Renew Europe": "Renew",
    "Fraktion der Europäischen Volkspartei (Christdemokraten)": "PPE",
    "Fraktion Patrioten für Europa": "PfE",
    "Fraktion der Europäischen Konservativen und Reformer": "ECR",
    "Fraktion Europa der Souveränen Nationen": "ESN",
    "Fraktion Die Linke im Europäischen Parlament - GUE/NGL": "The Left",
    "Fraktion der Grünen / Freie Europäische Allianz": "Verts/ALE",
    "Fraktionslos": "NI"
}

PARTEI_ABKÜRZUNGEN = {
    "Bündnis 90/Die Grünen": "Grune",
    "Sozialdemokratische Partei Deutschlands": "SPD",
    "Christlich Demokratische Union Deutschlands": "CDU",
    "Christlich-Soziale Union in Bayern e.V.": "CSU",
    "Freie Demokratische Partei": "FDP",
    "DIE LINKE.": "Linke",
    "Alternative für Deutschland": "AfD",
    'Partei Mensch Umwelt Tierschutz': 'Tierschutz',
    'Bündnis Sahra Wagenknecht – Vernunft und Gerechtigkeit': 'BSW',
    'Die PARTEI': 'Die Partei',
    'Freie Wähler': 'fw',
    'Ökologisch-Demokratische Partei': "ODP",
    'Familien-Partei Deutschlands': 'Familien Partei',
    'Partei des Fortschritts': 'PDF'
}


def extract_toc_entries(text):
    toc_entries = re.findall(r"(\d+\.\d+)\s+(.*?)(?:\s+)?\.{3,}\s*\d+", text)
    return toc_entries

def display_choices(toc_entries):
    print("\nAbstimmungspunkte im Dokument:\n")
    for i, (num, title) in enumerate(toc_entries, 1):
        st.write(f"{i}. [{num}] {title}")

def extract_pdf_text():
    uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")
    text = ""
    text1 = ""
    if uploaded_file is not None:
        # Load PDF into PyMuPDF from memory
        pdf_stream = BytesIO(uploaded_file.read())
        doc = fitz.open(stream=pdf_stream, filetype="pdf")

        # Extract and display text from each page
        for page_num, page in enumerate(doc, start=1):
            text += page.get_text()
        return text

def get_selected_entry(toc_entries):
    #1index = int(input("Bitte Nummer der gewünschten Abstimmung eingeben: ")) - 1
    selected = st.selectbox('Gewünschte Abstimmung auswählen: ', toc_entries)
    return selected

def crop_text_by_pattern(text, start_index, end_pattern):
    lines = text[start_index:].splitlines()
    cropped_lines = []
    for line in lines:
        if re.match(end_pattern, line.strip()):
            break
        cropped_lines.append(line)
    return "\n".join(cropped_lines)

def split_text_on_marker(text):
    # Normalize line endings
    marker_start = """ПОПРАВКИ В ПОДАДЕНИТЕ ГЛАСОВЕ И НАМЕРЕНИЯ ЗА ГЛАСУВАНЕ - CORRECCIONES E INTENCIONES DE VOTO - OPRAVY 
HLASOVÁNÍ A SDĚLENÍ O ÚMYSLU HLASOVAT - STEMMERETTELSER OG -INTENTIONER - BERICHTIGUNGEN DES 
STIMMVERHALTENS UND BEABSICHTIGTES STIMMVERHALTEN - HÄÄLETUSE PARANDUSED JA HÄÄLETUSKAVATSUSED - 
ΔΙΟΡΘΩΣΕΙΣ ΚΑΙ ΠΡΟΘΕΣΕΙΣ ΨΗΦΟΥ - CORRECTIONS TO VOTES AND VOTING INTENTIONS - CORRECTIONS ET INTENTIONS DE 
VOTE - CEARTÚCHÁIN AR AN VÓTA AGUS INTINNÍ VÓTÁLA - IZMJENE DANIH GLASOVA I NAMJERE GLASAČA - CORREZIONI E 
INTENZIONI DI VOTO - BALSOJUMU LABOJUMI UN NODOMI BALSOT - BALSAVIMO PATAISYMAI IR KETINIMAI - SZAVAZATOK 
HELYESBÍTÉSEI ÉS SZAVAZÁSI SZÁNDÉKOK - KORREZZJONIJIET U INTENZJONIJIET GĦALL-VOT - RECTIFICATIES STEMGEDRAG/ 
VOORGENOMEN STEMGEDRAG - KOREKTY GŁOSOWANIA I ZAMIAR GŁOSOWANIA - CORREÇÕES E INTENÇÕES DE VOTO - 
CORECTĂRI ŞI INTENŢII DE VOT - OPRAVY HLASOVANIA A ZÁMERY PRI HLASOVANÍ - POPRAVKI IN NAMERE GLASOVANJA - 
ÄÄNESTYSKÄYTTÄYTYMISTÄ JA ÄÄNESTYSAIKEITA KOSKEVAT ILMOITUKSET - RÄTTELSER/AVSIKTSFÖRKLARINGAR TILL 
AVGIVNA RÖSTER"""
    text = text.replace('\r\n', '\n')
    index = text.find(marker_start)
    if index == -1:
        return text.strip(), None
    else:
        part_1 = text[:index].strip()
        part_2 = text[index + len(marker_start):].strip()
        return part_1, part_2

def parse_vote_blocks(entries):
    result = {'+': defaultdict(list), '-': defaultdict(list), '0': defaultdict(list)}
    for symbol, block_text in entries:
        current_group = None
        lines = block_text.strip().splitlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            group_match = re.match(r'^([A-Za-z/&.\- ]+):$', line)
            if group_match:
                current_group = group_match.group(1).strip()
                continue

            if current_group:
                names = [name.strip().strip(",") for name in line.split(",") if name.strip()]
                result[symbol][current_group].extend(names)

    return {symbol: dict(groups) for symbol, groups in result.items()}

def vote_result(text, heading):
    known_groups = [
        "EPP", "S&D", "Renew", "Greens", "ID", "The Left", "ECR", "NI"
    ]

    # Finde alle Positionen des Headings im Text
    print('HEADING -------------------------')
    print(heading)
    matches = list(re.finditer(re.escape(heading), text))
    print(matches)
    print(text[2200:2400])
    if len(matches) < 2:
        return "⚠️ Heading nicht zweimal im Text gefunden."

    # Nimm das zweite Vorkommen
    start = matches[1].end()
    text = crop_text_by_pattern(text, start, r"^\d+\.\d+ A\d{2}-\d{4}/\d{4}")
    text, text2 = split_text_on_marker(text)
    pattern = r"^\d+\s*([+-0∅])\s*(.*?)(?=^\d+\s*[+-0∅]|\Z)"
    matches = re.findall(pattern, text, flags=re.DOTALL | re.MULTILINE)
    stimmen = parse_vote_blocks(matches)
    key_map = {
        '+': 'ja',
        '-': 'nein',
        '0': 'enthaltung'
    }
    return {key_map.get(k, k): v for k, v in stimmen.items()}, text2

def normalize_partei(name):
    return PARTEI_ABKÜRZUNGEN.get(name, name)

def normalize_fraktion(name):
    return FRANKTIONSKÜRZEL.get(name, name)

def parse_abgeordnete_from_file(pfad_zur_datei):
    tree = ET.parse(pfad_zur_datei)
    root = tree.getroot()
    abgeordnete_liste = []
    abgeordnete_liste2 = []

    for mep in root.findall("mep"):
        full_name = (mep.findtext("fullName") or "").strip()
        fraktion_lang = (mep.findtext("politicalGroup") or "").strip()
        national_party = (mep.findtext("nationalPoliticalGroup") or "").strip()

        # Fraktionskürzel verwenden, wenn bekannt
        fraktion = normalize_fraktion(fraktion_lang)
        national_party = normalize_partei(national_party)

        parts = full_name.split()
        nachnamen_teile = [teil.capitalize() for teil in parts if teil.isupper()]
        vornamen_teile = [teil.capitalize() for teil in parts if not teil.isupper()]


        if not nachnamen_teile:
            nachname = parts[-1]
            vorname = " ".join(parts[:-1])
        else:
            nachname = " ".join(nachnamen_teile)
            vorname = " ".join(vornamen_teile)

        if nachname == "Strack-zimmermann":
            nachname = "Strack-Zimmermann"

        abgeordnete_liste.append({
            "nachname": nachname,
            "vorname": vorname,
            "fraktion": fraktion,
            "partei": national_party
        })

        ### LISTE 2
        parts2 = full_name.split()
        nachnamen_teile = [teil.capitalize() for teil in parts if teil.isupper()]
        vornamen_teile = [teil.capitalize() for teil in parts if not teil.isupper()]

        if not nachnamen_teile:
            nachname2 = parts[-1]
            vorname2 = " ".join(parts[:-1])
        else:
            nachname2 = " ".join(nachnamen_teile)
            vorname2 = " ".join(vornamen_teile)

        abgeordnete_liste2.append({
            "nachname": nachname2,
            "vorname": vorname2,
            "fraktion": fraktion,
            "partei": national_party
        })
    return abgeordnete_liste, abgeordnete_liste2

def partei_sort_key(entry):
        partei = entry["partei"]
        try:
            partei_index = parteien_reihenfolge.index(partei)
        except ValueError:
            partei_index = len(parteien_reihenfolge)  # alles unbekannte ans Ende
        return (partei_index, entry["name"])
        
def auswertung_abstimmung_sortiert(
    abgeordnete_de,
    abstimmung,
    titel = "Ein Titel fehlt"
):
    ergebnis = {
        "title": titel,
        "ja": [],
        "nein": [],
        "enthaltung": [],
        "nicht_abgestimmt": []
    }

    abgeordnete_map = {a["nachname"]: a for a in abgeordnete_de}
    abgestimmt_nachnamen = set()

    for entscheidung in ["ja", "nein", "enthaltung"]:
        for fraktion, namen in abstimmung.get(entscheidung, {}).items():
            for name in namen:
                if name in abgeordnete_map:
                    abgeordneter = abgeordnete_map[name]
                    ergebnis[entscheidung].append({
                        "name": abgeordneter["nachname"],
                        "vorname": abgeordneter["vorname"],
                        "partei": abgeordneter["partei"]
                    })
                    abgestimmt_nachnamen.add(name)

    for abgeordneter in abgeordnete_de:
        if abgeordneter["nachname"] not in abgestimmt_nachnamen:
            ergebnis["nicht_abgestimmt"].append({
                "name": abgeordneter["nachname"],
                "vorname": abgeordneter["vorname"],
                "partei": abgeordneter["partei"]
            })

    for entscheidung in ["ja", "nein", "enthaltung", "nicht_abgestimmt"]:
        ergebnis[entscheidung].sort(key=partei_sort_key)
    return ergebnis
    
def draw_block(draw, persons, label, y_offset, icon_color, font, font2, font3, logos):
    draw.rectangle([PADDING, y_offset - 2, PADDING + 10, y_offset + ICON_SIZE ], fill=icon_color)
    draw.text((PADDING + REC_SIZE + 13, y_offset), label, fill=icon_color, font=font2)
    
    #y_offset += LINE_HEIGHT
    persons.insert(0, {'name': '', 'vorname': '', 'partei': ''}) 
    rows = math.ceil(len(persons) / COLUMN_COUNT)
    print(persons)

    for col in range(COLUMN_COUNT):
            for row in range(rows):

                index = row + rows * col 
                if index >= len(persons):
                    continue
                person = persons[index]

                if index == 0:
                    name = ''
                else:
                    name = f"{person['name']} {person['vorname'][0]}."
                if True:
                    if person['name'] == "Von Der Schulenburg":
                        name = "v. d. Schulenburg M."
                    
                    if person['name'] == "Strack-Zimmermann":
                        name = "Strack-Zimmermann M.-A."
                    
                    if person['name'] == "Warnke":
                        name = "Warnke J.-P."
                    
                    if person['name'] == "Oetjen":
                        name = "Oetje J.-C."
                logo = logos.get(person["partei"], None)

                x = PADDING + col * COL_WIDTH
                y = y_offset + row * LINE_HEIGHT

                    # Rechteck (Zustimmungsindikator)
                draw.rectangle([x, y -2, x + 10, y + ICON_SIZE + 2], fill=icon_color)

                    # Text
                if name == "Strack-Zimmermann M.-A.":
                    draw.text((x + REC_SIZE + 13, y+3), name, fill="black", font=font3)
                else:
                    draw.text((x + REC_SIZE + 13, y), name, fill="black", font=font)

                    # Logo
                if logo:
                    img.paste(logo, (x + REC_SIZE + 250 - logo.width, y), logo)

    return y_offset + rows * LINE_HEIGHT + LINE_HEIGHT

def load_logos():
    logos = {}
    for fname in os.listdir(LOGO_PATH):
        if fname.endswith(".png"):
            partei = fname.replace(".png", "")


            original_logo = Image.open(os.path.join(LOGO_PATH, fname)).convert("RGBA")
            # Calculate aspect ratio
            aspect_ratio = original_logo.width / original_logo.height
            new_width = int(ICON_SIZE * aspect_ratio)

            # Resize while preserving proportions
            logo = original_logo.resize((new_width, ICON_SIZE), Image.LANCZOS)

            # If it exceeds max width, scale it down again
            if logo.width > MAX_WIDTH:
                scale_ratio = MAX_WIDTH / logo.width
                new_width = MAX_WIDTH
                new_height = int(logo.height * scale_ratio)
                logo = logo.resize((new_width, new_height), Image.LANCZOS)
            
            logos[partei] = logo
    return logos

def wrap_text(text, font, max_width, draw):
    lines = []
    words = text.split()
    line = ""

    for word in words:
        test_line = line + word + " "
        bbox = font.getbbox(test_line)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            line = test_line
        else:
            lines.append(line.strip())
            line = word + " "

    if line:
        lines.append(line.strip())

    return lines


def generate_image(data, output_path="sharepic.png"):
    size4 = st.slider("Größe der Überschrift", min_value=0, max_value=100, value=42)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    font4 = ImageFont.truetype(FONT2, size4)
    font2 = ImageFont.truetype(FONT2, round(FONT_SIZE*0.9))
    font3 = ImageFont.truetype(FONT_PATH, round(FONT_SIZE *0.8))
    logos = load_logos()
    #print("Geladene Parteien-Logos:", logos.keys())

    # Höhe grob schätzen
    total_people = sum(len(data[k]) for k in ["ja", "nein", "enthaltung"])
    estimated_height = 1200 
    global img
    img = Image.new("RGBA", (1200, estimated_height), "white")
    draw = ImageDraw.Draw(img)

    # Überschrift
    wrapped_lines = wrap_text(data['title'], font4, img.width - 2 * PADDING, draw)

    y = PADDING 
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font4)
        line_width = bbox[2] - bbox[0]
        x1 = (img.width - line_width) // 2  # zentriert
        draw.text((x1, y), line, fill="black", font=font4)
        y += LINE_HEIGHT + round(size4 / 4)
    y = (PADDING + round(size4 / 2.8)) * len(wrapped_lines) + LINE_HEIGHT * 2 

    # Blöcke zeichnen
    y = draw_block(draw, data["ja"], "DAFÜR", y, COLOR_MAP["ja"], font, font2, font3, logos)
    y = draw_block(draw, data["nein"], "DAGEGEN", y, COLOR_MAP["nein"], font, font2, font3, logos)
    y = draw_block(draw, data["enthaltung"], "ENTHALTEN", y, COLOR_MAP["enthaltung"], font, font2, font3, logos)
    y = draw_block(draw, data["nicht_abgestimmt"], "NICHT ABGESTIMMT", y, COLOR_MAP["nicht_abgestimmt"], font, font2, font3, logos)

    img = img.crop((0, 0, img.width, y + 2 * LINE_HEIGHT))  # Bild kürzen
    st.image(img, caption="Vorschau", use_container_width=True)
    if st.button("Bild generieren"):
        img.show()
    
def apply_vote_corrections(data, correction_text):
    updated = deepcopy(data)

    # Stimmenblöcke extrahieren
    blocks = re.split(r"(?=\n[+\-0])", correction_text.strip())
    print(blocks)
    vote_map = {'+': 'ja', '-': 'nein', '0': 'enthaltung'}

    # Hilfsfunktion: Finde Person im Dict
    def find_and_remove(person, section):
        for key in ['ja', 'nein', 'enthaltung', 'nicht_abgestimmt']:
            for entry in updated[key]:
                full_name = f"{entry['vorname']} {entry['name']}".lower()
                print(full_name)
                if full_name == person.lower():
                    print('FOUND')
                    updated[key].remove(entry)
                    updated[section].append(entry)
                    return

    # Korrekturen anwenden
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        symbol = block[0]
        vote_type = vote_map.get(symbol)
        if not vote_type:
            continue

        # Namen extrahieren
        names = re.split(r",\s*", block[1:].strip())
        for full_name in names:
            if not full_name:
                continue
            parts = full_name.strip().split()
            if len(parts) < 2:
                continue  # Kein gültiger Name
            vorname = " ".join(parts[:-1])
            nachname = parts[-1]
            person = f"{vorname} {nachname}"
            find_and_remove(person, vote_type)

    return updated

def main():
    #pdf_path = input("Pfad oder Name der PDF-Datei: ").strip()
    st.header("Abstimmungsbild Generator")

    text = extract_pdf_text()
    if text:
        toc_entries = extract_toc_entries(text)
        # do something with toc_entries
    else:
        st.info("Waiting for PDF upload...")
        return None

    if not toc_entries:
        st.write("Keine Abstimmungen im Inhaltsverzeichnis gefunden.")
        return
    if not toc_entries:
        st.write("Keine Abstimmungen im Inhaltsverzeichnis gefunden.")
        return
    
    num, heading = get_selected_entry(toc_entries)
    #st.subheader("Abstimmungen im Dokument")
    #display_choices(toc_entries)
    titel = st.text_input("Titel der Abstimmung")
    if heading:

        print(f"\nAbstimmungsergebnis für: {num} – {heading}\n")
        result, text2 = vote_result(text, f"{num} {heading.strip()}")

        mep_list, mep_list2 = parse_abgeordnete_from_file('germans.xml')
        auswertung = auswertung_abstimmung_sortiert(mep_list, result, titel)

        if text2 is not None:
            auswertung = apply_vote_corrections(auswertung, text2)
            for entscheidung in ["ja", "nein", "enthaltung", "nicht_abgestimmt"]:
                auswertung[entscheidung].sort(key=partei_sort_key)
            
        print(auswertung)
        generate_image(auswertung)


main()
    

