import streamlit as st
import pandas as pd
import re
import io

# --- FUNCIONES DE LIMPIEZA ---
def clean_ticket(ticket_str):
    if pd.isna(ticket_str): return ""
    numbers = re.findall(r'\d+', str(ticket_str))
    if numbers: return numbers[-1]
    return ticket_str

def clean_monto(monto_str):
    if pd.isna(monto_str): return ""
    return str(monto_str).replace('$', '').replace('.', '').replace(',', '').strip()

# --- FUNCIONES DE PROCESAMIENTO ---
def procesar_saldos(df):
    renames = {
        'Marca temporal': 'Datetime Compensación',
        'Numero ticket ': 'Numero',
        'Numero de reserva ': 'Id_reserva'
    }
    df = df.rename(columns=renames)
    df.columns = df.columns.str.strip()
    
    df['Numero'] = df['Numero'].apply(clean_ticket)
    df['Monto a compensar'] = df['Monto a compensar'].apply(clean_monto)
    df['Compensación Aeropuerto'] = 'Saldo (Aeropuerto)'
    
    if 'Id_reserva' in df.columns:
        df['Id_reserva'] = df['Id_reserva'].astype(str).str.strip()
    
    return df

def procesar_transferencias(df):
    df.columns = df.columns.str.strip() 
    
    if 'Motivo' in df.columns:
        df = df[df['Motivo'].str.strip() == 'Compensación Aeropuerto']
    
    motivos_validos = ["Usuario pierde el vuelo", "Reserva no encuentra conductor o no llega el conductor"]
    if 'Si es compensación Aeropuerto selecciona el motivo' in df.columns:
        df = df[df['Si es compensación Aeropuerto selecciona el motivo'].str.strip().isin(motivos_validos)]
        
    renames = {
        'Fecha': 'Datetime Compensación',
        'Ticket': 'Numero',
        'Correo': 'Correo registrado en Cabify para realizar la carga',
        'Monto': 'Monto a compensar',
        'Si es compensación Aeropuerto selecciona el motivo': 'Motivo compensación',
        'Link payments, link del viaje o numero reserva': 'Id_reserva'
    }
    df = df.rename(columns=renames)
    
    if 'Numero' in df.columns: df['Numero'] = df['Numero'].apply(clean_ticket)
    if 'Monto a compensar' in df.columns: df['Monto a compensar'] = df['Monto a compensar'].apply(clean_monto)
        
    df['Compensación Aeropuerto'] = 'Transferencia (Aeropuerto)'
    
    if 'Id_reserva' in df.columns:
        df['Id_reserva'] = df['Id_reserva'].astype(str).str.strip()
        
    return df

def procesar_transacciones(lista_dfs):
    df_trans = pd.concat(lista_dfs, ignore_index=True)
    df_trans.columns = df_trans.columns.str.strip()
    
    if 'F.Hacia Aerop' in df_trans.columns:
        df_trans = df_trans.dropna(subset=['F.Hacia Aerop'])
        df_trans = df_trans[df_trans['F.Hacia Aerop'].str.strip() != '']
    
    df_trans = df_trans.rename(columns={
        'Id Reserva': 'Id_reserva',
        'F.Hacia Aerop': 'Tm_start_local_at'
    })
    
    if 'Id_reserva' in df_trans.columns:
        df_trans['Id_reserva'] = df_trans['Id_reserva'].astype(str).str.strip()
    
    # Prevenir error si no están las columnas tras el rename
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

# --- PANEL DE DIAGNÓSTICO ---
with st.expander("🛠️ Diagnóstico de Archivos (Clic para expandir)"):
    st.write("Usa este panel para verificar si la app está leyendo correctamente las columnas.")
    try:
        if archivo_saldos:
            df_saldos_test = pd.read_excel(archivo_saldos)
            st.success("✅ Saldos leído correctamente. Columnas detectadas:")
            st.write(df_saldos_test.columns.tolist())
            archivo_saldos.seek(0) # Reiniciar puntero
            
        if archivo_transf:
            df_transf_test = pd.read_excel(archivo_transf)
            st.success("✅ Transferencias leído correctamente. Columnas detectadas:")
            st.write(df_transf_test.columns.tolist())
            archivo_transf.seek(0)
            
        if archivos_transacciones:
            df_trans_test = pd.read_csv(archivos_transacciones[0])
            st.success(f"✅ Transacciones leído correctamente. Columnas del primer archivo:")
            st.write(df_trans_test.columns.tolist())
            archivos_transacciones[0].seek(0)
            
    except ImportError as e:
        if 'openpyxl' in str(e):
            st.error("🚨 ERROR DE ENTORNO: Falta 'openpyxl'. Streamlit Cloud no ha instalado la librería para leer Excel. Ve a las opciones de Streamlit Cloud (⋮) arriba a la derecha y haz clic en 'Reboot app'.")
    except Exception as e:
        st.error(f"Error al leer archivo en diagnóstico: {e}")

# --- BOTÓN DE PROCESAMIENTO ---
if st.button("Procesar y Cruzar Datos", type="primary"):
    if archivo_saldos and archivo_transf and archivos_transacciones:
        try:
            with st.spinner('Procesando datos...'):
                # Lectura de archivos
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
                
                # Validar columnas faltantes para avisar al usuario
                faltantes_saldos = [c for c in columnas_requeridas if c not in df_saldos.columns]
                if faltantes_saldos: st.warning(f"⚠️ Atención: A la base de SALDOS le faltaron estas columnas finales: {faltantes_saldos}")
                    
                df_saldos = df_saldos[[c for c in columnas_requeridas if c in df_saldos.columns]]
                df_transf = df_transf[[c for c in columnas_requeridas if c in df_transf.columns]]
                
                df_compensaciones = pd.concat([df_saldos, df_transf], ignore_index=True)
                
                # Verificar si Id_reserva existe para poder cruzar
                if 'Id_reserva' not in df_compensaciones.columns or 'Id_reserva' not in df_trans.columns:
                    st.error("🚨 Error crítico: No se encontró la columna 'Id_reserva' o su equivalente original en los archivos, no se puede hacer el cruce.")
                    st.stop()
                
                df_final = pd.merge(df_compensaciones, df_trans, on='Id_reserva', how='inner')
                
                if 'Tm_start_local_at' in df_final.columns:
                    tm_clean = df_final['Tm_start_local_at'].str.replace(r'\.\s*m\.', 'm', regex=True).str.replace(r'\s+', ' ', regex=True)
                    df_final['Tm_dt'] = pd.to_datetime(tm_clean, errors='coerce', dayfirst=True)
                    
                    df_final['Fecha'] = df_final['Tm_dt'].dt.strftime('%d/%m/%Y')
                    df_final['Hora'] = df_final['Tm_dt'].dt.hour.fillna(-1).astype(int) 
                
                columnas_finales = columnas_requeridas + ['Tm_start_local_at', 'Fecha', 'Hora']
                df_final = df_final[[c for c in columnas_finales if c in df_final.columns]]
                
            st.success(f"¡Cruce realizado con éxito! Encontramos {len(df_final)} coincidencias.")
            st.dataframe(df_final)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Compensaciones')
            
            st.download_button(
                label="📥 Descargar Resultado (Excel .xlsx)",
                data=buffer.getvalue(),
                file_name="Output_Compensaciones_Cruzadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except ImportError as e:
            if 'openpyxl' in str(e):
                st.error("🚨 ERROR DE ENTORNO: Falta 'openpyxl'. Por favor reinicia la app en Streamlit Cloud o verifica que el archivo requirements.txt contiene la palabra 'openpyxl'.")
        except Exception as e:
            st.error("Ocurrió un error inesperado. Revisa el panel de diagnóstico arriba para ver si las columnas coinciden.")
            st.exception(e) # Esto imprimirá el error técnico real para saber exactamente qué falló.
    else:
        st.warning("Por favor sube el archivo de saldos, el de transferencias y al menos un archivo de transacciones para continuar.")
