import streamlit as st
from .messages import VALIDATION_MESSAGES


def display_validation_result(data: dict) -> None:
    if data is None:
        st.error("Ошибка валидации")
        return

    verdict = data.get("verdict")
    if verdict is not None:
        msg = VALIDATION_MESSAGES["verdict"].get(bool(verdict))
        st.success(msg) if verdict else st.error(msg)

    checks_source = data.get("checks") if isinstance(data.get("checks"), dict) else data
    if isinstance(checks_source, dict):
        for check_key, msg_map in VALIDATION_MESSAGES["checks"].items():
            result = checks_source.get(check_key)
            if isinstance(result, bool):
                if result:
                    st.error(msg_map[result])
                else:
                    st.success(msg_map[result])
