"""Gerador de Faturas Eletrónicas e Recibos de Proveniência em PDF de Alto Calibre.
Utiliza ReportLab para compor documentos fiscais e comprovativos criptográficos.
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


def generate_invoice_pdf(
    invoice_number: str,
    title: str,
    seller_name: str,
    seller_contact: str,
    seller_location: str | None,
    buyer_name: str | None,
    buyer_contact: str | None,
    item_description: str,
    item_category: str,
    price_formatted: str,
    currency_code: str = "MZN",
    b2_key: str | None = None,
    sha256_hash: str | None = None,
    created_at: str | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Estilos customizados de alto nível
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
    )
    subtitle_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748B'),
    )
    header_right = ParagraphStyle(
        'HeaderRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#2563EB'),
    )
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
    )
    value_style = ParagraphStyle(
        'Value',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A'),
    )
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white,
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
    )
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#94A3B8'),
    )

    elements = []

    # Cabeçalho da Fatura
    header_data = [
        [
            Paragraph("<b>BOLADAS.COM</b><br/><font size=8 color='#64748B'>Marketplace & Proveniência Digital Internacional</font>", title_style),
            Paragraph(f"FATURA ELETRÓNICA<br/><font size=9 color='#475569'>Nº {invoice_number}</font>", header_right),
        ]
    ]
    t_header = Table(header_data, colWidths=[320, 200])
    t_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(t_header)
    elements.append(Spacer(1, 15))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceAfter=15))

    # Meta informações (Data, Estado, Proveniência)
    issue_date = created_at or datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    meta_data = [
        [
            Paragraph("<b>Data de Emissão:</b>", label_style), Paragraph(issue_date, value_style),
            Paragraph("<b>Moeda de Liquidação:</b>", label_style), Paragraph(currency_code, value_style),
        ],
        [
            Paragraph("<b>Estado Fiscal:</b>", label_style), Paragraph("<font color='#16A34A'><b>PROCESSADO / CONFIRMADO</b></font>", value_style),
            Paragraph("<b>Segurança:</b>", label_style), Paragraph("Provável Backblaze B2 (SHA-256)", value_style),
        ]
    ]
    t_meta = Table(meta_data, colWidths=[110, 150, 120, 140])
    t_meta.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 2)]))
    elements.append(t_meta)
    elements.append(Spacer(1, 15))

    # Dados do Vendedor e Comprador
    parties_data = [
        [
            Paragraph("<b>DADOS DO VENDEDOR / ENTIDADE</b>", label_style),
            Paragraph("<b>DADOS DO CLIENTE / COMPRADOR</b>", label_style),
        ],
        [
            Paragraph(f"<b>{seller_name}</b><br/>Contactos: {seller_contact}<br/>Localização: {seller_location or 'Moçambique / Internacional'}", value_style),
            Paragraph(f"<b>{buyer_name or 'Cliente Geral / Consumidor Final'}</b><br/>Contactos: {buyer_contact or 'N/D'}", value_style),
        ]
    ]
    t_parties = Table(parties_data, colWidths=[260, 260])
    t_parties.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(t_parties)
    elements.append(Spacer(1, 20))

    # Tabela de Itens / Detalhe da Transação
    items_header = [
        Paragraph("Item / Descrição do Produto", table_header),
        Paragraph("Categoria", table_header),
        Paragraph("Preço Unitário", table_header),
        Paragraph("Total", table_header),
    ]

    items_row = [
        Paragraph(f"<b>{title}</b><br/><font size=8 color='#64748B'>{item_description[:120] + ('...' if len(item_description) > 120 else '')}</font>", table_cell),
        Paragraph(item_category, table_cell),
        Paragraph(price_formatted, table_cell),
        Paragraph(f"<b>{price_formatted}</b>", table_cell),
    ]

    t_items = Table([items_header, items_row], colWidths=[240, 100, 90, 90])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 15))

    # Totais
    totals_data = [
        [Paragraph("Subtotal:", label_style), Paragraph(price_formatted, ParagraphStyle('R', parent=value_style, alignment=TA_RIGHT))],
        [Paragraph("Impostos / Taxas (0% Exento/Incl.):", label_style), Paragraph(f"0.00 {currency_code}", ParagraphStyle('R', parent=value_style, alignment=TA_RIGHT))],
        [Paragraph("<b>TOTAL GERAL:</b>", ParagraphStyle('L', parent=label_style, fontSize=11)), Paragraph(f"<b>{price_formatted}</b>", ParagraphStyle('R', parent=label_style, fontSize=11, alignment=TA_RIGHT, textColor=colors.HexColor('#2563EB')))],
    ]
    t_totals = Table(totals_data, colWidths=[380, 140])
    t_totals.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_totals)
    elements.append(Spacer(1, 20))

    # Prova Criptográfica de Registos B2
    if b2_key or sha256_hash:
        prov_text = f"<b>PROVA DE PROVENIÊNCIA DIGITADA (BACKBLAZE B2)</b><br/>"
        if b2_key:
            prov_text += f"Storage Key: <code>{b2_key}</code><br/>"
        if sha256_hash:
            prov_text += f"SHA-256 Checksum: <code>{sha256_hash}</code>"

        prov_table = Table([[Paragraph(prov_text, ParagraphStyle('P', parent=subtitle_style, fontSize=8, leading=11))]], colWidths=[520])
        prov_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        elements.append(prov_table)
        elements.append(Spacer(1, 20))

    # Rodapé Internacional
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=10))
    elements.append(Paragraph(
        "Fatura Emitida Eletronicamente via Boladas.com · Documento válido para verificação comercial e proveniência de produtos · Suporte: +258 872599084",
        footer_style
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
