import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from pypdf import PdfReader
from io import StringIO
from streamlit_gsheets import GSheetsConnection
from pdf_generator import generar_pdf_reporte

st.set_page_config(page_title="Finanzas Dayana", layout="wide")

# Conexión con Google Sheets (Base de Datos)
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        df = conn.read(worksheet="Movimientos", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion'])
        
        df.columns = df.columns.str.strip().str.replace('Categoría', 'Categoria').str.replace('Método_Pago', 'Metodo_Pago')
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce').dt.date
        df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        df = df.dropna(subset=['Fecha'])
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion'])

df_base = cargar_datos()

# --- LÓGICA DE EXTRACCIÓN (NU Y ODOO) ---
def categorizar_nu(descripcion):
    desc_lower = str(descripcion).lower()
    keywords_dayana = [
        "abts el mayorista", "teip impresiones", "abts ctrl mayorista pr",
        "envases y plasticos", "abts el mayorista mark", "abts guga ensenada", "ley ensenada"
    ]
    for kw in keywords_dayana:
        if kw in desc_lower:
            return "Produccion Dayana"
    return "Varios"

def procesar_pdf_nu(file):
    reader = PdfReader(file)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    # Extraer Fecha de Corte para definir Año-Mes
    corte_match = re.search(r"Fecha de corte:\s*(\d{2})\s+([A-Za-z]+)\s+(\d{4})", texto_completo, re.IGNORECASE)
    meses = {"ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06", 
             "jul": "07", "ago": "08", "sep": "09", "oct": "10", "nov": "11", "dic": "12"}
    
    if corte_match:
        ano = corte_match.group(3)
        mes_str = corte_match.group(2)[:3].lower()
        mes = meses.get(mes_str, "01")
    else:
        ano = str(datetime.now().year)
        mes = f"{datetime.now().month:02d}"

    # Patrón de extracción de cargos
    patron_cargo = r"(\d{2}\s+[A-Za-z]{3})\s+(.*?)\s+\$\s*([\d,]+\.\d{2})"
    coincidencias = re.findall(patron_cargo, texto_completo)
    
    registros = []
    for dia_mes, desc, monto_str in coincidencias:
        monto = float(monto_str.replace(",", ""))
        if monto > 0 and "pago recibido" not in desc.lower():
            dia = dia_mes.split()[0].zfill(2)
            fecha_fmt = f"{ano}-{mes}-{dia}"
            cat = categorizar_nu(desc)
            registros.append({
                "Tipo": "Gasto",
                "Monto": monto,
                "Categoria": cat,
                "Metodo_Pago": "NU (CREDITO)",
                "Fecha": fecha_fmt,
                "Descripcion": desc.strip()
            })
    return pd.DataFrame(registros)

def procesar_csv_odoo(file):
    df_odoo = pd.read_csv(file)
    registros = []
    for _, row in df_odoo.iterrows():
        cliente = str(row.get("Cliente", "")).strip()
        ref_orden = str(row.get("Referencia de la orden", "")).strip()
        ref_cliente = str(row.get("Referencia del cliente", "")).strip()
        monto = float(row.get("Total", 0))
        fecha_raw = str(row.get("Fecha de creacion", row.get("Fecha de creación", datetime.now().strftime("%Y-%m-%d"))))
        
        fecha_fmt = fecha_raw.split()[0]
        desc = f"{cliente} - {ref_orden} - {ref_cliente}".strip(" -")
        
        registros.append({
            "Tipo": "Ingreso",
            "Monto": monto,
            "Categoria": "Ventas",
            "Metodo_Pago": "Efectivo",
            "Fecha": fecha_fmt,
            "Descripcion": desc
        })
    return pd.DataFrame(registros)

# --- NAVEGACIÓN EN SIDEBAR ---
st.sidebar.title("📌 Navegación")
pagina = st.sidebar.radio("Ir a:", ["📊 Dashboard Financiero", "📄 Extractor Nu / Odoo"])

# ==========================================
# PÁGINA 1: DASHBOARD FINANCIERO
# ==========================================
if pagina == "📊 Dashboard Financiero":
    st.title("Analiza tus finanzas con reportes detallados")
    st.caption("Visualiza todas tus transacciones organizadas por fecha, categoría y tipo")

    # FILTROS
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        atajo = st.selectbox("Atajo de Período", ["Personalizado", "Hoy", "Esta semana", "Este mes", "Últimos 3 meses"])
        hoy = datetime.now().date()
        if atajo == "Hoy":
            f_ini, f_fin = hoy, hoy
        elif atajo == "Esta semana":
            f_ini = hoy - timedelta(days=hoy.weekday())
            f_fin = f_ini + timedelta(days=6)
        elif atajo == "Este mes":
            f_ini = hoy.replace(day=1)
            f_fin = hoy
        elif atajo == "Últimos 3 meses":
            f_ini = hoy - timedelta(days=90)
            f_fin = hoy
        else:
            f_ini = hoy.replace(day=1)
            f_fin = hoy

    with col_f2:
        f_inicio = st.date_input("Fecha Inicio", value=f_ini)
        f_final = st.date_input("Fecha Fin", value=f_fin)

    with col_f3:
        filtro_tipo = st.selectbox("Tipo de Registro", ["TODOS", "Ingreso", "Gasto"])

    categorias_opts = ["TODAS"] + sorted(list(df_base['Categoria'].dropna().unique())) if not df_base.empty else ["TODAS"]
    with col_f4:
        filtro_cat = st.selectbox("Categoría", categorias_opts)

    # APLICAR FILTROS
    df_filtrado = df_base.copy()
    if not df_filtrado.empty:
        df_filtrado = df_filtrado[(df_filtrado['Fecha'] >= f_inicio) & (df_filtrado['Fecha'] <= f_final)]
        if filtro_tipo != "TODOS":
            df_filtrado = df_filtrado[df_filtrado['Tipo'] == filtro_tipo]
        if filtro_cat != "TODAS":
            df_filtrado = df_filtrado[df_filtrado['Categoria'] == filtro_cat]

    # CÁLCULOS
    ingresos = df_filtrado[df_filtrado['Tipo'] == 'Ingreso']['Monto'].sum() if not df_filtrado.empty else 0.0
    egresos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']['Monto'].sum() if not df_filtrado.empty else 0.0
    balance = ingresos - egresos

    # EXPORTACIÓN
    col_exp1, col_exp2 = st.columns(2)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with col_exp1:
        csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar CSV", data=csv_data, file_name=f"reporte_{f_inicio}_a_{f_final}_{timestamp}.csv", mime="text/csv", use_container_width=True)

    with col_exp2:
        if not df_filtrado.empty:
            pdf_bytes = generar_pdf_reporte(df_filtrado, f_inicio, f_final, ingresos, egresos, balance)
            st.download_button("📄 Exportar PDF", data=pdf_bytes, file_name=f"reporte_{f_inicio}_a_{f_final}_{timestamp}.pdf", mime="application/pdf", use_container_width=True)

    st.markdown("---")

    # SCORECARDS
    c_ing, c_egr, c_bal = st.columns(3)
    c_ing.metric("TOTAL DE INGRESOS", f"${ingresos:,.2f}")
    c_egr.metric("TOTAL DE EGRESOS", f"-${egresos:,.2f}")
    c_bal.metric("BALANCE DEL PERÍODO", f"${balance:,.2f}")

    st.markdown(f"### Lista de Transacciones ({len(df_filtrado)} registros)")
    st.dataframe(df_filtrado, use_container_width=True)

# ==========================================
# PÁGINA 2: EXTRACTOR NU / ODOO
# ==========================================
else:
    st.title("Extracción y Registro de Gastos e Ingresos")
    st.caption("Carga tus PDFs de Nu o CSVs de Odoo para transformarlos automáticamente al formato TSV de Google Sheets.")

    tab1, tab2 = st.tabs(["💳 Estado de Cuenta Nu (PDF)", "🛍️ Ventas Odoo (CSV)"])
    
    # PESTAÑA NU
    with tab1:
        st.subheader("Extraer Egresos desde PDF Nu")
        pdf_file = st.file_uploader("Sube tu Estado de Cuenta Nu en PDF", type=["pdf"], key="pdf_nu")
        if pdf_file:
            try:
                df_extracted_nu = procesar_pdf_nu(pdf_file)
                if not df_extracted_nu.empty:
                    st.success(f"Se extrajeron {len(df_extracted_nu)} cargos correctamente.")
                    
                    # Salida interactiva editable
                    df_edited = st.data_editor(df_extracted_nu, num_rows="dynamic", use_container_width=True)
                    
                    # Generar TSV
                    tsv_data = df_edited.to_csv(index=False, sep='\t', header=False)
                    st.markdown("#### Formato TSV para copiar y pegar en Sheets:")
                    st.code(tsv_data, language="text")
                    
                    # Botón de guardado directo a Sheets
                    if st.button("🚀 Guardar estos registros directamente en Google Sheets", key="btn_nu"):
                        df_total = pd.concat([df_base, df_edited], ignore_index=True)
                        conn.update(worksheet="Movimientos", data=df_total)
                        st.success("¡Egresos añadidos con éxito a la base de datos de Google Sheets!")
                        st.rerun()
                else:
                    st.warning("No se encontraron cargos positivos en el archivo subido.")
            except Exception as e:
                st.error(f"Error al procesar el PDF: {e}")

    # PESTAÑA ODOO
    with tab2:
        st.subheader("Extraer Ingresos desde CSV Odoo")
        csv_file = st.file_uploader("Sube tu archivo de ventas Odoo en CSV", type=["csv"], key="csv_odoo")
        if csv_file:
            try:
                df_extracted_odoo = procesar_csv_odoo(csv_file)
                if not df_extracted_odoo.empty:
                    st.success(f"Se extrajeron {len(df_extracted_odoo)} ventas correctamente.")
                    
                    # Salida interactiva editable
                    df_edited_odoo = st.data_editor(df_extracted_odoo, num_rows="dynamic", use_container_width=True)
                    
                    # Generar TSV
                    tsv_data_odoo = df_edited_odoo.to_csv(index=False, sep='\t', header=False)
                    st.markdown("#### Formato TSV para copiar y pegar en Sheets:")
                    st.code(tsv_data_odoo, language="text")
                    
                    # Botón de guardado directo a Sheets
                    if st.button("🚀 Guardar estas ventas directamente en Google Sheets", key="btn_odoo"):
                        df_total = pd.concat([df_base, df_edited_odoo], ignore_index=True)
                        conn.update(worksheet="Movimientos", data=df_total)
                        st.success("¡Ventas añadidas con éxito a la base de datos de Google Sheets!")
                        st.rerun()
            except Exception as e:
                st.error(f"Error al procesar el CSV: {e}")
