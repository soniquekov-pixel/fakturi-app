import streamlit as st
import pandas as pd
import pdfplumber
import requests
import re

# --- 1. ТЕХНИЧЕСКИ НАСТРОЙКИ (КОДОВЕ НА ВАШИТЕ ГУГЪЛ ЛИНКОВЕ) ---
GOOGLE_SHEET_URL = "https://google.com"
# Оптимизиран и директен адрес за изпращане на данни към Google Форми
GOOGLE_FORM_SUBMIT_URL = "https://google.com"

FORM_ENTRIES = {
    "Номер": "entry.1039474932",  
    "Дата": "entry.1749385920",   
    "Сума": "entry.849204859",    
    "Клиент": "entry.203948502",  
    "Падеж": "entry.938204859",   
    "Статус": "entry.184920495"   
}

# --- 2. ДВУЕЗИЧЕН АЛГОРИТЪМ ЗА ИЗВЛИЧАНЕ НА ДАННИ ОТ БИЗНЕС НАВИГАТОР ---
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

def send_to_google_form(data):
    form_data = {
        FORM_ENTRIES["Номер"]: data["Номер"],
        FORM_ENTRIES["Дата"]: data["Дата"],
        FORM_ENTRIES["Сума"]: data["Сума"],
        FORM_ENTRIES["Клиент"]: data["Клиент"],
        FORM_ENTRIES["Падеж"]: data["Падеж"],
        FORM_ENTRIES["Статус"]: data["Статус"]
    }
    
    # Стандартно изпращане без излишни хедъри, за да не се бърка Google
    response = requests.post(GOOGLE_FORM_SUBMIT_URL, data=form_data)
    
    # Google Forms връща код 200 при успешна обработка на уеб заявка
    success = response.status_code == 200
    return success, response.status_code

# --- 4. ИНТЕРФЕЙС НА УЕБ САЙТА (STREAMLIT) ---
st.set_page_config(page_title="Дневник Фактури", layout="wide")
st.title("📊 Споделен онлайн дневник за фактури")
st.write("Система за автоматично извличане на данни от фактури и проследяване на падежи.")

# Зареждане на данните
try:
    df = pd.read_csv(GOOGLE_SHEET_URL)
    df.columns = [str(col).strip() for col in df.columns]
except Exception:
    df = pd.DataFrame(columns=["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"])

# Уверяваме се, че колоните съществуват
for col_name in ["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"]:
    if col_name not in df.columns:
        found = False
        for actual_col in df.columns:
            if col_name.lower() in actual_col.lower():
                df.rename(columns={actual_col: col_name}, inplace=True)
                found = True
                break
        if not found:
            df[col_name] = "-"

# СЕКЦИЯ 1: КАЧВАНЕ НА НОВИ ФАКТУРИ
st.sidebar.header("📁 Качване на нови документи")
uploaded_file = st.sidebar.file_uploader("Пуснете PDF фактура тук:", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Извлечи и Запиши в Дневника"):
        with st.spinner("Разчитане на Бизнес Навигатор бланка..."):
            extracted_data = extract_invoice_data(uploaded_file)
            
            if extracted_data and extracted_data["Номер"] != "Не е намерен":
                # --- ПРОВЕРКА ЗА ДУБЛИРАНЕ ---
                existing_numbers = df["Номер"].astype(str).tolist()
                current_number = str(extracted_data["Номер"])
                
                is_duplicate = False
                if current_number in existing_numbers:
                    matched_rows = df[df["Номер"].astype(str) == current_number]
                    if extracted_data["Клиент"] in matched_rows["Клиент"].tolist():
                        is_duplicate = True
                
                if is_duplicate:
                    st.sidebar.warning(f"⚠️ Внимание! Фактура №{current_number} за клиент '{extracted_data['Клиент']}' вече съществува в дневника!")
                else:
                    success, status_code = send_to_google_form(extracted_data)
                    if success:
                        st.sidebar.success(f"✅ Фактура №{extracted_data['Номер']} е записана успешно!")
                        st.rerun()
                    else:
                        st.sidebar.error(f"Възникна грешка при записа в Google Sheets (Код: {status_code}).")
            else:
                st.sidebar.error("Неуспешно разчитане. Моля, проверете дали PDF файлът има текстов слой.")

# СЕКЦИЯ 2: ТАБЛИЦА С ДАННИ И ФИЛТРИ
st.header("📋 Списък с обработени фактури")

col1, col2 = st.columns(2)

with col1:
    unique_clients = ["Всички"] + sorted(df["Клиент"].dropna().unique().tolist())
    selected_client = st.selectbox("🔍 Филтър по Клиент:", unique_clients, key="client_select")
    
with col2:
    status_options = ["Всички", "Платена", "Неплатена"]
    selected_status = st.selectbox("🔔 Филтър по Статус:", status_options, key="status_select")
    
filtered_df = df.copy()
if selected_client != "Всички":
    filtered_df = filtered_df[filtered_df["Клиент"] == selected_client]
if selected_status != "Всички":
    filtered_df = filtered_df[filtered_df["Статус"] == selected_status]

st.dataframe(filtered_df[["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"]],
