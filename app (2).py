
import streamlit as st
from pathlib import Path
import tempfile
import zipfile
import shutil
import uuid
import sys

PROJECT = Path(tempfile.gettempdir()) / "ai-shorts-studio"
UPLOAD_DIR = PROJECT / "uploads"
OUTPUT_DIR = PROJECT / "outputs"
SHORTS_DIR = OUTPUT_DIR / "shorts"
VERTICAL_DIR = OUTPUT_DIR / "vertical"
CAPTION_DIR = OUTPUT_DIR / "captions"

for folder in [
    UPLOAD_DIR,
    SHORTS_DIR,
    VERTICAL_DIR,
    CAPTION_DIR
]:
    folder.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shorts_engine import generate_shorts


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="AI Shorts Studio",
    page_icon="🎬",
    layout="wide"
)


# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>

.stApp {
    background: #080b12;
    color: #f5f7fa;
}

.block-container {
    max-width: 1250px;
    padding-top: 2rem;
}

.main-title {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 5px;
}

.subtitle {
    color: #9aa4b2;
    font-size: 17px;
    margin-bottom: 30px;
}

.card {
    background: #111722;
    border: 1px solid #202938;
    border-radius: 16px;
    padding: 22px;
    margin-bottom: 18px;
}

.small {
    color: #9aa4b2;
    font-size: 14px;
}

div[data-testid="stSidebar"] {
    background: #0b0f17;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎬 AI Shorts Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Turn long videos into engaging AI-powered short videos.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## ⚙️ Settings")

    aspect_ratio = st.selectbox(
        "Aspect Ratio",
        ["9:16", "16:9", "1:1"]
    )

    max_duration = st.selectbox(
        "Maximum Short Duration",
        [30, 45, 60, 90],
        index=2
    )

    number_of_shorts = st.slider(
        "Number of Shorts",
        1,
        20,
        5
    )

    ai_titles = st.checkbox(
        "🤖 AI Titles",
        True
    )

    auto_captions = st.checkbox(
        "💬 Auto Captions",
        True
    )

    thumbnail_text = st.checkbox(
        "🖼️ Thumbnail Text",
        True
    )

    st.divider()

    st.markdown("### 📊 Current Files")

    current_shorts = list(
        SHORTS_DIR.glob("*.mp4")
    )

    current_vertical = list(
        VERTICAL_DIR.glob("*.mp4")
    )

    st.write(
        f"🎞️ Shorts: **{len(current_shorts)}**"
    )

    st.write(
        f"📱 Vertical: **{len(current_vertical)}**"
    )


# ============================================================
# UPLOAD
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True
)

st.subheader("📤 Upload Long Video")

uploaded_file = st.file_uploader(
    "Choose a video",
    type=["mp4", "mov", "mkv", "avi"]
)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# SCRIPT
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True
)

st.subheader("📝 Script / Transcript")

script_text = st.text_area(
    "Optional transcript",
    height=180,
    placeholder=(
        "You can paste your transcript here. "
        "If empty, Whisper will automatically transcribe the video."
    )
)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# GENERATE
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True
)

generate = st.button(
    "🚀 Generate AI Shorts",
    type="primary",
    use_container_width=True
)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PROCESS
# ============================================================

if generate:

    if uploaded_file is None:

        st.error(
            "❌ Please upload a video first."
        )

    else:

        # ----------------------------------------------------
        # Unique project ID
        # ----------------------------------------------------

        story_id = uuid.uuid4().hex[:10]

        safe_name = uploaded_file.name

        video_path = (
            UPLOAD_DIR /
            f"{story_id}_{safe_name}"
        )


        # ----------------------------------------------------
        # Save uploaded video
        # ----------------------------------------------------

        with open(video_path, "wb") as f:

            f.write(
                uploaded_file.getbuffer()
            )


        st.success(
            f"✅ New video uploaded: {uploaded_file.name}"
        )


        # ----------------------------------------------------
        # IMPORTANT:
        # Delete old generated results
        # ----------------------------------------------------

        for folder in [
            SHORTS_DIR,
            VERTICAL_DIR,
            CAPTION_DIR
        ]:

            for file in folder.glob("*"):

                if file.is_file():

                    try:
                        file.unlink()
                    except:
                        pass


        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        progress = st.progress(0)

        status = st.empty()


        try:

            status.write(
                "🎤 Step 1/5 — Transcribing video with Whisper..."
            )

            progress.progress(10)


            result = generate_shorts(
                video_path=str(video_path),
                number_of_shorts=number_of_shorts,
                aspect_ratio=aspect_ratio,
                max_duration=max_duration
            )


            progress.progress(75)

            status.write(
                "🎬 Step 4/5 — Preparing generated shorts..."
            )


            # ------------------------------------------------
            # Results
            # ------------------------------------------------

            selected = result["selected"]

            vertical_files = result["vertical"]

            progress.progress(90)

            status.write(
                "📦 Step 5/5 — Creating ZIP package..."
            )


            # ------------------------------------------------
            # ZIP
            # ------------------------------------------------

            zip_path = (
                PROJECT /
                f"AI_Shorts_{story_id}.zip"
            )


            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zipf:

                for video in vertical_files:

                    video = Path(video)

                    if video.exists():

                        zipf.write(
                            video,
                            arcname=video.name
                        )


            progress.progress(100)

            status.success(
                "🎉 AI Shorts generation completed!"
            )


            # ------------------------------------------------
            # Summary
            # ------------------------------------------------

            st.markdown("## ✅ Generated Shorts")

            st.write(
                f"**Shorts created:** {len(vertical_files)}"
            )

            st.write(
                f"**Aspect ratio:** {aspect_ratio}"
            )


            # ------------------------------------------------
            # Selected segments
            # ------------------------------------------------

            for i, short in enumerate(
                selected,
                1
            ):

                title = (
                    short.get("text", "")
                    .strip()
                )

                if len(title) > 100:

                    title = title[:100] + "..."


                st.markdown(
                    f"### Short {i}"
                )

                if title:

                    st.caption(title)


                if i <= len(vertical_files):

                    video = Path(
                        vertical_files[i - 1]
                    )

                    if video.exists():

                        st.video(
                            str(video)
                        )

                        with open(
                            video,
                            "rb"
                        ) as f:

                            st.download_button(
                                "⬇️ Download Short",
                                f.read(),
                                file_name=video.name,
                                mime="video/mp4",
                                key=f"download_new_{story_id}_{i}"
                            )


            # ------------------------------------------------
            # ZIP
            # ------------------------------------------------

            st.markdown("## 📦 Download All")

            if zip_path.exists():

                with open(
                    zip_path,
                    "rb"
                ) as f:

                    st.download_button(
                        "⬇️ Download All Shorts ZIP",
                        f.read(),
                        file_name=zip_path.name,
                        mime="application/zip",
                        use_container_width=True
                    )


        except Exception as e:

            progress.empty()

            status.empty()

            st.error(
                "❌ Generation failed."
            )

            st.exception(e)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    '<div class="small">'
    'AI Shorts Studio • Whisper + FFmpeg • Google Colab'
    '</div>',
    unsafe_allow_html=True
)
