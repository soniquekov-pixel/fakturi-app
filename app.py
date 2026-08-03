import streamlit as st
import pandas as pd
import pdfplumber
import os
import re
from datetime import datetime

# --- 0. ЗАЩИТА С ПАРОЛА ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.set_page_config(page_title="Вход - Дневник Фактури", layout="centered")
    st.title("🔒 Заключена система")
    st.write("Моля, въведете парола, за да достъпите споделения дневник за фактури.")
    
    user_password = st.text_input("Парола:", type="password")
    if st.button("🚪 Вход"):
        if user_password == "00000000":
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Грешна парола! Опитайте отново.")
    st.stop()

# ИМЕТО НА ФАЙЛА С АРХИВА В GITHUB
DB_FILE = "база_данни.csv"

# Инициализиране на постоянната памет на сайта, за да не се трие при рестарт
if "main_data" not in st.session_state:
    if os.path.exists(DB_FILE):
        # Зареждаме заварените 2 месеца с данни от GitHub първоначално
        st.session_state["main_data"] = pd.read_csv(DB_FILE, dtype={"Номер": str, "Падеж": str, "Сума": str})
    else:
        st.session_state["main_data"] = pd.DataFrame(columns=["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"])

# Взимаме актуалния масив от паметта на сайта
df = st.session_state["main_data"]
df.columns = [str(col).strip() for col in df.columns]

# Автоматично хронологично сортиране (водещо по Дата на фактурата)
if not df.empty and "Дата" in df.columns:
    df['temp_date'] = pd.to_datetime(df['Дата'], format='%d.%m.%Y', errors='coerce')
    df = df.sort_values(by=['temp_date', 'Номер'], ascending=[True, True])
    df = df.drop(columns=['temp_date'])
    st.session_state["main_data"] = df

# --- 2. ДВУЕЗИЧЕН АЛГОРИТЪМ ЗА ИЗВЛИЧАНЕ ОТ БИЗНЕС НАВИГАТОР ---
def extract_invoice_data(file_bytes):
    with pdfplumber.open(file_bytes) as pdf:
        if len(pdf.pages) > 0:
            page_text = pdf.pages[0].extract_text()
        else:
            return None
            
        if not page_text:
            return None
        
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        invoice_number, invoice_date, invoice_client, invoice_amount = "Не е намерен", "Не е намерена", "Не е намерен", "Не е намерена"
        
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
            
            if "плащане" in line_lower or line_lower.startswith("всичко"):
                invoice_amount = line.split()[-1].strip()
                
            if "total" in line_lower or "cost" in line_lower:
                words = line.split()
                last_word = words[-1].strip()
                if any(char.isdigit() for char in last_word):
                    invoice_amount = last_word
                else:
                    if (i + 1) < len(lines):
                        next_line_words = lines[i + 1].split()
                        if next_line_words:
                            invoice_amount = next_line_words[-1].strip()

        invoice_amount = invoice_amount.replace(":", "").strip()
        if invoice_amount != "Не е намерена" and "eur" not in invoice_amount.lower() and "лв" not in invoice_amount.lower():
            invoice_amount += " EUR"

        return {"Номер": invoice_number, "Дата": invoice_date, "Сума": invoice_amount, "Клиент": invoice_client, "Падеж": "-", "Статус": "Неплатена"}

# --- 3. ИНТЕРФЕЙС НА УЕБ САЙТА (STREAMLIT) ---
st.set_page_config(page_title="Дневник Фактури", layout="wide")
st.title("📊 Споделен онлайн дневник за фактури")
st.write("Система за автоматично извличане на данни от фактури и управление на падежи.")

# СЕКЦИЯ 1: КАЧВАНЕ НА НОВИ ФАКТУРИ
st.sidebar.header("📁 Качване на нови документи")
uploaded_file = st.sidebar.file_uploader("Пуснете PDF фактура тук:", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Извлечи и Запиши в Дневника"):
        with st.spinner("Разчитане на бланката..."):
            extracted_data = extract_invoice_data(uploaded_file)
            
            if extracted_data and extracted_data["Номер"] != "Не е намерен":
                current_number = str(extracted_data["Номер"])
                
                is_duplicate = False
                if not df.empty and "Номер" in df.columns:
                    matched_rows = df[df["Номер"].astype(str) == current_number]
                    if extracted_data["Клиент"] in matched_rows["Клиент"].tolist():
                        is_duplicate = True
                
                if is_duplicate:
                    st.sidebar.warning(f"⚠️ Внимание! Фактура №{current_number} за този клиент вече съществува!")
                else:
                    new_row = pd.DataFrame([extracted_data])
                    st.session_state["main_data"] = pd.concat([st.session_state["main_data"], new_row], ignore_index=True)
                    st.sidebar.success(f"✅ Фактура №{current_number} е записана успешно!")
                    st.rerun()

# СЕКЦИЯ 2: УПРАВЛЕНИЕ И РЕДАКЦИЯ
st.header("📋 Списък с обработени фактури")

available_cols = ["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"]
for col in available_cols:
    if col not in df.columns:
        df[col] = "-"

if not df.empty:
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        unique_clients = ["Всички"] + sorted(df["Клиент"].dropna().unique().tolist())
        selected_client = st.selectbox("🔍 Филтър по Клиент:", unique_clients)
    with f2:
        selected_status = st.selectbox("🔔 Филтър по Статус:", ["Всички", "Платена", "Неплатена"])
    with f3:
        start_pad = st.date_input("📅 Падеж от:", value=None)
    with f4:
        end_pad = st.date_input("📅 Падеж до:", value=None)
        
    filtered_df = df.copy()
    if selected_client != "Всички":
        filtered_df = filtered_df[filtered_df["Клиент"] == selected_client]
    if selected_status != "Всички":
        filtered_df = filtered_df[filtered_df["Статус"] == selected_status]
        
    if start_pad or end_pad:
        filtered_df['temp_pad_date'] = pd.to_datetime(filtered_df['Падеж'], format='%d.%m.%Y', errors='coerce')
        if start_pad: filtered_df = filtered_df[filtered_df['temp_pad_date'] >= pd.to_datetime(start_pad)]
        if end_pad: filtered_df = filtered_df[filtered_df['temp_pad_date'] <= pd.to_datetime(end_pad)]
        filtered_df = filtered_df.drop(columns=['temp_pad_date'])

    def style_status(val):
        if val == "Неплатена": return "color: #FF4B4B; font-weight: bold;"
        elif val == "Платена": return "color: #00D488; font-weight: bold;"
        return ""

    st.dataframe(filtered_df[available_cols].style.map(style_status, subset=["Статус"]), use_container_width=True, hide_index=True)
    
    # БУТОН ЗА ИЗТЕГЛЯНЕ НА АКТУАЛНИЯ ЕКСЕЛ
    try:
        import io
        towrite = io.BytesIO()
        st.session_state["main_data"].to_excel(towrite, index=False, header=True, engine='openpyxl')
        towrite.seek(0)
        st.download_button(label="📥 Свали актуализирания дневник в Excel файл", data=towrite, file_name="Dnevnik_Fakturi_Aktualen.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception: pass

    st.subheader("✏️ Бърза промяна на данни (Сума / Падеж / Статус)")
    invoice_to_edit = st.selectbox("Изберете номер на фактура за редактиране:", df["Номер"].tolist())
    
    if invoice_to_edit:
        idx = df[df["Номер"] == invoice_to_edit].index[0]
        
        col_edit1, col_edit2, col_edit3 = st.columns(3)
        with col_edit1:
            current_amount = str(st.session_state["main_data"].loc[idx, "Сума"])
            new_amount = st.text_input("Сума:", value=current_amount, key=f"amount_{invoice_to_edit}")
        with col_edit2:
            current_pad_str = str(st.session_state["main_data"].loc[idx, "Падеж"])
            try: default_date = datetime.strptime(current_pad_str, "%d.%m.%Y").date()
            except ValueError: default_date = datetime.today().date()
            new_pad_date_obj = st.date_input("Падеж от календара:", value=default_date, key=f"pad_date_{invoice_to_edit}")
            new_pad_date = new_pad_date_obj.strftime("%d.%m.%Y")
        with col_edit3:
            current_st = str(st.session_state["main_data"].loc[idx, "Статус"])
            st_idx = 0 if current_st == "Неплатена" else 1
            new_st = st.selectbox("Статус на плащане:", ["Неплатена", "Платена"], index=st_idx, key=f"status_select_{invoice_to_edit}")
            
        if st.button("💾 Запази промените", key="save_btn"):
            st.session_state["main_data"].loc[idx, "Сума"] = new_amount
            st.session_state["main_data"].loc[idx, "Падеж"] = new_pad_date
            st.session_state["main_data"].loc[idx, "Статус"] = new_st
            st.success("Промените бяха запазени успешно!")
            st.rerun()
else:
    st.info("Дневникът все още е празен.")
