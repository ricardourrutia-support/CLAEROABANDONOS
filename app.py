import streamlit as st
import pandas as pd
import re
import io

# --- FUNCIONES DE LIMPIEZA ---
def clean_ticket(ticket_str):
    """Extrae solo el número de ticket (ignora # o links)."""
    if pd.isna(ticket_str): return ""
    numbers = re.findall(r'\d+', str(ticket_str))
    if numbers: return numbers[-1]
    return ticket_str

def clean_monto(monto_str):
    """Limpia los montos quitando $, puntos y espacios."""
    if pd.isna(monto_str): return ""
    return str(monto_str).replace('$', '').replace('.', '').replace(',', '').strip()

# --- FUNCIONES DE PROCESAMIENTO ---
def procesar_saldos(df):
    df.columns = df.columns.str.strip()
    
    renames = {
        'Marca temporal': 'Datetime Compensación',
        'Numero ticket': 'Numero',
        'Numero de reserva': 'Id_reserva'
    }
    df = df.rename(columns=renames)
    
    if 'Numero' in df.columns:
        df['Numero'] = df['Numero'].apply(clean_ticket)
    if 'Monto a compensar' in df.columns:
        df['Monto a compensar'] = df['Monto a compensar'].apply(clean_monto)
        
    df['Compensación Aeropuerto'] = 'Saldo (Aeropuerto)'
    
    if 'Id_reserva' in df.columns:
        df['Id_reserva'] = df['Id_reserva'].astype(str).str.strip()
    
    return df

def procesar_transferencias(df):
    # 1. Eliminar columnas duplicadas/vacías específicas ANTES de limpiar espacios
    columnas_a_eliminar = ['Fecha', 'Monto '] 
    df = df.drop(columns=[col for col in columnas_a_eliminar if col in df.columns])
    
    # 2. Limpiar espacios de las columnas restantes
    df.columns = df.columns.str.strip() 
    
    # Filtros de motivos
    if 'Motivo' in df.columns:
        df = df[df['Motivo'].astype(str).str.strip() == 'Compensación Aeropuerto']
    
    motivos_validos = ["Usuario pierde el vuelo", "Reserva no encuentra conductor o no llega el conductor"]
    if 'Si es compensación Aeropuerto selecciona el motivo' in df.columns:
        df = df[df['Si es compensación Aeropuerto selecciona el motivo'].astype(str).str.strip().isin(motivos_validos)]
        
    renames = {
        'Fecha': 'Datetime Compensación',
        'Ticket': 'Numero',
        'Correo': 'Correo registrado en Cabify para realizar la carga',
        'Monto': 'Monto a compensar',
        'Si es compensación Aeropuerto selecciona el motivo': 'Motivo compensación',
        'Link payments, link del viaje o numero reserva': 'Id_reserva'
    }
    df = df.rename(columns=renames)
    
    if 'Numero' in df.columns: 
        df['Numero'] = df['Numero'].apply(clean_ticket)
    if 'Monto a compensar' in df.columns: 
        df['Monto a compensar'] = df['Monto a compensar'].apply(clean_monto)
        
    df['Compensación Aeropuerto'] = 'Transferencia (Aeropuerto)'
    
    if 'Id_reserva' in df.columns:
        df['Id_reserva'] = df['Id_reserva'].astype(str).str.strip()
        
    return df

def procesar_transacciones(lista_dfs):
    df_trans = pd.concat(lista_dfs, ignore_index=True)
    df_trans.columns = df_trans.columns.str.strip()
    
    if 'F.Hacia Aerop' in df_trans.columns:
        df_trans = df_trans.dropna(subset=['F.Hacia Aerop'])
        df_trans = df_trans[df_trans['F.Hacia Aerop'].astype(str).str.strip() != '']
    
    df_trans = df_trans.rename(columns={
        'Id Reserva': 'Id_reserva',
        'F.Hacia Aerop': 'Tm_start_local_at'
    })
    
    if 'Id_reserva' in df_trans.columns:
        df_trans['Id_reserva'] = df_trans['Id_reserva'].astype(str).str.strip()
    
    cols_to_keep = [c for c in ['Id_reserva', 'Tm_start_local_at'] if c in df_trans.columns]
    return df_trans[cols_to_keep]


# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Cruce Compensaciones", layout="wide")
st.title("✈️ Cruce de Compensaciones Aeropuerto vs Transacciones")

st.markdown("### 1. Sube los archivos de Compensaciones")
col1, col2 = st.columns(2)

with col1: archivo_saldos = st.file_uploader("Archivo de Saldos (Excel)", type=['xlsx'])
with col2: archivo_transf = st.file_uploader("Archivo de Transferencias (Excel)", type=['xlsx'])

st.markdown("### 2. Sube los archivos de Transacciones (CSV)")
archivos_transacciones = st.file_uploader("Archivos de Transacciones (Múltiples)", type=['csv'], accept_multiple_files=True)

with st.expander("🛠️ Diagnóstico de Archivos (Clic para expandir)"):
    st.write("Verifica si la app está leyendo correctamente las columnas.")
    try:
        if archivo_saldos:
            st.success("✅ Archivo de Saldos cargado.")
            archivo_saldos.seek(0) 
        if archivo_transf:
            st.success("✅ Archivo de Transferencias cargado.")
            archivo_transf.seek(0)
        if archivos_transacciones:
            st.success(f"✅ {len(archivos_transacciones)} Archivo(s) de Transacciones cargado(s).")
            archivos_transacciones[0].seek(0)
    except Exception as e:
        st.error(f"Error al leer archivo: {e}")

if st.button("Procesar y Cruzar Datos", type="primary"):
    if archivo_saldos and archivo_transf and archivos_transacciones:
        try:
            with st.spinner('Procesando datos...'):
                # Lectura
                df_saldos = pd.read_excel(archivo_saldos)
                df_transf = pd.read_excel(archivo_transf)
                lista_trans = [pd.read_csv(f) for f in archivos_transacciones]
                
                # Procesamiento
                df_saldos = procesar_saldos(df_saldos)
                df_transf = procesar_transferencias(df_transf)
                df_trans = procesar_transacciones(lista_trans)
                
                columnas_requeridas = [
                    'Datetime Compensación', 'Dirección de correo electrónico', 'Numero', 
                    'Correo registrado en Cabify para realizar la carga', 'Monto a compensar', 
                    'Motivo compensación', 'Id_reserva', 'Compensación Aeropuerto'
                ]
                
                # Advertencias si faltan columnas
                faltantes_saldos = [c for c in columnas_requeridas if c not in df_saldos.columns]
                if faltantes_saldos: st.warning(f"⚠️ A SALDOS le faltan estas columnas: {faltantes_saldos}")
                    
                df_saldos = df_saldos[[c for c in columnas_requeridas if c in df_saldos.columns]]
                df_transf = df_transf[[c for c in columnas_requeridas if c in df_transf.columns]]
                
                # Unir saldos y transferencias
                df_compensaciones = pd.concat([df_saldos, df_transf], ignore_index=True)
                
                if 'Id_reserva' not in df_compensaciones.columns or 'Id_reserva' not in df_trans.columns:
                    st.error("🚨 Error crítico: No se encontró la columna 'Id_reserva', no se puede hacer el cruce.")
                    st.stop()
                
                # Cruce final
                df_final = pd.merge(df_compensaciones, df_trans, on='Id_reserva', how='inner')
                
                # --- LÓGICA DE PARSEO DE FECHA Y HORA ROBUSTA ---
                if 'Tm_start_local_at' in df_final.columns:
                    # Limpieza extrema de espacios duros y AM/PM
                    tm_clean = df_final['Tm_start_local_at'].astype(str)
                    tm_clean = tm_clean.str.replace(r'\xa0', ' ', regex=True)
                    tm_clean = tm_clean.str.replace(r'[aA]\.?\s*[mM]\.?', 'AM', regex=True)
                    tm_clean = tm_clean.str.replace(r'[pP]\.?\s*[mM]\.?', 'PM', regex=True)
                    
                    # Conversión a datetime (Con format='mixed' para casos raros sin AM/PM)
                    try:
                        df_final['Tm_dt'] = pd.to_datetime(tm_clean, errors='coerce', dayfirst=True, format='mixed')
                    except ValueError:
                        df_final['Tm_dt'] = pd.to_datetime(tm_clean, errors='coerce', dayfirst=True)
                    
                    # Fecha como objeto real y Hora como entero puro
                    df_final['Fecha'] = df_final['Tm_dt'].dt.date
                    df_final['Hora'] = df_final['Tm_dt'].dt.hour.astype('Int64')
                
                # Ordenar columnas finales
                columnas_finales = columnas_requeridas + ['Tm_start_local_at', 'Fecha', 'Hora']
                df_final = df_final[[c for c in columnas_finales if c in df_final.columns]]
                
            st.success(f"¡Cruce realizado con éxito! Encontramos {len(df_final)} coincidencias.")
            st.dataframe(df_final)
            
            # --- EXPORTACIÓN A EXCEL ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter', datetime_format='dd/mm/yyyy') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Compensaciones')
            
            st.download_button(
                label="📥 Descargar Resultado (Excel .xlsx)",
                data=buffer.getvalue(),
                file_name="Output_Compensaciones_Cruzadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error("Ocurrió un error inesperado al procesar. Este es el detalle técnico:")
            st.exception(e)
    else:
        st.warning("Por favor sube el archivo de saldos, el de transferencias y al menos un archivo de transacciones para continuar.")
