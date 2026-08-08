import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from pdf_generator import generar_pdf_reporte

st.set_page_config(page_title="Dashboard Financiero Dayana", layout="wide")

# Conexión con Google Sheets (Base de Datos)
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    df = conn.read(worksheet="Movimientos", ttl=0)
    if df.empty:
        return pd.DataFrame(columns=['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion'])
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date
    df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
    return df

df_base = cargar_datos()

# Sidebar: Cargar nuevos registros semanal/mensual
st.sidebar.title("📥 Cargar Movimientos")
opcion_carga = st.sidebar.radio("Fuente de datos:", ["Formato TSV / Pegado directo", "Extraer PDF Nu / CSV Odoo"])

if opcion_carga == "Formato TSV / Pegado directo":
    raw_tsv = st.sidebar.text_area("Pega aquí las filas en formato TSV (de tu app de extracción):")
    if st.sidebar.button("Guardar en Base de Datos"):
        if raw_tsv.strip():
            # Procesar datos pegados
            from io import StringIO
            df_nuevos = pd.read_csv(StringIO(raw_tsv), sep='\t', names=['Tipo', 'Monto', 'Categoria', 'Metodo_Pago', 'Fecha', 'Descripcion'])
            df_total = pd.concat([df_base, df_nuevos], ignore_index=True)
            conn.update(worksheet="Movimientos", data=df_total)
            st.sidebar.success("¡Registros guardados en Google Sheets exitosamente!")
            st.rerun()

# --- HEADER DEL DASHBOARD ---
st.title("Analiza tus finanzas con reportes detallados")
st.caption("Visualiza todas tus transacciones organizadas por fecha, categoría y tipo")

# --- SECCIÓN DE FILTROS ---
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

with col_f4:
    categorias_opts = ["TODAS"] + list(df_base['Categoria'].dropna().unique()) if not df_base.empty else ["TODAS"]
    filtro_cat = st.selectbox("Categoría", categorias_opts)

# Aplicar Filtros
df_filtrado = df_base.copy()
if not df_filtrado.empty:
    df_filtrado = df_filtrado[(df_filtrado['Fecha'] >= f_inicio) & (df_filtrado['Fecha'] <= f_final)]
    if filtro_tipo != "TODOS":
        df_filtrado = df_filtrado[df_filtrado['Tipo'] == filtro_tipo]
    if filtro_cat != "TODAS":
        df_filtrado = df_filtrado[df_filtrado['Categoria'] == filtro_cat]

# CÁLCULO DE INDICADORES
ingresos = df_filtrado[df_filtrado['Tipo'] == 'Ingreso']['Monto'].sum() if not df_filtrado.empty else 0.0
egresos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']['Monto'].sum() if not df_filtrado.empty else 0.0
balance = ingresos - egresos

# --- BOTONES DE EXPORTACIÓN Y INDICADORES ---
col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_csv = f"reporte_{f_inicio}_a_{f_final}_{timestamp}.csv"
    st.download_button("📥 Exportar CSV", data=csv_data, file_name=nombre_csv, mime="text/csv", use_container_width=True)

with col_exp2:
    if not df_filtrado.empty:
        pdf_bytes = generar_pdf_reporte(df_filtrado, f_inicio, f_final, ingresos, egresos, balance)
        nombre_pdf = f"reporte_{f_inicio}_a_{f_final}_{timestamp}.pdf"
        st.download_button("📄 Exportar PDF", data=pdf_bytes, file_name=nombre_pdf, mime="application/pdf", use_container_width=True)

st.markdown("---")

# SCORECARDS PRINCIPALES
c_ing, c_egr, c_bal = st.columns(3)
c_ing.metric("TOTAL DE INGRESOS", f"${ingresos:,.2f}")
c_egr.metric("TOTAL DE EGRESOS", f"-${egresos:,.2f}")
c_bal.metric("BALANCE DEL PERÍODO", f"${balance:,.2f}")

st.markdown("### Lista de Transacciones")
st.dataframe(df_filtrado, use_container_width=True)
