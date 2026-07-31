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

# ИМЕТО НА ФАЙЛА С БАЗАТА ДАННИ
DB_FILE = "dnevnik_fakturi.csv"

# Инициализиране, ако не съществува
if not os.path.exists(DB_FILE):
    df_init = pd.DataFrame(columns=["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"])
    df_init.to_csv(DB_FILE, index=False, encoding="utf-8-sig")

# Зареждане на данните
df = pd.read_csv(DB_FILE, dtype={"Номер": str, "Падеж": str, "Сума": str})

# Автоматично хронологично сортиране (водещо по Дата на фактурата)
if not df.empty:
    df['temp_date'] = pd.to_datetime(df['Дата'], format='%d.%m.%Y', errors='coerce')
    df = df.sort_values(by=['temp_date', 'Номер'], ascending=[True, True])
    df = df.drop(columns=['temp_date'])

# --- 2. ИНТЕЛИГЕНТЕН ДВУЕЗИЧЕН АЛГОРИТЪМ ЗА ИЗВЛИЧАНЕ ---
def extract_invoice_data(file_bytes):
    with pdfplumber.open(file_bytes) as pdf:
        if len(pdf.pages) > 0:
            page_text = pdf.pages[0].extract_text()
        else:
            return None
            
        if not page_text:
            return None
        
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
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
            
            # Търсене на Сума БГ (всичко за плащане, сума за плащане)
            if "плащане" in line_lower or line_lower.startswith("всичко"):
                invoice_amount = line.split()[-1].strip()
                
            # Гъвкаво търсене на Сума АНГ (хваща тотал кост, костс или само тотал на реда със сумата)
            if "total" in line_lower and any(num in line_lower for num in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
                # Взимаме последната дума от реда, която е самото число
                invoice_amount = line.split()[-1].strip()

        # Почистване на сумата
        invoice_amount = invoice_amount.replace(":", "").strip()
        if invoice_amount != "Не е намерена" and "eur" not in invoice_amount.lower() and "лв" not in invoice_amount.lower():
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
                if not df.empty:
                    matched_rows = df[df["Номер"].astype(str) == current_number]
                    if extracted_data["Клиент"] in matched_rows["Клиент"].tolist():
                        is_duplicate = True
                
                if is_duplicate:
                    st.sidebar.warning(f"⚠️ Внимание! Фактура №{current_number} за този клиент вече съществува!")
                else:
                    new_row = pd.DataFrame([extracted_data])
                    df = pd.concat([df, new_row], ignore_index=True)
                    df.to_csv(DB_FILE, index=False, encoding="utf-8-sig")
                    st.sidebar.success(f"✅ Фактура №{current_number} е записана!")
                    st.rerun()
            else:
                st.sidebar.error("Неуспешно разчитане на PDF файла.")

# СЕКЦИЯ 2: УПРАВЛЕНИЕ И РЕДАКЦИЯ
st.header("📋 Списък с обработени фактури")

if not df.empty:
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        unique_clients = ["Всички"] + sorted(df["Клиент"].dropna().unique().tolist())
        selected_client = st.selectbox("🔍 Филтър по ...", unique_clients, key="client_select")
    with f2:
        selected_status = st.selectbox("🔔 Филтър по ...", ["Всички", "Платена", "Неплатена"], key="status_select")
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
        if start_pad:
            filtered_df = filtered_df[filtered_df['temp_pad_date'] >= pd.to_datetime(start_pad)]
        if end_pad:
            filtered_df = filtered_df[filtered_df['temp_pad_date'] <= pd.to_datetime(end_pad)]
        filtered_df = filtered_df.drop(columns=['temp_pad_date'])

    def style_status(val):
        if val == "Неплатена": return "color: #FF4B4B; font-weight: bold;"
        elif val == "Платена": return "color: #00D488; font-weight: bold;"
        return ""

    st.dataframe(
        filtered_df[["Номер", "Дата", "Сума", "Клиент", "Падеж", "Статус"]].style.map(style_status, subset=["Статус"]), 
        use_container_width=True, 
        hide_index=True
    )
    
    try:
        import io
        towrite = io.BytesIO()
        df.to_excel(towrite, index=False, header=True, engine='openpyxl')
        towrite.seek(0)
        st.download_button(label="📥 Изтегли целия дневник в Excel файл", data=towrite, file_name="Dnevnik_Fakturi_Backup.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception: pass

    # РЕДАКЦИЯ НА ПАДЕЖ, СТАТУС И СУМА
    st.subheader("✏️ Бърза промяна на данни (Сума / Падеж / Статус)")
    invoice_to_edit = st.selectbox("Изберете номер на фактура за редактиране:", df["Номер"].tolist())
    
    if invoice_to_edit:
        idx = df[df["Номер"] == invoice_to_edit].index
        
        col_edit1, col_edit2, col_edit3 = st.columns(3)
        with col_edit1:
            current_amount = str(df.loc[idx, "Сума"].values[0])
            new_amount = st.text_input("Сума (напр. 800.00 EUR):", value=current_amount, key=f"amount_{invoice_to_edit}")
        with col_edit2:
            current_pad_str = str(df.loc[idx, "Падеж"].values[0])
            try:
                default_date = datetime.strptime(current_pad_str, "%d.%m.%Y").date()
            except ValueError:
                default_date = datetime.today().date()
            new_pad_date_obj = st.date_input("Падеж от календара:", value=default_date, key=f"pad_date_{invoice_to_edit}")
            new_pad_date = new_pad_date_obj.strftime("%d.%m.%Y")
        with col_edit3:
            current_st = str(df.loc[idx, "Статус"].values[0])
            st_idx = 0 if current_st == "Неплатена" else 1
            new_st = st.selectbox("Статус на плащане:", ["Неплатена", "Платена"], index=st_idx, key=f"status_select_{invoice_to_edit}")
            
        if st.button("💾 Запази промените", key="save_btn"):
            df.loc[idx, "Сума"] = new_amount
            df.loc[idx, "Падеж"] = new_pad_date
            df.loc[idx, "Статус"] = new_st
            df.to_csv(DB_FILE, index=False, encoding="utf-8-sig")
            st.success("Промените бяха запазени успешно!")
            st.rerun()
else:
    st.info("Дневникът все още е празен. Качете първата си фактура от менюто вляво!")
