from datetime import datetime
import re

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError, ClientError
import streamlit as st

# ======================= UI ЧАСТЬ =========================
st.set_page_config(page_title="S3 File Uploader", layout="centered")

st.write("")
st.title("RB Loan Deferment IDP")
st.write("Загрузите один файл в Amazon S3.")

# --- Основные параметры ---
AWS_PROFILE = ""   # профиль AWS из ~/.aws/credentials (оставьте пустым для env/role)
AWS_REGION = "us-east-1"   # регион AWS
BUCKET_NAME = "loan-deferment-idp-event-triggered-tlek"  # имя S3-бакета
KEY_PREFIX = "requests/"  # базовый префикс для загрузок

# --- Кастомизация интерфейса ---
st.markdown("""
<style>
.block-container{max-width:980px;padding-top:1.25rem;}
.meta{color:#6b7280;font-size:0.92rem;margin:0.25rem 0 1rem 0;}
.meta code{background:#f3f4f6;border:1px solid #e5e7eb;padding:2px 6px;border-radius:6px;}
.card{border:1px solid #e5e7eb;border-radius:14px;background:#ffffff;box-shadow:0 2px 8px rgba(0,0,0,.04);} 
.card.pad{padding:22px;}
.result-card{border:1px solid #e5e7eb;border-radius:14px;padding:16px;background:#fafafa;}
.stButton>button{border-radius:10px;padding:.65rem 1rem;font-weight:600;}
.stDownloadButton>button{border-radius:10px;}
</style>
""", unsafe_allow_html=True)

with st.expander("Помощь и настройка", expanded=False):
    tabs = st.tabs(["Запуск приложения", "Создание Access Key", "Окружение"])
    with tabs[0]:
        st.markdown("#### 1) Установите AWS CLI v2")
        st.code('''curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"\nsudo installer -pkg AWSCLIV2.pkg -target /''', language="bash")
        st.code("aws --version", language="bash")
        st.markdown("#### 2) Настройте учётные данные")
        st.code("aws configure", language="bash")
        st.markdown("#### 3) Запустите приложение")
        st.code("streamlit run main.py", language="bash")
    with tabs[1]:
        st.markdown("### 🔑 Создание Access Key (CLI)")
        st.markdown("Программные ключи нужны для работы из кода/CLI. Создайте их в AWS IAM.")
    with tabs[2]:
        st.markdown("### Окружение")
        st.markdown(f"- Bucket: `{BUCKET_NAME}`\n- Region: `{AWS_REGION}`")

# --- Форма загрузки ---
with st.form("upload_form", clear_on_submit=False):
    uploaded_file = st.file_uploader(
        "Выберите документ",
        type=["pdf", "jpg", "png", "jpeg"],
        accept_multiple_files=False,
        help="Поддержка: PDF, JPEG",
    )
    submitted = st.form_submit_button("Загрузить", type="primary")


# ===================== ФУНКЦИИ ============================

def get_s3_client(profile, region_name):
    if profile:
        session = boto3.session.Session(profile_name=profile, region_name=region_name or None)
        return session.client("s3")
    return boto3.client("s3", region_name=region_name or None)

def get_next_upload_folder(s3_client, bucket, prefix):
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        existing_max = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []) or []:
                p = cp.get("Prefix", "")
                m = re.search(r"upload_id_(\d{3,})/\Z", p)
                if m:
                    existing_max = max(existing_max, int(m.group(1)))
        next_id = existing_max + 1
        return f"{prefix}upload_id_{next_id:03d}/"
    except Exception:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{prefix}upload_id_{ts}/"

# =============== ОСНОВНОЙ ПРОЦЕСС =========================
if submitted:
    if not BUCKET_NAME:
        st.error("S3-бакет не настроен.")
    elif not uploaded_file:
        st.error("Не выбран файл для загрузки.")
    else:
        try:
            s3 = get_s3_client(AWS_PROFILE.strip() or None, AWS_REGION)

            original_name = uploaded_file.name
            base_prefix = (KEY_PREFIX or "").strip() or "uploads/"
            if base_prefix and not base_prefix.endswith("/"):
                base_prefix += "/"

            upload_folder = get_next_upload_folder(s3, BUCKET_NAME, base_prefix)
            input_folder = f"{upload_folder}input/"
            key = f"{input_folder}{original_name}"


            uploaded_file.seek(0)
            content_type = getattr(uploaded_file, "type", None) or "application/octet-stream"
            with st.status("Загрузка файла...", expanded=False) as status:
                s3.upload_fileobj(
                    Fileobj=uploaded_file,
                    Bucket=BUCKET_NAME,
                    Key=key,
                    ExtraArgs={"ContentType": content_type},
                )
                status.update(label="Файл загружен", state="complete")

            s3_uri = f"s3://{BUCKET_NAME}/{key}"
            st.success(f"Файл успешно загружен в {s3_uri}")

            st.session_state["last_s3_bucket"] = BUCKET_NAME
            st.session_state["last_s3_key"] = key
            st.session_state["last_s3_uri"] = s3_uri

        except NoCredentialsError:
            st.error("AWS-учётные данные не найдены. Настройте их через ~/.aws/credentials или переменные окружения.")
        except ClientError as e:
            err = e.response.get("Error", {})
            st.error(f"AWS ClientError: {err.get('Code', 'Unknown')} - {err.get('Message', str(e))}")
        except (BotoCoreError, Exception) as e:
            st.error(f"Ошибка при загрузке: {e}")
