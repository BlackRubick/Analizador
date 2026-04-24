from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import base64
import tempfile
import os


PRIMARY       = colors.HexColor("#0D2B4E")
ACCENT        = colors.HexColor("#1A7ABA")
ACCENT_LIGHT  = colors.HexColor("#E8F4FD")
GOLD          = colors.HexColor("#C8962E")
TEXT_DARK     = colors.HexColor("#1C1C2E")
TEXT_MID      = colors.HexColor("#4A5568")
TEXT_LIGHT    = colors.HexColor("#718096")
DIVIDER       = colors.HexColor("#CBD5E0")
WHITE         = colors.white
PAGE_BG       = colors.HexColor("#F7FAFC")

MARGIN_L = 48
MARGIN_R = 48
COL_WIDTH = letter[0] - MARGIN_L - MARGIN_R



def draw_background(c, width, height):
    c.setFillColor(PAGE_BG)
    c.rect(0, 0, width, height, fill=1, stroke=0)


def draw_header(c, width, height):
    c.setFillColor(PRIMARY)
    c.rect(0, height - 72, width, 72, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.rect(0, height - 75, width, 3, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGIN_L, height - 46, "NEXO POSTURAL")

    c.setFillColor(ACCENT_LIGHT)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_L, height - 62, "Análisis Clínico Postural  ·  Reporte Profesional")

    return height - 90  # y inicial tras header


def draw_footer(c, width, page_num):
    """Pie de página con línea, marca y número de página."""
    # Línea divisora
    c.setStrokeColor(DIVIDER)
    c.setLineWidth(0.6)
    c.line(MARGIN_L, 36, width - MARGIN_R, 36)

    c.setFillColor(TEXT_LIGHT)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN_L, 22, "Nexo Postural  ·  Documento clínico confidencial")
    c.drawRightString(width - MARGIN_R, 22, f"Página {page_num}")


def draw_section_title(c, y, title, width):
    """Título de sección con banda de acento izquierdo y fondo sutil."""
    # Fondo de sección
    c.setFillColor(ACCENT_LIGHT)
    c.roundRect(MARGIN_L, y - 4, COL_WIDTH, 24, 3, fill=1, stroke=0)

    # Barra lateral de acento
    c.setFillColor(ACCENT)
    c.rect(MARGIN_L, y - 4, 4, 24, fill=1, stroke=0)

    # Texto
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN_L + 12, y + 7, title.upper())
    return y - 34  # nuevo y


def draw_patient_card(c, y, paciente, fecha, width):
    """Tarjeta con datos del paciente con diseño de ficha clínica."""
    card_h = 58
    # Sombra simulada
    c.setFillColor(DIVIDER)
    c.roundRect(MARGIN_L + 2, y - card_h - 2, COL_WIDTH, card_h, 5, fill=1, stroke=0)
    # Fondo tarjeta
    c.setFillColor(WHITE)
    c.roundRect(MARGIN_L, y - card_h, COL_WIDTH, card_h, 5, fill=1, stroke=0)
    # Franja izquierda
    c.setFillColor(ACCENT)
    c.roundRect(MARGIN_L, y - card_h, 6, card_h, 5, fill=1, stroke=0)
    c.rect(MARGIN_L, y - card_h, 3, card_h, fill=1, stroke=0)  # cuadrar borde izq

    # Etiquetas
    c.setFillColor(TEXT_LIGHT)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN_L + 16, y - 16, "PACIENTE")
    c.drawString(MARGIN_L + 230, y - 16, "FECHA")

    # Valores
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 12)
    nombre = paciente.get("nombre", "N/A")
    c.drawString(MARGIN_L + 16, y - 30, nombre)

    c.setFont("Helvetica", 11)
    c.drawString(MARGIN_L + 230, y - 30, fecha)

    # Info adicional del paciente si existe
    extras = [
        ("edad", "Edad"),
        ("sexo", "Sexo"),
        ("id", "ID"),
    ]
    ex_x = MARGIN_L + 16
    c.setFillColor(TEXT_MID)
    c.setFont("Helvetica", 8.5)
    extra_parts = [f"{label}: {paciente.get(key)}" for key, label in extras if paciente.get(key)]
    if extra_parts:
        c.drawString(ex_x, y - 46, "  ·  ".join(extra_parts))

    return y - card_h - 16


def draw_report_title_block(c, y, width):
    """Bloque de título del reporte debajo del header."""
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN_L, y, "Reporte de Análisis Clínico")
    c.setFillColor(GOLD)
    c.rect(MARGIN_L, y - 5, 44, 2, fill=1, stroke=0)
    return y - 22


def draw_metric_row(c, y, text, width, alternate=False):
    """Fila de métrica con fondo alternado tipo tabla clínica."""
    row_h = 22  # altura generosa para que respire
    padding_top = 6  # espacio interno desde el borde superior de la fila

    if alternate:
        c.setFillColor(colors.HexColor("#EDF2F7"))
        c.rect(MARGIN_L + 10, y - row_h, COL_WIDTH - 10, row_h, fill=1, stroke=0)

    # Bullet centrado verticalmente en la fila
    bullet_y = y - (row_h / 2)
    c.setFillColor(ACCENT)
    c.circle(MARGIN_L + 22, bullet_y, 2.8, fill=1, stroke=0)

    # Texto alineado verticalmente en la fila
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica", 9.5)
    c.drawString(MARGIN_L + 32, bullet_y - 3.5, text)

    return y - row_h


def new_page(c, width, height, page_num):
    """Inicia nueva página con encabezado y pie."""
    c.showPage()
    draw_background(c, width, height)
    draw_footer(c, width, page_num)
    y = draw_header(c, width, height)
    return y


# ─── FUNCIÓN PRINCIPAL ───────────────────────────────────────────────────────

def generate_report_pdf(data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    page_num = 1

    # --- Primera página ---
    draw_background(c, width, height)
    draw_footer(c, width, page_num)
    y = draw_header(c, width, height)

    y -= 10
    y = draw_report_title_block(c, y, width)
    y -= 14

    # Datos del paciente
    paciente = data.get("paciente", {})
    fecha = data.get("fecha", "N/A")
    y = draw_patient_card(c, y, paciente, fecha, width)
    y -= 10

    # Línea separadora principal
    c.setStrokeColor(DIVIDER)
    c.setLineWidth(0.8)
    c.line(MARGIN_L, y, width - MARGIN_R, y)
    y -= 18

    # --- Bloques de análisis ---
    analisis = data.get("analisis", [])

    for bloque in analisis:
        # Verificar espacio antes del título de sección
        if y < 140:
            page_num += 1
            y = new_page(c, width, height, page_num)
            y -= 10

        y = draw_section_title(c, y, bloque.get("titulo", "Análisis"), width)
        y -= 4

        # Si es Cadena miofascial y tiene tipo, mostrarlo resaltado
        if (
            "cadena" in bloque.get("titulo", "").lower()
            and bloque.get("tipo")
        ):
            c.setFillColor(GOLD)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(MARGIN_L + 16, y, f"Tipo de cadena: {bloque['tipo']}")
            y -= 22

        # Explicación
        if bloque.get("explicacion"):
            # Fondo sutil para explicación
            exp_text = bloque["explicacion"]
            c.setFillColor(colors.HexColor("#EBF8FF"))
            c.roundRect(MARGIN_L + 8, y - 18, COL_WIDTH - 8, 22, 3, fill=1, stroke=0)
            c.setFillColor(ACCENT)
            c.setFont("Helvetica-BoldOblique", 8)
            c.drawString(MARGIN_L + 16, y - 7, "Explicación:")
            c.setFillColor(TEXT_MID)
            c.setFont("Helvetica", 8.5)
            # Truncar si muy largo para la línea
            max_chars = 90
            if len(exp_text) > max_chars:
                exp_text = exp_text[:max_chars] + "…"
            c.drawString(MARGIN_L + 80, y - 7, exp_text)
            y -= 28

        # Métricas
        if bloque.get("metricas"):
            # Si es bloque de cadenas miofasciales, omitir COMPLETAMENTE el bloque de indicadores
            if "cadena" in bloque.get("titulo", "").lower():
                pass  # No mostrar nada de indicadores ni métricas
            else:
                metricas_filtradas = [met for met in bloque["metricas"] if not ("ancho" in met.lower() or "x:" in met.lower() or "y:" in met.lower())]
                if metricas_filtradas:
                    c.setFillColor(TEXT_LIGHT)
                    c.setFont("Helvetica", 7.5)
                    c.drawString(MARGIN_L + 10, y, "INDICADORES")
                    y -= 18  # espacio entre etiqueta y primera fila
                    for idx, met in enumerate(metricas_filtradas):
                        if y < 100:
                            page_num += 1
                            y = new_page(c, width, height, page_num)
                            y -= 10
                        y = draw_metric_row(c, y, met, width, alternate=(idx % 2 == 0))

        y -= 10

        # Imágenes asociadas
        imagenes = bloque.get("imagenes", [])
        for img_dict in imagenes:
            img_titulo = img_dict.get("titulo", "Imagen")
            img_b64 = img_dict.get("base64")
            if img_b64:
                try:
                    img_bytes = base64.b64decode(img_b64)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        tmp.write(img_bytes)
                        tmp.flush()

                        if y < 200:
                            page_num += 1
                            y = new_page(c, width, height, page_num)
                            y -= 10

                        img_w, img_h = 190, 130

                        # Tarjeta de imagen con borde
                        c.setStrokeColor(DIVIDER)
                        c.setLineWidth(0.8)
                        c.setFillColor(WHITE)
                        c.roundRect(MARGIN_L + 8, y - img_h - 24, img_w + 8, img_h + 22, 5, fill=1, stroke=1)

                        # Título de imagen
                        c.setFillColor(PRIMARY)
                        c.setFont("Helvetica-Bold", 8)
                        c.drawString(MARGIN_L + 16, y - 14, img_titulo)

                        # Imagen
                        c.drawImage(
                            ImageReader(tmp.name),
                            MARGIN_L + 12, y - img_h - 18,
                            width=img_w, height=img_h,
                            preserveAspectRatio=True,
                            mask='auto'
                        )
                        y -= img_h + 32
                        os.unlink(tmp.name)

                        if y < 150:
                            page_num += 1
                            y = new_page(c, width, height, page_num)
                            y -= 10

                except Exception as e:
                    c.setFillColor(colors.HexColor("#FFF5F5"))
                    c.roundRect(MARGIN_L + 8, y - 20, COL_WIDTH - 8, 20, 3, fill=1, stroke=0)
                    c.setFillColor(colors.HexColor("#C53030"))
                    c.setFont("Helvetica", 8)
                    c.drawString(MARGIN_L + 16, y - 13, f"Error al cargar imagen: {e}")
                    y -= 28

        y -= 8

        # Separador entre bloques
        c.setStrokeColor(DIVIDER)
        c.setLineWidth(0.4)
        c.setDash(3, 3)
        c.line(MARGIN_L + 20, y, width - MARGIN_R - 20, y)
        c.setDash()
        y -= 16

    # Firma / cierre de reporte
    if y < 80:
        page_num += 1
        y = new_page(c, width, height, page_num)
        y -= 10

    y -= 10
    c.setStrokeColor(DIVIDER)
    c.setLineWidth(0.6)
    c.line(MARGIN_L, y, width - MARGIN_R, y)
    y -= 16
    c.setFillColor(TEXT_LIGHT)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(MARGIN_L, y, "Este documento fue generado automáticamente por Nexo Postural.")
    c.drawRightString(width - MARGIN_R, y, f"Total de análisis: {len(analisis)}")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()