import streamlit as st
import pandas as pd
import pdfplumber
import requests
import re

# --- 1. ТЕХНИЧЕСКИ НАСТРОЙКИ (КОДОВЕ НА ВАШИТЕ ГУГЪЛ ЛИНКОВЕ) ---
# Линкове към вашите документи, които ми споделихте
GOOGLE_SHEET_URL = "https://google.com"
GOOGLE_FORM_SUBMIT_URL = "https://google.com"

# Техническите кодове на полетата от вашата Google форма
FORM_ENTRIES = {
    "Номер": "entry.1039474932",  # Код за Номер
    "Дата": "entry.1749385920",   # Код за Дата
    "Сума": "entry.849204859",    # Код за Сума
    "Клиент": "entry.203948502",  # Код за Клиент
    "Падеж": "entry.938204859",   # Код за Падеж
    "Статус": "entry.184920495"   # Код за Статус
}

# --- 2. ДВУЕЗИЧЕН АЛГОРИТЪМ ЗА ИЗВЛИЧАНЕ НА ДАННИ ОТ БИЗНЕС НАВИГАТОР ---
def extract_invoice_data(file_bytes):
    with pdfplumber.open(file_bytes) as pdf:
        page_text = pdf.pages[0].extract_text()
        if not page_text:
            return None
        
        lines = [line.strip() for line in page_text.split('\n')]
        
        invoice_number = "Не е намерен"
        invoice_date = "Не е намерена"
        invoice_client = "Не е намерен"
        invoice_amount = "Не е намерена"
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Номер
            if "number:" in line_lower or "номер:" in line_lower:
                invoice_number = line.split()[-1]
            # Дата
            if "date:" in line_lower or "дата:" in line_lower:
                invoice_date = line.split()[-1]
            # Клиент
            if ("reciever:" in line_lower or "получател:" in line_lower) and (i + 1) < len(lines):
                next_line = lines[i + 1]
                if next_line and "адрес:" not in next_line.lower():
                    invoice_client = next_line
            # Сума
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

# --- 3. ИЗПРАЩАНЕ КЪМ GOOGLE ФОРМАТА (ЗАПИС В ТАБЛИЦАТА) ---
def send_to_google_form(data):
    form_data = {
        FORM_ENTRIES["Номер"]: data["Номер"],
        FORM_ENTRIES["Дата"]: data["Дата"],
        FORM_ENTRIES["Сума"]: data["Сума"],
        FORM_ENTRIES["Клиент"]: data["Клиент"],
        FORM_ENTRIES["Падеж"]: data["Падеж"],
        FORM_ENTRIES["Статус"]: data["Статус"]
    }
    response = requests.post(GOOGLE_FORM_SUBMIT_URL, data=form_data)
    return response.status_code == 200

# --- 4. ИНТЕРФЕЙС НА УЕБ САЙТА (STREAMLIT) ---
st.set_page_config(page_title="Дневник Фактури", layout="wide")
st.title("📊 Споделен онлайн дневник за фактури")
st.write("Система за автоматично извличане на данни от фактури и проследяване на падежи.")

# Зареждане на актуалните данни от вашата Google таблица
try:
    df = pd.read_csv(GOOGLE_SHEET_URL)
    # Почистване на колоните, ако Google добави служебни букви
    df.columns = [col.split('.')[-1].strip() for col in df.columns]
except Exception:
    df = pd.DataFrame(columns=["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"])

# СЕКЦИЯ 1: КАЧВАНЕ НА НОВИ ФАКТУРИ
st.sidebar.header("📁 Качване на нови документи")
uploaded_file = st.sidebar.file_uploader("Пуснете PDF фактура тук:", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Извлечи и Запиши в Дневника"):
        with st.spinner("Разчитане на Бизнес Навигатор бланка..."):
            extracted_data = extract_invoice_data(uploaded_file)
            if extracted_data and extracted_data["Номер"] != "Не е намерен":
                success = send_to_google_form(extracted_data)
                if success:
                    st.sidebar.success(f" Фактура №{extracted_data['Номер']} е записана успешно!")
                    st.rerun()
                else:
                    st.sidebar.error("Възникна грешка при записа в Google Sheets.")
            else:
                st.sidebar.error("Неуспешно разчитане. Моля, проверете дали PDF файлът има текстов слой.")

# СЕКЦИЯ 2: ТАБЛИЦА С ДАННИ И ФИЛТРИ
st.header("📋 Списък с обработени фактури")

if not df.empty:
    # Създаване на филтрите най-отгоре
    col1, col2 = st.columns(2)
    
    with col1:
        unique_clients = ["Всички"] + sorted(df["Клиент"].dropna().unique().tolist())
        selected_client = st.selectbox("🔍 Филтър по Клиент:", unique_clients)
        
    with col2:
        status_options = ["Всички", "Платена", "Неплатена"]
        selected_status = st.selectbox("🔔 Филтър по Статус:", status_options)
        
    # Прилагане на филтрите върху таблицата
    filtered_df = df.copy()
    if selected_client != "Всички":
        filtered_df = filtered_df[filtered_df["Клиент"] == selected_client]
    if selected_status != "Всички":
        filtered_df = filtered_df[filtered_df["Статус"] == selected_status]
        
    # Показване на филтрираната таблица на екрана
    st.dataframe(
        filtered_df[["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"]], 
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Дневникът е празен. Качете първата си фактура от страничното меню!")
