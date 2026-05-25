import random
from pathlib import Path
from datetime import datetime

import gspread
import pandas as pd
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image


# ============================================================
# 用户参数
# ============================================================
IMAGE_DIR = "images/3band_400"
CRITERIA_IMAGE = "criteria/criteria_01.png"

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

GSHEET_ID = "179fyTvQAMNw3HQnCelxzlxumXknfDc6ETZzm7dvGL0U"

SHEET_HEADER = [
    "user_name",
    "image_name",
    "has_bar",
    "bar_ring_connected",
    "inner_ring_color_same",
    "comment",
    "timestamp",
]

HAS_BAR_OPTIONS = ["yes", "no", "unclear"]
BAR_RING_OPTIONS = ["connected", "not_connected", "unclear", "not_applicable"]
COLOR_OPTIONS = ["same", "different", "unclear"]

NOT_RING_VALUE = "not_ring"


# ============================================================
# 页面设置
# ============================================================
st.set_page_config(page_title="Ring Galaxy Classifier", layout="wide")
st.title("Ring Galaxy Classifier")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 1.0rem;
        padding-left: 1.6rem;
        padding-right: 1.6rem;
        max-width: 1320px;
    }

    h1 {
        font-size: 2.0rem !important;
        margin-bottom: 0.8rem !important;
    }

    h3 {
        font-size: 1.20rem !important;
        margin-top: 0.55rem !important;
        margin-bottom: 0.45rem !important;
    }

    h4 {
        font-size: 1.0rem !important;
        margin-top: 0.55rem !important;
        margin-bottom: 0.35rem !important;
    }

    div[data-testid="stImage"] {
        text-align: center;
    }

    div[data-testid="stImage"] img {
        max-height: 68vh;
        max-width: 100%;
        object-fit: contain;
        border-radius: 12px;
        box-shadow: 0 2px 14px rgba(0, 0, 0, 0.10);
    }

    .info-card {
        background: #f7f9fc;
        border: 1px solid #e3e7ef;
        border-radius: 12px;
        padding: 0.72rem 0.85rem;
        margin-bottom: 0.55rem;
        min-height: 4.0rem;
    }

    .info-title {
        font-size: 0.82rem;
        color: #667085;
        margin-bottom: 0.25rem;
    }

    .info-value {
        font-size: 0.98rem;
        font-weight: 650;
        color: #1f2937;
        word-break: break-word;
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 800;
        margin-top: 0.45rem;
        margin-bottom: 0.75rem;
        color: #1f2937;
    }

    .question-title {
        font-size: 0.95rem;
        font-weight: 750;
        margin-top: 0.75rem;
        margin-bottom: 0.35rem;
        color: #1f2937;
    }

    .subtle-text {
        font-size: 0.82rem;
        color: #667085;
        margin-bottom: 0.25rem;
    }

    .soft-divider {
        height: 1px;
        background: #e5e7eb;
        margin: 1.0rem 0 1.0rem 0;
    }

    div[role="radiogroup"] label {
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 0.65rem;
        padding: 0.38rem 0.65rem;
        margin-bottom: 0.25rem;
        background-color: white;
        transition: all 0.15s ease;
        min-height: 2.15rem;
    }

    div[role="radiogroup"] label:hover {
        border-color: #d6aa00;
        background-color: #fff8d6;
    }

    div[role="radiogroup"] label:has(input:checked) {
        background-color: #fff1a8 !important;
        border-color: #d6aa00 !important;
        color: #111111 !important;
        font-weight: 700 !important;
    }

    div.stButton > button {
        height: 2.35rem;
        border-radius: 0.65rem;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 0.65rem;
    }

    div[data-testid="stNumberInput"] input {
        border-radius: 0.65rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Google Sheet
# ============================================================
@st.cache_resource
def init_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope,
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(GSHEET_ID).sheet1
    return sheet


def ensure_sheet_header():
    sheet = init_gsheet()
    values = sheet.get_all_values()

    if not values:
        sheet.update("A1:G1", [SHEET_HEADER])
        return SHEET_HEADER

    header = values[0]

    if header != SHEET_HEADER:
        sheet.update("A1:G1", [SHEET_HEADER])

    return SHEET_HEADER


@st.cache_data(ttl=60, show_spinner=False)
def fetch_user_records(user_name):
    try:
        sheet = init_gsheet()
        ensure_sheet_header()

        values = sheet.get_all_values()

        if len(values) <= 1:
            return []

        header = values[0]
        records = []

        for row_idx, row in enumerate(values[1:], start=2):
            row = row + [""] * (len(header) - len(row))
            record = dict(zip(header, row))
            record["sheet_row"] = row_idx

            if str(record.get("user_name", "")).strip() == user_name:
                records.append(record)

        return records

    except Exception as e:
        st.warning(f"读取 Google Sheet 失败：{e}")
        return []


def load_user_state(user_name):
    records = fetch_user_records(user_name)

    done_names = set()
    record_map = {}

    for r in records:
        image_name = str(r.get("image_name", "")).strip()

        if not image_name:
            continue

        record_map[image_name] = r

        has_bar = str(r.get("has_bar", "")).strip()
        bar_ring_connected = str(r.get("bar_ring_connected", "")).strip()
        inner_ring_color_same = str(r.get("inner_ring_color_same", "")).strip()

        if has_bar and bar_ring_connected and inner_ring_color_same:
            done_names.add(image_name)

    st.session_state.user_records = records
    st.session_state.done_names = done_names
    st.session_state.record_map = record_map


def save_annotation(
    user_name,
    image_name,
    has_bar,
    bar_ring_connected,
    inner_ring_color_same,
    comment,
):
    sheet = init_gsheet()
    ensure_sheet_header()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_row = [
        user_name,
        image_name,
        has_bar,
        bar_ring_connected,
        inner_ring_color_same,
        comment,
        now,
    ]

    existing = st.session_state.record_map.get(image_name)

    if existing and existing.get("sheet_row"):
        sheet_row = int(existing["sheet_row"])
        sheet.update(f"A{sheet_row}:G{sheet_row}", [new_row])
    else:
        sheet.append_row(new_row, value_input_option="RAW")

    fetch_user_records.clear()
    load_user_state(user_name)


# ============================================================
# 图片读取
# ============================================================
def load_images():
    image_dir = Path(IMAGE_DIR)

    if not image_dir.exists():
        return []

    images = []

    for p in image_dir.iterdir():
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            images.append(p)

    images.sort(key=lambda x: x.name)
    return images


def get_random_unlabeled_index(images, done_names):
    candidates = [i for i, p in enumerate(images) if p.name not in done_names]

    if candidates:
        return random.choice(candidates)

    if images:
        return 0

    return None


def get_index_by_image_number(images, image_number):
    target = str(image_number)

    for i, p in enumerate(images):
        if p.stem == target:
            return i

    return None


def safe_choice(value, options, default="unclear"):
    value = str(value).strip()

    if value in options:
        return value

    return default


def load_existing_to_form(existing):
    if existing:
        old_has_bar = str(existing.get("has_bar", "")).strip()

        if old_has_bar == NOT_RING_VALUE:
            st.session_state.has_bar = "unclear"
            st.session_state.bar_ring_connected = "not_applicable"
            st.session_state.inner_ring_color_same = "unclear"
            st.session_state.comment = existing.get("comment", "") or ""
            return

        st.session_state.has_bar = safe_choice(
            existing.get("has_bar", ""),
            HAS_BAR_OPTIONS,
            default="unclear",
        )

        if st.session_state.has_bar == "no":
            st.session_state.bar_ring_connected = "not_applicable"
        else:
            st.session_state.bar_ring_connected = safe_choice(
                existing.get("bar_ring_connected", ""),
                BAR_RING_OPTIONS,
                default="unclear",
            )

        st.session_state.inner_ring_color_same = safe_choice(
            existing.get("inner_ring_color_same", ""),
            COLOR_OPTIONS,
            default="unclear",
        )

        st.session_state.comment = existing.get("comment", "") or ""

    else:
        st.session_state.has_bar = "unclear"
        st.session_state.bar_ring_connected = "unclear"
        st.session_state.inner_ring_color_same = "unclear"
        st.session_state.comment = ""


def go_to_next_unlabeled(images):
    next_idx = get_random_unlabeled_index(
        images,
        st.session_state.done_names,
    )

    if next_idx is not None:
        st.session_state.current_index = next_idx

    st.session_state.need_reload_form = True
    st.rerun()


# ============================================================
# Session State
# ============================================================
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if "last_user_name" not in st.session_state:
    st.session_state.last_user_name = ""

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "user_records" not in st.session_state:
    st.session_state.user_records = []

if "done_names" not in st.session_state:
    st.session_state.done_names = set()

if "record_map" not in st.session_state:
    st.session_state.record_map = {}

if "last_saved_message" not in st.session_state:
    st.session_state.last_saved_message = ""

if "need_reload_form" not in st.session_state:
    st.session_state.need_reload_form = True

if "has_bar" not in st.session_state:
    st.session_state.has_bar = "unclear"

if "bar_ring_connected" not in st.session_state:
    st.session_state.bar_ring_connected = "unclear"

if "inner_ring_color_same" not in st.session_state:
    st.session_state.inner_ring_color_same = "unclear"

if "comment" not in st.session_state:
    st.session_state.comment = ""


# ============================================================
# 侧边栏
# ============================================================
images = load_images()

st.sidebar.header("User")

user_name = st.sidebar.text_input(
    "请输入用户名",
    value=st.session_state.user_name,
).strip()

if user_name:
    if user_name != st.session_state.last_user_name:
        st.session_state.user_name = user_name
        st.session_state.last_user_name = user_name

        load_user_state(user_name)

        next_idx = get_random_unlabeled_index(
            images,
            st.session_state.done_names,
        )

        if next_idx is not None:
            st.session_state.current_index = next_idx

        st.session_state.need_reload_form = True
        st.rerun()

    else:
        st.session_state.user_name = user_name

if not st.session_state.user_name:
    st.info("请先在左侧输入用户名。")
    st.stop()

user_name = st.session_state.user_name

if not images:
    st.error(f"没有在 `{IMAGE_DIR}` 中找到图片。")
    st.stop()

num_total = len(images)
num_done = len(st.session_state.done_names)

st.sidebar.markdown(f"**当前用户：** {user_name}")
st.sidebar.markdown(f"**已完成：** {num_done} / {num_total}")

if st.sidebar.button("刷新当前用户记录", use_container_width=True):
    load_user_state(user_name)
    st.session_state.need_reload_form = True
    st.rerun()


st.sidebar.markdown("---")
show_criteria = st.sidebar.checkbox("显示分类标准", value=False)

if st.session_state.user_records:
    df_export = pd.DataFrame(st.session_state.user_records)
    df_export = df_export.drop(columns=["sheet_row"], errors="ignore")

    csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")

    st.sidebar.download_button(
        "导出当前用户 CSV",
        data=csv_bytes,
        file_name=f"annotations_{user_name}.csv",
        mime="text/csv",
    )


# ============================================================
# 当前图片
# ============================================================
current_index = max(0, min(st.session_state.current_index, num_total - 1))
st.session_state.current_index = current_index

current_image = images[current_index]
existing = st.session_state.record_map.get(current_image.name)

if st.session_state.need_reload_form:
    load_existing_to_form(existing)
    st.session_state.need_reload_form = False


# ============================================================
# 分类标准
# ============================================================
if show_criteria:
    st.markdown("## 分类标准")

    if Path(CRITERIA_IMAGE).exists():
        st.image(
            CRITERIA_IMAGE,
            caption=CRITERIA_IMAGE,
            use_container_width=True,
        )
    else:
        st.warning(f"没有找到分类标准图片：{CRITERIA_IMAGE}")


# ============================================================
# 主界面
# ============================================================
left, right = st.columns([3.2, 2.2], gap="large")

with left:
    info1, info2, info3 = st.columns(3)

    with info1:
        st.markdown(
            f"""
            <div class="info-card">
                <div class="info-title">当前图片</div>
                <div class="info-value">{current_index + 1} / {num_total}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with info2:
        st.markdown(
            f"""
            <div class="info-card">
                <div class="info-title">文件名</div>
                <div class="info-value">{current_image.name}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with info3:
        if current_image.name in st.session_state.done_names:
            status_text = "已标注"
            status_color = "#067647"
            status_bg = "#ecfdf3"
        else:
            status_text = "未标注"
            status_color = "#175cd3"
            status_bg = "#eff8ff"

        st.markdown(
            f"""
            <div class="info-card" style="background:{status_bg};">
                <div class="info-title">状态</div>
                <div class="info-value" style="color:{status_color};">{status_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    try:
        img = Image.open(current_image)

        st.image(
            img,
            caption=current_image.name,
            width=560,
        )

    except Exception as e:
        st.error(f"图片读取失败：{e}")


with right:
    with st.container(height=760, border=False):

        st.markdown('<div class="section-title">快速判断</div>', unsafe_allow_html=True)

        if st.button("not_ring：不是环星系，直接下一张", use_container_width=True):
            save_annotation(
                user_name=user_name,
                image_name=current_image.name,
                has_bar=NOT_RING_VALUE,
                bar_ring_connected="not_applicable",
                inner_ring_color_same="not_applicable",
                comment=st.session_state.comment,
            )

            st.session_state.last_saved_message = (
                f"已保存：{current_image.name} | not_ring"
            )

            go_to_next_unlabeled(images)

        st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title">三个问题</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="question-title">1. 该星系是否有棒？</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "该星系是否有棒？",
            HAS_BAR_OPTIONS,
            key="has_bar",
            horizontal=True,
            label_visibility="collapsed",
            format_func=lambda x: {
                "yes": "yes：有棒",
                "no": "no：无棒",
                "unclear": "unclear：不确定",
            }.get(x, x),
        )

        if st.session_state.has_bar == "no":
            st.session_state.bar_ring_connected = "not_applicable"

            st.markdown(
                '<div class="question-title">2. 棒和环是否相连？</div>',
                unsafe_allow_html=True,
            )

            st.info("第一题选择了 no：无棒，因此第二题自动记为 not_applicable。")

        else:
            st.markdown(
                '<div class="question-title">2. 棒和环是否相连？</div>',
                unsafe_allow_html=True,
            )

            st.radio(
                "棒和环是否相连？",
                BAR_RING_OPTIONS,
                key="bar_ring_connected",
                horizontal=False,
                label_visibility="collapsed",
                format_func=lambda x: {
                    "connected": "connected：相连",
                    "not_connected": "not_connected：不相连",
                    "unclear": "unclear：不确定",
                    "not_applicable": "not_applicable：不适用",
                }.get(x, x),
            )

        st.markdown(
            '<div class="question-title">3. 星系内部颜色和环的颜色是否相同？</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "星系内部颜色和环的颜色是否相同？",
            COLOR_OPTIONS,
            key="inner_ring_color_same",
            horizontal=True,
            label_visibility="collapsed",
            format_func=lambda x: {
                "same": "same：相同",
                "different": "different：不同",
                "unclear": "unclear：不确定",
            }.get(x, x),
        )

        st.markdown("#### 备注")
        st.text_input("备注，可选", key="comment", label_visibility="collapsed")

        if st.button("保存并下一张", use_container_width=True, type="primary"):
            save_annotation(
                user_name=user_name,
                image_name=current_image.name,
                has_bar=st.session_state.has_bar,
                bar_ring_connected=st.session_state.bar_ring_connected,
                inner_ring_color_same=st.session_state.inner_ring_color_same,
                comment=st.session_state.comment,
            )

            st.session_state.last_saved_message = (
                f"已保存：{current_image.name} | "
                f"has_bar={st.session_state.has_bar}, "
                f"bar_ring_connected={st.session_state.bar_ring_connected}, "
                f"inner_ring_color_same={st.session_state.inner_ring_color_same}"
            )

            go_to_next_unlabeled(images)

        st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title">快速跳转</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subtle-text">输入图片编号，例如 123 对应 123.png</div>',
            unsafe_allow_html=True,
        )

        default_number = int(current_image.stem) if current_image.stem.isdigit() else 1

        jump_number = st.number_input(
            "输入图片编号，例如 123 对应 123.png",
            min_value=1,
            value=default_number,
            step=1,
            label_visibility="collapsed",
        )

        if st.button("跳转到该图片", use_container_width=True):
            target_idx = get_index_by_image_number(images, int(jump_number))

            if target_idx is not None:
                st.session_state.current_index = target_idx
                st.session_state.need_reload_form = True
                st.rerun()
            else:
                st.warning(f"没有找到编号为 {int(jump_number)} 的图片。")


if st.session_state.last_saved_message:
    st.success(st.session_state.last_saved_message)