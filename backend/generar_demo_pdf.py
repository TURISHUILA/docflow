from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

# Datos extraídos (simulando lo que GPT-5.2 extraería)
datos_ce = {
    "filename": "CE_Test_001.pdf",
    "numero": "CE-2025-999",
    "fecha": "20 de Diciembre de 2025",
    "concepto": "Pago honorarios servicios de consultoría empresarial",
    "beneficiario": "Global Consulting Group SAS",
    "nit": "800.555.888-9",
    "valor": 8500000,
    "referencia": "REF-789-2025"
}

datos_cpp = {
    "filename": "CPP_Test_001.pdf",
    "numero": "CPP-2025-999",
    "fecha": "18 de Diciembre de 2025",
    "proveedor": "Global Consulting Group SAS",
    "nit": "800.555.888-9",
    "valor": 8500000,
    "vencimiento": "31 de Diciembre de 2025"
}

datos_factura = {
    "filename": "Factura_Test_001.pdf",
    "numero": "FV-9999",
    "fecha": "15 de Diciembre de 2025",
    "proveedor": "Global Consulting Group SAS",
    "nit": "800.555.888-9",
    "valor_base": 7142857,
    "iva": 1357143,
    "total": 8500000
}

datos_soporte = {
    "filename": "Soporte_Pago_Test_001.pdf",
    "banco": "Bancolombia",
    "fecha": "20 de Diciembre de 2025",
    "beneficiario": "Global Consulting Group SAS",
    "valor": 8500000,
    "referencia": "REF-789-2025",
    "estado": "TRANSACCION EXITOSA"
}

# Crear PDF
pdf_path = "/app/frontend/public/downloads/DEMO_REPORTE_FINAL.pdf"
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
story = []
styles = getSampleStyleSheet()

# Estilos personalizados
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=20,
    textColor=colors.HexColor('#1a202c'),
    spaceAfter=12,
    alignment=1
)

heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=14,
    textColor=colors.HexColor('#2d3748'),
    spaceAfter=10,
    spaceBefore=10
)

# Título
story.append(Paragraph("REPORTE CONSOLIDADO DE PAGO", title_style))
story.append(Paragraph("Consecutivo: 2025-DEMO", styles['Normal']))
story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
story.append(Spacer(1, 0.3*inch))

# Resumen Ejecutivo
story.append(Paragraph("RESUMEN EJECUTIVO", heading_style))

resumen_data = [
    ['Campo', 'Información Extraída por GPT-5.2'],
    ['Tercero/Beneficiario', 'Global Consulting Group SAS'],
    ['NIT', '800.555.888-9'],
    ['Valor Total', '$8,500,000 COP'],
    ['Concepto', 'Servicios de consultoría empresarial'],
    ['Referencia Bancaria', 'REF-789-2025'],
    ['Banco', 'Bancolombia'],
    ['Documentos Incluidos', '4 documentos'],
    ['Estado de Validación', '✓ COMPLETO']
]

resumen_table = Table(resumen_data, colWidths=[2.5*inch, 4*inch])
resumen_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 12),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 10),
    ('TOPPADDING', (0, 1), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
]))

story.append(resumen_table)
story.append(Spacer(1, 0.3*inch))

# Detalle de documentos
story.append(Paragraph("DETALLE DE DOCUMENTOS ANALIZADOS POR GPT-5.2", heading_style))
story.append(Spacer(1, 0.1*inch))

# Documento 1: Comprobante Egreso
story.append(Paragraph("1. COMPROBANTE DE EGRESO", heading_style))
doc1_data = [
    ['Campo', 'Valor Extraído por IA'],
    ['Archivo', datos_ce['filename']],
    ['Número', datos_ce['numero']],
    ['Fecha', datos_ce['fecha']],
    ['Concepto', datos_ce['concepto']],
    ['Beneficiario', datos_ce['beneficiario']],
    ['NIT', datos_ce['nit']],
    ['Valor', f"${datos_ce['valor']:,} COP"],
    ['Referencia', datos_ce['referencia']]
]

doc1_table = Table(doc1_data, colWidths=[2.5*inch, 4*inch])
doc1_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc1_table)
story.append(Spacer(1, 0.2*inch))

# Documento 2: Cuenta Por Pagar
story.append(Paragraph("2. CUENTA POR PAGAR", heading_style))
doc2_data = [
    ['Campo', 'Valor Extraído por IA'],
    ['Archivo', datos_cpp['filename']],
    ['Número', datos_cpp['numero']],
    ['Fecha', datos_cpp['fecha']],
    ['Proveedor', datos_cpp['proveedor']],
    ['NIT', datos_cpp['nit']],
    ['Valor', f"${datos_cpp['valor']:,} COP"],
    ['Vencimiento', datos_cpp['vencimiento']]
]

doc2_table = Table(doc2_data, colWidths=[2.5*inch, 4*inch])
doc2_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc2_table)
story.append(Spacer(1, 0.2*inch))

# Nueva página
story.append(PageBreak())

# Documento 3: Factura
story.append(Paragraph("3. FACTURA", heading_style))
doc3_data = [
    ['Campo', 'Valor Extraído por IA'],
    ['Archivo', datos_factura['filename']],
    ['Número', datos_factura['numero']],
    ['Fecha', datos_factura['fecha']],
    ['Proveedor', datos_factura['proveedor']],
    ['NIT', datos_factura['nit']],
    ['Valor Base', f"${datos_factura['valor_base']:,}"],
    ['IVA (19%)', f"${datos_factura['iva']:,}"],
    ['TOTAL', f"${datos_factura['total']:,} COP"]
]

doc3_table = Table(doc3_data, colWidths=[2.5*inch, 4*inch])
doc3_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc3_table)
story.append(Spacer(1, 0.2*inch))

# Documento 4: Soporte de Pago
story.append(Paragraph("4. SOPORTE DE PAGO", heading_style))
doc4_data = [
    ['Campo', 'Valor Extraído por IA'],
    ['Archivo', datos_soporte['filename']],
    ['Banco', datos_soporte['banco']],
    ['Fecha', datos_soporte['fecha']],
    ['Beneficiario', datos_soporte['beneficiario']],
    ['Valor', f"${datos_soporte['valor']:,} COP"],
    ['Referencia', datos_soporte['referencia']],
    ['Estado', datos_soporte['estado']]
]

doc4_table = Table(doc4_data, colWidths=[2.5*inch, 4*inch])
doc4_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#718096')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(doc4_table)
story.append(Spacer(1, 0.3*inch))

# Nueva página para validaciones
story.append(PageBreak())

# Validaciones
story.append(Paragraph("VALIDACIONES Y VERIFICACIONES AUTOMÁTICAS", heading_style))
story.append(Spacer(1, 0.1*inch))

validaciones = [
    ['Estado', 'Validación', 'Detalle'],
    ['✓', 'Consistencia de Valores', 'Todos los documentos reportan: $8,500,000 COP'],
    ['✓', 'Consistencia de Tercero', 'Beneficiario: Global Consulting Group SAS (NIT: 800.555.888-9)'],
    ['✓', 'Completitud', 'Los 4 tipos de documentos están presentes'],
    ['✓', 'Correlación Bancaria', 'Referencia REF-789-2025 coincide entre CE y Soporte'],
    ['✓', 'Validación de Fechas', 'Fechas consistentes: 15-20 de Diciembre 2025'],
    ['✓', 'Banco Verificado', 'Bancolombia - Transacción exitosa']
]

val_table = Table(validaciones, colWidths=[0.6*inch, 2.4*inch, 3.5*inch])
val_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#48bb78')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
    ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0fff4')),
    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#48bb78')),
    ('FONTSIZE', (0, 1), (-1, -1), 9),
    ('TOPPADDING', (0, 1), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
]))

story.append(val_table)
story.append(Spacer(1, 0.3*inch))

# Conclusión
story.append(Paragraph("CONCLUSIÓN Y RECOMENDACIÓN", heading_style))
conclusion_text = """
<b>Resultado del Análisis Automático con GPT-5.2:</b><br/>
Los 4 documentos fueron procesados exitosamente. La información extraída es consistente 
y todas las validaciones se superaron satisfactoriamente.<br/><br/>
<b>Pago:</b> $8,500,000 COP<br/>
<b>Beneficiario:</b> Global Consulting Group SAS (NIT: 800.555.888-9)<br/>
<b>Referencia:</b> REF-789-2025<br/><br/>
<b style="color: green;">✓ RECOMENDACIÓN: APROBAR PAGO</b><br/>
<b>Motivo:</b> Documentación completa, valores consistentes, transacción bancaria exitosa.
"""
story.append(Paragraph(conclusion_text, styles['Normal']))

# Pie de página
story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("_" * 90, styles['Normal']))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph("<b>Generado por:</b> Administrador (admin@docflow.com)", styles['Normal']))
story.append(Paragraph("<b>Sistema:</b> DocFlow - Gestión Documental Inteligente", styles['Normal']))
story.append(Paragraph("<b>Tecnología IA:</b> GPT-5.2 con Clave Universal Emergent", styles['Normal']))
story.append(Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d de %B de %Y, %H:%M')}", styles['Normal']))

# Construir PDF
doc.build(story)

print(f"✓ PDF de demostración generado exitosamente")
print(f"  Ubicación: {pdf_path}")
print(f"  Contenido: Reporte consolidado con información extraída por GPT-5.2")
