from datetime import datetime, timezone, timedelta
import re
import json
from io import BytesIO

from botocore.exceptions import BotoCoreError, NoCredentialsError, ClientError
import streamlit as st
from app.config import load_config
from app.aws.session import get_s3_client
from app.aws.s3_ops import get_next_upload_folder, upload_fileobj, put_json, get_json_or_none
from app.utils.polling import wait_for
from app.validation.render import display_validation_result
from PyPDF2 import PdfReader

# ======================= UI ЧАСТЬ =========================
st.set_page_config(page_title="S3 File Uploader", layout="centered")

st.write("")
st.title("RB Loan Deferment IDP")
st.write("Загрузите один файл в Amazon S3.")

# --- Основные параметры ---
cfg = load_config()

# --- Кастомизация интерфейса ---

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# --- Причина отсрочки (вне формы для динамики) ---
reasons_map = {
    "Временная нетрудоспособность заемщика по причине болезни": [
        "Лист временной нетрудоспособности (больничный лист)",
        "Выписка из стационара (выписной эпикриз)",
        "Больничный лист на сопровождающего (если предусмотрено)",
        "Заключение врачебно-консультативной комиссии (ВКК).",
        "Справка об инвалидности.",
        "Справка о степени утраты общей трудоспособности.",
    ],
    "Уход заемщика в декретный отпуск": [
        "Лист временной нетрудоспособности (больничный лист)",
        "Приказ о выходе в декретный отпуск по уходу за ребенком",
        "Справка о выходе в декретный отпуск по уходу за ребенком",
    ],
    "Потеря дохода заемщика (увольнение, сокращение, отпуск без содержания и т.д.)": [
        "Приказ/Справка о расторжении трудового договора",
        "Справка о регистрации в качестве безработного",
        "Приказ работодателя о предоставлении отпуска без сохранения заработной платы",
        "Справка о неполучении доходов",
        "Уведомление о регистрации в качестве лица, ищущего работу",
        "Лица, зарегистрированные в качестве безработных",
    ],
}
fio = st.text_input("ФИО", placeholder="Иванов Иван Иванович")

reason_options = ["Выберите причину"] + list(reasons_map.keys())
reason = st.selectbox(
    "Причина отсрочки",
    options=reason_options,
    index=0,
    help="Сначала выберите причину, затем подходящий тип документа",
    key="reason",
)


doc_options = ["Выберите тип документа"] + (
    reasons_map[reason] if reason in reasons_map else []
)
doc_type = st.selectbox(
    "Тип документа",
    options=doc_options,
    index=0,
    key="doc_type",
)

# --- Форма загрузки ---
with st.form("upload_form", clear_on_submit=False):

    uploaded_file = st.file_uploader(
        "Выберите документ",
        type=["pdf", "jpg", "png", "jpeg"],
        accept_multiple_files=False,
        help="Поддержка: PDF, JPEG",
    )
    submitted = st.form_submit_button("Загрузить", type="primary")


# =============== ОСНОВНОЙ ПРОЦЕСС =========================
if submitted:
    if not cfg.bucket_name:
        st.error("S3-бакет не настроен.")
    elif not fio:
        st.error("Укажите ФИО")
    elif reason == "Выберите причину":
        st.error("Выберите причину отсрочки.")
    elif doc_type == "Выберите тип документа":
        st.error("Выберите тип документа.")
    elif not uploaded_file:
        st.error("Не выбран файл для загрузки.")
    else:
        # Проверка количества страниц для PDF (не более 3)
        if (
            getattr(uploaded_file, "type", "") == "application/pdf"
            or str(getattr(uploaded_file, "name", "")).lower().endswith(".pdf")
        ):
            try:
                pdf_bytes = uploaded_file.getvalue()
                reader = PdfReader(BytesIO(pdf_bytes))
                if len(reader.pages) > 3:
                    st.error("PDF-документ должен содержать не более 3 страниц.")
                    st.stop()
            except Exception as e:
                st.error(f"Не удалось прочитать PDF: {e}")
                st.stop()
            finally:
                uploaded_file.seek(0)
        try:
            s3 = get_s3_client(cfg.aws_profile.strip() or None, cfg.aws_region)

            original_name = uploaded_file.name
            base_prefix = (cfg.key_prefix or "").strip() or "uploads/"
            if base_prefix and not base_prefix.endswith("/"):
                base_prefix += "/"

            upload_folder = get_next_upload_folder(s3, cfg.bucket_name, base_prefix)
            input_folder = f"{upload_folder}input/"
            key = f"{input_folder}{original_name}"

            uploaded_file.seek(0)
            content_type = (
                getattr(uploaded_file, "type", None) or "application/octet-stream"
            )
            with st.status("Загрузка файла...", expanded=False) as status:
                upload_fileobj(
                    s3_client=s3,
                    bucket=cfg.bucket_name,
                    key=key,
                    fileobj=uploaded_file,
                    content_type=content_type,
                )
                request_dt = datetime.now(timezone(timedelta(hours=cfg.timezone_offset_hours)))
                request_date = request_dt.strftime("%d.%m.%Y")
                meta_key = f"{upload_folder}metadata.json"
                metadata = {"full_name": fio, "request_reason": reason, "doc_type": doc_type, "request_date": request_date}
                put_json(s3_client=s3, bucket=cfg.bucket_name, key=meta_key, data=metadata)
                s3_uri = f"s3://{cfg.bucket_name}/{key}"
                s3_meta_uri = f"s3://{cfg.bucket_name}/{meta_key}"
                st.write(f"Файл успешно загружен в {s3_uri}")
                st.write(f"Метаданные успешно загружены в {s3_meta_uri}")
                status.update(label="Файл загружен", state="complete")

            st.session_state["last_s3_bucket"] = cfg.bucket_name
            st.session_state["last_s3_key"] = key
            st.session_state["last_s3_uri"] = s3_uri

            st.session_state["last_s3_meta_key"] = meta_key
            st.session_state["last_s3_meta_uri"] = s3_meta_uri

            st.session_state["last_upload_folder"] = upload_folder
            result_key = f"{upload_folder}output/validation.json"
            st.session_state["last_validation_key"] = result_key

            with st.status("Ожидание результата обработки...", expanded=False) as status:
                validation = wait_for(lambda: get_json_or_none(s3, cfg.bucket_name, result_key), timeout_sec=18, interval_sec=1.0)
                if validation is not None:
                    status.update(label="Результаты получены", state="complete")
                    st.session_state["last_validation"] = validation
                    display_validation_result(validation)
                else:
                    status.update(label="Результаты пока не готовы", state="complete")

        except NoCredentialsError:
            st.error(
                "AWS-учётные данные не найдены. Настройте их через ~/.aws/credentials или переменные окружения."
            )
        except ClientError as e:
            err = e.response.get("Error", {})
            st.error(
                f"AWS ClientError: {err.get('Code', 'Unknown')} - {err.get('Message', str(e))}"
            )
        except (BotoCoreError, Exception) as e:
            st.error(f"Ошибка при загрузке: {e}")

if st.session_state.get("last_upload_folder"):
    if st.button("Проверить результат", key="check_validation"):
        try:
            s3 = get_s3_client(cfg.aws_profile.strip() or None, cfg.aws_region)
            result_key = st.session_state.get("last_validation_key") or f"{st.session_state['last_upload_folder']}output/validation.json"
            with st.status("Проверка результата...", expanded=False) as status:
                validation = wait_for(lambda: get_json_or_none(s3, cfg.bucket_name, result_key), timeout_sec=6, interval_sec=1.0)
                if validation is not None:
                    status.update(label="Результаты получены", state="complete")
                    st.session_state["last_validation"] = validation
                    display_validation_result(validation)
                else:
                    status.update(label="Результаты не найдены", state="complete")
        except ClientError as e:
            err = e.response.get("Error", {})
            st.error(f"AWS ClientError: {err.get('Code', 'Unknown')} - {err.get('Message', str(e))}")
        except (BotoCoreError, Exception) as e:
            st.error(f"Ошибка при проверке: {e}")
