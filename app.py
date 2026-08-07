import streamlit as st
import pypdf
import re

st.set_page_config(page_title="Extractor Nu -> Moneda.pro", page_icon="💳", layout="centered")

st.title("💳 Extractor Nu a Moneda.pro")
st.write("Sube tu estado de cuenta en PDF para generar el mensaje en el formato recomendado por Moneda.pro.")

PROD_DAYANA_KEYWORDS = [
    "abts el mayorista", 
    "teip impresiones", 
    "abts ctrl mayorista pr", 
    "envases y plasticos", 
    "abts el mayorista mark", 
    "abts guga ensenada", 
    "ley ensenada"
]

MONTHS_MAP = {
    'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06',
    'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
}

MONTHS_NAME = {
    '01': 'ENERO', '02': 'FEBRERO', '03': 'MARZO', '04': 'ABRIL', '05': 'MAYO', '06': 'JUNIO',
    '07': 'JULIO', '08': 'AGOSTO', '09': 'SEPTIEMBRE', '10': 'OCTUBRE', '11': 'NOVIEMBRE', '12': 'DICIEMBRE'
}

uploaded_file = st.file_uploader("Arrastra o selecciona aquí tu PDF de NU", type=["pdf"])

if uploaded_file is not None:
    reader = pypdf.PdfReader(uploaded_file)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    # 1. Identificar Fecha de Corte (Búsqueda más flexible con o sin caracteres especiales)
    corte_match = re.search(r'Fecha de corte:?\s*\|?\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', full_text, re.IGNORECASE)
    
    if corte_match:
        dia_corte = corte_match.group(1)
        mes_corte_str = corte_match.group(2).upper()
        anio_corte = corte_match.group(3)
        
        mes_num = MONTHS_MAP.get(mes_corte_str, '01')
        nombre_mes = MONTHS_NAME.get(mes_num, mes_corte_str)
        
        st.success(f"📅 **Fecha de corte:** {dia_corte} {mes_corte_str} {anio_corte} | Filtrando gastos de **{nombre_mes}**")

        # 2. Extraer transacciones
        pattern = re.compile(r'(\d{2}\s+[A-Z]{3}\s+\d{4})\s+(\d{2}\s+[A-Z]{3}\s+\d{4})\s+(.*?)\s+([\+\-]\$[\d,]+\.\d{2})')
        matches = pattern.findall(full_text)

        gastos_lineas = []

        for m in matches:
            fecha_op, fecha_cargo, desc, monto = m
            desc_clean = desc.split('|')[0].strip()
            
            # Solo cargos / egresos (+)
            if monto.startswith('+$'):
                d, mon, y = fecha_op.split()
                # Filtrar solo las transacciones del mes de corte
                if mon.upper() == mes_corte_str:
                    formatted_date = f"{y}-{MONTHS_MAP.get(mon.upper(), '01')}-{d}"
                    
                    # Limpiar prefijos de extracción si existen
                    d_clean = re.sub(r'^(88\s*|Ztl\*|Sgt\*)', '', desc_clean).strip()
                    d_lower = d_clean.lower()
                    
                    # Regla de categoría
                    has_cat = any(kw in d_lower for kw in PROD_DAYANA_KEYWORDS)
                    categoria = "Produccion Dayana" if has_cat else "Varios"
                    
                    monto_val = monto.replace('+$', '').replace(',', '').strip()
                    # Formato: Gasto, $monto, Categoría, NU (CREDITO), YYYY-MM-DD, Descripción
                    line_str = f"Gasto, ${monto_val}, {categoria}, NU (CREDITO), {formatted_date}, {d_clean}"
                    gastos_lineas.append(line_str)

        if gastos_lineas:
            encabezado = f"Hola Moneda, registra los siguientes gastos correspondientes a mi tarjeta NU de {nombre_mes} {anio_corte}:\n\n"
            mensaje_final = encabezado + "\n".join(gastos_lineas)

            st.subheader("📝 Mensaje listo para enviar por WhatsApp")
            st.text_area("Copia el texto de abajo:", mensaje_final, height=400)
            st.info(f"💡 Total de egresos procesados: **{len(gastos_lineas)}**")
        else:
            st.warning(f"No se encontraron gastos pertenecientes al mes de {nombre_mes}.")
    else:
        st.error("No se pudo detectar la Fecha de Corte en el PDF subido.")
