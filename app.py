import streamlit as st
import pandas as pd
from datetime import date
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

# Configuración de la página
st.set_page_config(page_title="Seguimiento de Obra - Fundación Masaveu", layout="centered")

# 1. Incorporar imagen del logo (Asegúrate de tener el archivo logo.png en GitHub)
try:
    st.image("logo.png", width=200)
except:
    st.title("🏗️ Seguimiento de Obra")

# Listas de opciones
tareas = [
    "Trazado y marcado de cajas, tubos y cuadros", "Ejecución rozas en paredes y techos",
    "Montaje de soportes", "Colocación tubos y conductos", "Tendido de cables",
    "Identificación y etiquetado", "Conexionado de cables en bornes o regletas",
    "Instalación y conexionado de mecanismos", "Fijación de carril DIN y mecanismos en cuadro eléctrico",
    "Cableado interno del cuadro eléctrico", "Configuración de equipos domóticos y/o automáticos",
    "Conexionado de sensores/actuadores de equipos domóticos/automáticos", "Pruebas de continuidad",
    "Pruebas de aislamiento", "Verificación de tierras", "Programación del automatismo", "Pruebas de funcionamiento"
]

estados = [
    "Avance de la tarea en torno al 25% aprox.", "Avance de la tarea en torno al 50% aprox.",
    "Avance de la tarea en torno al 75% aprox.", "OK, finalizado sin errores",
    "Finalizado, pero con errores pendientes de corregir", "Finalizado y corregidos los errores"
]

# Inicializar el historial en la sesión de Streamlit (Temporal)
if 'historico' not in st.session_state:
    st.session_state.historico = pd.DataFrame(columns=["Fecha", "Trabajador", "Tarea", "Estado"])

# Formulario de entrada
with st.form("registro_obra"):
    st.subheader("Nuevo Registro de Actividad")
    nombre_trabajador = st.text_input("Nombre del trabajador")
    fecha_envio = st.date_input("Fecha de envío", date.today())
    tarea_seleccionada = st.selectbox("Seleccione la tarea:", tareas)
    estado_seleccionado = st.selectbox("Estado de la tarea:", estados)
    
    submit = st.form_submit_button("Añadir al registro")

if submit:
    nuevo_dato = {
        "Fecha": fecha_envio.strftime("%d/%m/%Y"),
        "Trabajador": nombre_trabajador,
        "Tarea": tarea_seleccionada,
        "Estado": estado_seleccionado
    }
    st.session_state.historico = pd.concat([st.session_state.historico, pd.DataFrame([nuevo_dato])], ignore_index=True)
    st.success("Registro añadido localmente.")

# Mostrar tabla actual
st.write("### Registros actuales", st.session_state.historico)

# --- Generación de Excel ---
if not st.session_state.historico.empty:
    nombre_archivo = "seguimiento_obra.xlsx"
    st.session_state.historico.to_excel(nombre_archivo, index=False)
    
    with open(nombre_archivo, "rb") as f:
        st.download_button(
            label="📥 Descargar Excel",
            data=f,
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- Envío por Correo ---
    st.divider()
    st.subheader("Envío por Email")
    email_profesora = "fmo@fundacionmasaveu.com" # Cambiar por el real
    
    if st.button("📧 Enviar reporte por correo"):
        try:
            # Configuración desde Secrets
            remitente = st.secrets["EMAIL_SENDER"]
            password = st.secrets["EMAIL_PASSWORD"]
            
            msg = MIMEMultipart()
            msg['From'] = remitente
            msg['To'] = f"{email_profesora}, {remitente}"
            msg['Subject'] = f"Reporte de Obra - {nombre_trabajador}"
            
            cuerpo = f"Se adjunta el reporte de obra generado por {nombre_trabajador} el día {fecha_envio}."
            msg.attach(MIMEText(cuerpo, 'plain'))
            
            # Adjuntar archivo
            attachment = open(nombre_archivo, "rb")
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {nombre_archivo}")
            msg.attach(part)
            
            # Servidor SMTP (Ejemplo con Gmail)
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(remitente, password)
            server.send_message(msg)
            server.quit()
            
            st.success(f"Correo enviado con éxito a {email_profesora} y {remitente}")
        except Exception as e:
            st.error(f"Error al enviar el correo: {e}")
            st.info("Asegúrate de haber configurado los 'Secrets' en Streamlit.")

# --- 4. EXPORTACIÓN Y ENVÍO ---
    st.divider()
    st.dataframe(st.session_state.datos_obra)
   
    nombre_archivo = "reporte_obra.xlsx"
    st.session_state.datos_obra.to_excel(nombre_archivo, index=False)

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        with open(nombre_archivo, "rb") as f:
            st.download_button("📥 Descargar Excel", f, file_name=nombre_archivo)
    with col_b2:
        if st.button("📧 Enviar por Correo"):
            try:
                u, p, prof = st.secrets["email"]["user"], st.secrets["email"]["pass"], st.secrets["email"]["profe"]
                msg = MIMEMultipart()
                msg['From'], msg['To'], msg['Subject'] = u, f"{prof}, {u}", "Reporte Obra Actualizado"
                msg.attach(MIMEText("Se adjunta el seguimiento de obra.", 'plain'))
                with open(nombre_archivo, "rb") as a:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(a.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f"attachment; filename={nombre_archivo}")
                    msg.attach(part)
                s = smtplib.SMTP('smtp.gmail.com', 587)
                s.starttls()
                s.login(u, p)
                s.send_message(msg)
                s.quit()
                st.success("✅ Enviado correctamente.")
            except Exception as e:
                st.error(f"Error: {e}")
