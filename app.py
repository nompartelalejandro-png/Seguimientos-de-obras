import streamlit as st
import pandas as pd
from datetime import date
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO
st.set_page_config(page_title="App Seguimiento de Obra - Fundación Masaveu", layout="centered")

# Estilo personalizado para el logo y títulos
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1a4a7a; color: white; }
    </style>
    """, unsafe_allow_html=True)

# 2. INCORPORAR LOGO (Se busca archivo logo.png en el repositorio)
if os.path.exists("logo.png"):
    st.image("logo.png", width=200)
else:
    st.title("🏗️ Seguimiento de Obra")

# 3. LISTADO DE TAREAS (Según requerimientos)
tareas = [
    "Trazado y marcado de cajas, tubos y cuadros",
    "Ejecución rozas en paredes y techos",
    "Montaje de soportes",
    "Colocación tubos y conductos",
    "Tendido de cables",
    "Identificación y etiquetado",
    "Conexionado de cables en bornes o regletas",
    "Instalación y conexionado de mecanismos",
    "Fijación de carril DIN y mecanismos en cuadro eléctrico",
    "Cableado interno del cuadro eléctrico",
    "Configuración de equipos domóticos y/o automáticos",
    "Conexionado de sensores/actuadores de equipos domóticos/automáticos",
    "Pruebas de continuidad",
    "Pruebas de aislamiento",
    "Verificación de tierras",
    "Programación del automatismo",
    "Pruebas de funcionamiento"
]

# 4. LISTADO DE ESTADOS
estados = [
    "Avance de la tarea en torno al 25% aprox.",
    "Avance de la tarea en torno al 50% aprox.",
    "Avance de la tarea en torno al 75% aprox.",
    "OK, finalizado sin errores",
    "Finalizado, pero con errores pendientes de corregir",
    "Finalizado y corregidos los errores"
]

# 5. GESTIÓN DE DATOS (Sesión temporal)
if 'db_obra' not in st.session_state:
    st.session_state.db_obra = pd.DataFrame(columns=["Fecha", "Trabajador", "Tarea", "Estado"])

# 6. FORMULARIO DE ENTRADA
with st.expander("➕ Añadir Nuevo Registro", expanded=True):
    with st.form("formulario_obra"):
        col1, col2 = st.columns(2)
        with col1:
            trabajador = st.text_input("Nombre del Trabajador")
        with col2:
            fecha = st.date_input("Fecha de envío", date.today())
        
        tarea_sel = st.selectbox("Seleccione la Tarea:", tareas)
        estado_sel = st.selectbox("Estado de la Tarea:", estados)
        
        btn_add = st.form_submit_button("Registrar Tarea")

if btn_add:
    if trabajador:
        nuevo_registro = {
            "Fecha": fecha.strftime("%d/%m/%Y"),
            "Trabajador": trabajador,
            "Tarea": tarea_sel,
            "Estado": estado_sel
        }
        st.session_state.db_obra = pd.concat([st.session_state.db_obra, pd.DataFrame([nuevo_registro])], ignore_index=True)
        st.success("Registro añadido correctamente")
    else:
        st.warning("Por favor, indica el nombre del trabajador")

# 7. VISUALIZACIÓN Y DESCARGA DE EXCEL
st.subheader("📋 Registros de la Sesión")
st.dataframe(st.session_state.db_obra, use_container_width=True)

if not st.session_state.db_obra.empty:
    file_name = "seguimiento_obra.xlsx"
    st.session_state.db_obra.to_excel(file_name, index=False)
    
    with open(file_name, "rb") as f:
        st.download_button(
            label="📥 Descargar Excel al Dispositivo",
            data=f,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # 8. BOTÓN DE ENVÍO POR EMAIL (Para evitar pérdida de datos)
    st.divider()
    st.subheader("📧 Envío Seguro a la Empresa")
    st.info("Como los datos son temporales, usa este botón para enviar el Excel por correo antes de cerrar la app.")
    
    if st.button("Enviar Excel por Email"):
        try:
            # Estos datos se configuran en Streamlit Cloud -> Settings -> Secrets
            email_sender = st.secrets["EMAIL_USER"]
            email_password = st.secrets["EMAIL_PASS"]
            email_receiver = "ana@fundacionmasaveu.com"  # Mail de la profesora/empresa

            msg = MIMEMultipart()
            msg['From'] = email_sender
            msg['To'] = f"{email_receiver}, {email_sender}"
            msg['Subject'] = f"REPORTE OBRA: {trabajador} - {fecha}"
            
            body = f"Se adjunta el reporte de obra generado por {trabajador}."
            msg.attach(MIMEText(body, 'plain'))

            with open(file_name, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f"attachment; filename= {file_name}")
                msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(email_sender, email_password)
            server.send_message(msg)
            server.quit()
            
            st.success(f"✅ Enviado con éxito a {email_receiver}")
        except Exception as e:
            st.error(f"Error: No se pudo enviar el correo. Verifica los Secrets. Detalle: {e}")
