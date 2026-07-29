import streamlit as st
import pandas as pd
import pdfplumber
import os
import re

# Име на вградената база данни на сайта
DB_FILE = "dnevnik_fakturi.csv"

# Инициализиране на базата данни, ако не съществува
if not os.path.exists(DB_FILE):
    df_init = pd.DataFrame(columns=["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"])
    df_init.to_csv(DB_FILE, index=False, encoding="utf-8-sig")

# --- ДВУЕЗИЧЕН АЛГОРИТЪМ ЗА ИЗВЛИЧАНЕ НА ДАННИ ОТ БИЗНЕС НАВИГАТОР ---
def extract_invoice_data(file_bytes):
    with pdfplumber.open(file_bytes) as pdf:
        if len(pdf.pages) > 0:
            page_text = pdf.pages[0].extract_text()
        else:
            return None
            
        if not page_text:
            return None
        
        lines = [line.strip() for line in page_text.split('\n')]
        
        invoice_number = "Не е намерен"
        invoice_date = "Не е намерена"
        invoice_client = "Не е намерен"
        invoice_amount = "Не е намерена"
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "number:" in line_lower or "номер:" in line_lower:
                invoice_number = line.split()[-1]
            if "date:" in line_lower or "дата:" in line_lower:
                invoice_date = line.split()[-1]
            if ("reciever:" in line_lower or "получател:" in line_lower) and (i + 1) < len(lines):
                next_line = lines[i + 1]
                if next_line and "адрес:" not in next_line.lower():
                    invoice_client = next_line
            if "сума за плащане:" in line_lower:
                invoice_amount = line.split(":")[-1].strip() + " EUR"
            elif line_lower.startswith("всичко ") and invoice_amount == "Не е намерена":
                invoice_amount = line.split()[-1].strip() + " EUR"
                
            match_en = re.search(r'total\s+costs?[\s\:]+(.*)', line_lower)
            if match_en:
                start_idx = line_lower.find(match_en.group(1))
                invoice_amount = line[start_idx:].strip()
                if "eur" not in invoice_amount.lower():
                    invoice_amount += " EUR"

        return {
            "Номер": invoice_number,
            "Дата": invoice_date,
            "Сума": invoice_amount,
            "Клиент": invoice_client,
            "Падеж": "-",
            "Статус": "Неплатена"
        }

# --- ИНТЕРФЕЙС НА УЕБ САЙТА (STREAMLIT) ---
st.set_page_config(page_title="Дневник Фактури", layout="wide")
st.title("📊 Споделен онлайн дневник за фактури")
st.write("Автоматично извличане на данни от фактури на Бизнес Навигатор и управление на падежи.")

# Зареждане на данните от вградената база
df = pd.read_csv(DB_FILE, dtype={"Номер": str})

# СЕКЦИЯ 1: КАЧВАНЕ НА НОВИ ФАКТУРИ
st.sidebar.header("📁 Качване на нови документи")
uploaded_file = st.sidebar.file_uploader("Пуснете PDF фактура тук:", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Извлечи и Запиши в Дневника"):
        with st.spinner("Разчитане на бланката..."):
            extracted_data = extract_invoice_data(uploaded_file)
            
            if extracted_data and extracted_data["Номер"] != "Не е намерен":
                current_number = str(extracted_data["Номер"])
                
                # Проверка за дублиране във вътрешната база
                is_duplicate = False
                if not df.empty:
                    matched_rows = df[df["Номер"].astype(str) == current_number]
                    if extracted_data["Клиент"] in matched_rows["Клиент"].tolist():
                        is_duplicate = True
                
                if is_duplicate:
                    st.sidebar.warning(f"⚠️ Фактура №{current_number} за този клиент вече съществува!")
                else:
                    # Записване в локалния CSV файл
                    new_row = pd.DataFrame([extracted_data])
                    df = pd.concat([df, new_row], ignore_index=True)
                    df.to_csv(DB_FILE, index=False, encoding="utf-8-sig")
                    st.sidebar.success(f"✅ Фактура №{current_number} е записана!")
                    st.rerun()
            else:
                st.sidebar.error("Неуспешно разчитане на PDF файла.")

# СЕКЦИЯ 2: УПРАВЛЕНИЕ И РЕДАКЦИЯ НА ПАДЕЖИ И СТАТУС директно от сайта
st.header("📋 Списък с обработени фактури")

if not df.empty:
    # Филтри най-отгоре
    col1, col2 = st.columns(2)
    with col1:
        unique_clients = ["Всички"] + sorted(df["Клиент"].dropna().unique().tolist())
        selected_client = st.selectbox("🔍 Филтър по Клиент:", unique_clients)
    with col2:
        selected_status = st.selectbox("🔔 Филтър по Статус:", ["Всички", "Платена", "Неплатена"])
        
    # Прилагане на филтрите за визуализация
    filtered_df = df.copy()
    if selected_client != "Всички":
        filtered_df = filtered_df[filtered_df["Клиент"] == selected_client]
    if selected_status != "Всички":
        filtered_df = filtered_df[filtered_df["Статус"] == selected_status]
        
    # Показване на таблицата
    st.dataframe(filtered_df[["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"]], use_container_width=True, hide_index=True)
    
    # Бърза форма за промяна на Падеж и Статус под таблицата
    st.subheader("✏️ Бърза промяна на Падеж или Статус")
    invoice_to_edit = st.selectbox("Изберете номер на фактура за редактиране:", df["Номер"].tolist())
    
    if invoice_to_edit:
        idx = df[df["Номер"] == invoice_to_edit].index[0]
        
        col_edit1, col_edit2 = st.columns(2)
        with col_edit1:
            new_pad_date = st.text_input("Въведете Падеж (напр. 15.08.2026):", value=str(df.loc[idx, "Падеж"]))
        with col_edit2:
            current_st = df.loc[idx, "Status" if "Status" in df.columns else "Статус"]
            st_idx = 0 if current_st == "Неплатена" else 1
            new_st = st.selectbox("Статус на плащане:", ["Неплатена", "Платена"], index=st_idx)
            
        if st.button("💾 Запази промените"):
            df.loc[idx, "Падеж"] = new_pad_date
            df.loc[idx, "Статус"] = new_st
            df.to_csv(DB_FILE, index=False, encoding="utf-8-sig")
            st.success("Промените бяха запазени успешно!")
            st.rerun()
else:
    st.info("Дневникът все още е празен. Качете първата си фактура от менюто вляво!")
