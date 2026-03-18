import streamlit as st
import pandas as pd
import re

# --- FUNCIONES DE LIMPIEZA ---
def clean_ticket(ticket_str):
    """Extrae solo el número de ticket (ignora # o links)."""
    if pd.isna(ticket_str):
        return ""
    # Busca todos los bloques de números en el string
    numbers = re.findall(r'\d+', str(ticket_str))
    if numbers:
        return numbers[-1] # Toma el último bloque (ideal para los links largos)
    return ticket_str

def clean_monto(monto_str):
    """Limpia los montos quitando $, puntos y espacios."""
    if pd.isna(monto_str):
        return ""
    return str(monto_str).replace('$', '').replace('.', '').replace(',', '').strip()

# --- FUNCIONES DE PROCESAMIENTO ---
def procesar_saldos(file):
    df = pd.read_csv(file)
    
    # Renombrar columnas según el output deseado
    renames = {
        'Marca temporal': 'Datetime Compensación',
        'Numero ticket ': 'Numero',
        'Numero de reserva ': 'Id_reserva'
        # Los demás nombres (Dirección de correo electrónico, etc.) ya coinciden o se ajustarán
    }
    df = df.rename(columns=renames)
    
    # Asegurar que las columnas existan, corrigiendo posibles espacios al final de los nombres
    df.columns = df.columns.str.strip()
    
    # Limpiezas
    df['Numero'] = df['Numero'].apply(clean_ticket)
    df['Monto a compensar'] = df['Monto a compensar'].apply(clean_monto)
    
    # Agregar columna diferenciadora
    df['Compensación Aeropuerto'] = 'Saldo (Aeropuerto)'
    
    # Forzar Id_reserva como string para el cruce
    df['Id_reserva'] = df['Id_reserva'].astype(str).str.strip()
    
    return df

def procesar_transferencias(file):
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip() # Limpiar espacios en los nombres de columnas
    
    # Filtros obligatorios
    # 1. Motivo == Compensación Aeropuerto
    if 'Motivo' in df.columns:
        df = df[df['Motivo'].str.strip() == 'Compensación Aeropuerto']
    
    # 2. Tipos de motivos específicos
    motivos_validos = [
        "Usuario pierde el vuelo", 
        "Reserva no encuentra conductor o no llega el conductor"
    ]
    if 'Si es compensación Aeropuerto selecciona el motivo' in df.columns:
        df = df[df['Si es compensación Aeropuerto selecciona el motivo'].str.strip().isin(motivos_validos)]
        
    # Renombrar columnas
    renames = {
        'Fecha': 'Datetime Compensación',
        'Ticket': 'Numero',
        'Correo': 'Correo registrado en Cabify para realizar la carga',
        'Monto': 'Monto a compensar',
        'Si es compensación Aeropuerto selecciona el motivo': 'Motivo compensación',
        'Link payments, link del viaje o numero reserva': 'Id_reserva'
    }
    df = df.rename(columns=renames)
    
    # Limpiezas
    if 'Numero' in df.columns:
        df['Numero'] = df['Numero'].apply(clean_ticket)
    if 'Monto a compensar' in df.columns:
        df['Monto a compensar'] = df['Monto a compensar'].apply(clean_monto)
        
    # Agregar columna diferenciadora
    df['Compensación Aeropuerto'] = 'Transferencia (Aeropuerto)'
    
    # Forzar Id_reserva como string
    if 'Id_reserva' in df.columns:
        df['Id_reserva'] = df['Id_reserva'].astype(str).str.strip()
        
    return df

def procesar_transacciones(files):
    lista_dfs = []
    for f in files:
        df_temp = pd.read_csv(f)
        lista_dfs.append(df_temp)
        
    df_trans = pd.concat(lista_dfs, ignore_index=True)
    df_trans.columns = df_trans.columns.str.strip()
    
    # Filtrar solo donde F.Hacia Aerop no esté vacío (viajes hacia el aeropuerto)
    df_trans = df_trans.dropna(subset=['F.Hacia Aerop'])
    df_trans = df_trans[df_trans['F.Hacia Aerop'].str.strip() != '']
    
    # Renombrar
    df_trans = df_trans.rename(columns={
        'Id Reserva': 'Id_reserva',
        'F.Hacia Aerop': 'Tm_start_local_at'
    })
    
    df_trans['Id_reserva'] = df_trans['Id_reserva'].astype(str).str.strip()
    
    return df_trans[['Id_reserva', 'Tm_start_local_at']]

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Cruce Compensaciones Aeropuerto", layout="wide")
st.title("✈️ Cruce de Compensaciones Aeropuerto vs Transacciones")

st.markdown("### 1. Sube los archivos de Compensaciones")
col1, col2 = st.columns(2)

with col1:
    archivo_saldos = st.file_uploader("Archivo de Saldos (CSV)", type=['csv'])
with col2:
    archivo_transf = st.file_uploader("Archivo de Transferencias (CSV)", type=['csv'])

st.markdown("### 2. Sube los archivos de Transacciones (Múltiples permitidos)")
archivos_transacciones = st.file_uploader("Archivos de Transacciones (CSV)", type=['csv'], accept_multiple_files=True)

if st.button("Procesar y Cruzar Datos", type="primary"):
    if archivo_saldos and archivo_transf and archivos_transacciones:
        try:
            with st.spinner('Procesando datos...'):
                # 1. Procesar bases
                df_saldos = procesar_saldos(archivo_saldos)
                df_transf = procesar_transferencias(archivo_transf)
                
                # Columnas finales que necesitamos
                columnas_requeridas = [
                    'Datetime Compensación', 'Dirección de correo electrónico', 'Numero', 
                    'Correo registrado en Cabify para realizar la carga', 'Monto a compensar', 
                    'Motivo compensación', 'Id_reserva', 'Compensación Aeropuerto'
                ]
                
                # Asegurar que existan y concatenar compensaciones
                df_saldos = df_saldos[[c for c in columnas_requeridas if c in df_saldos.columns]]
                df_transf = df_transf[[c for c in columnas_requeridas if c in df_transf.columns]]
                df_compensaciones = pd.concat([df_saldos, df_transf], ignore_index=True)
                
                # 2. Procesar transacciones
                df_trans = procesar_transacciones(archivos_transacciones)
                
                # 3. Cruce (Merge)
                # Hacemos un inner join para quedarnos solo con los que hacen "match"
                df_final = pd.merge(df_compensaciones, df_trans, on='Id_reserva', how='inner')
                
                # 4. Extraer Fecha y Hora del Tm_start_local_at
                # Ajustamos textos como "a. m." para que pandas lo entienda mejor
                tm_clean = df_final['Tm_start_local_at'].str.replace(r'\.\s*m\.', 'm', regex=True).str.replace(r'\s+', ' ', regex=True)
                # Parsear datetime (maneja formatos mixtos de forma segura)
                df_final['Tm_dt'] = pd.to_datetime(tm_clean, errors='coerce', dayfirst=True)
                
                df_final['Fecha'] = df_final['Tm_dt'].dt.strftime('%d/%m/%Y')
                # Llenar hora vacía con un identificador (ej: -1) si falló el parseo para no perder el dato
                df_final['Hora'] = df_final['Tm_dt'].dt.hour.fillna(-1).astype(int) 
                
                # Ordenar columnas como en el output deseado
                columnas_finales = columnas_requeridas + ['Tm_start_local_at', 'Fecha', 'Hora']
                df_final = df_final[columnas_finales]
                
            st.success("¡Cruce realizado con éxito!")
            st.dataframe(df_final)
            
            # Botón de descarga
            csv_export = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Resultado (CSV)",
                data=csv_export,
                file_name="Output_Compensaciones_Cruzadas.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Ocurrió un error al procesar los datos: {e}")
            st.write("Verifica que las columnas de los archivos correspondan exactamente a lo mencionado.")
    else:
        st.warning("Por favor sube el archivo de saldos, el de transferencias y al menos un archivo de transacciones para continuar.")
