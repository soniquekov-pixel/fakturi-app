import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="СПАСИТЕЛЕН АРХИВ", layout="wide")
st.title("📦 Спасителен прозорец за архив на данни")

DB_FILE = "dnevnik_fakturi.csv"

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE, dtype={"Номер": str})
    st.success(f" Намерени са {len(df)} бр. записани фактури в системата!")
    
    # Показваме ги за проверка
    st.dataframe(df, use_container_width=True)
    
    # Бутон за незабавно изтегляне
    import io
    towrite = io.BytesIO()
    df.to_excel(towrite, index=False, header=True, engine='openpyxl')
    towrite.seek(0)
    st.download_button(
        label="📥 ИЗТЕГЛИ АРХИВА В EXCEL ВЕДНАГА",
        data=towrite,
        file_name="Dnevnik_Fakturi_SPASEN_ARCHIVE.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.error("Внимание: Старият файл 'dnevnik_fakturi.csv' не беше намерен на този сървър!")
