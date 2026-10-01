
import json
import re
import subprocess
from pathlib import Path

import torch
import whisper


# ============================================================
# DIRECTORIES
# ============================================================

PROJECT = Path("/content/ai-shorts-studio")

UPLOAD_DIR = PROJECT / "uploads"
OUTPUT_DIR = PROJECT / "outputs"

SHORTS_DIR = OUTPUT_DIR / "shorts"
VERTICAL_DIR = OUTPUT_DIR / "vertical"
CAPTION_DIR = OUTPUT_DIR / "captions"
CAPTIONED_DIR = OUTPUT_DIR / "captioned"

for folder in [
    UPLOAD_DIR,
    SHORTS_DIR,
    VERTICAL_DIR,
    CAPTION_DIR,
    CAPTIONED_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# WHISPER
# ============================================================

_model = None


def get_whisper_model():

    global _model

    if _model is None:

        device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"Loading Whisper on {device}...")

        _model = whisper.load_model(
            "small",
            device=device
        )

    return _model


# ============================================================
# TRANSCRIPTION
# ============================================================

def transcribe_video(video_path):

    video_path = str(video_path)

    model = get_whisper_model()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    result = model.transcribe(
        video_path,
        fp16=(device == "cuda"),
        verbose=False
    )

    transcript_file = PROJECT / "whisper_transcript.json"

    with open(
        transcript_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    return result


# ============================================================
# BUILD CANDIDATES
# ============================================================

def build_candidates(
    whisper_result,
    min_duration=20,
    max_duration=60
):

    segments = []

    for i, segment in enumerate(
        whisper_result.get("segments", []),
        1
    ):

        text = segment.get("text", "").strip()

        if not text:
            continue

        segments.append(
            {
                "id": i,
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "text": text,
            }
        )


    candidates = []

    for i in range(len(segments)):

        start = segments[i]["start"]

        collected = []

        for j in range(i, len(segments)):

            end = segments[j]["end"]

            duration = end - start

            if duration > max_duration:
                break

            collected.append(
                segments[j]["text"]
            )

            if duration >= min_duration:

                candidates.append(
                    {
                        "start": round(start, 2),
                        "end": round(end, 2),
                        "duration": round(duration, 2),
                        "text": " ".join(collected),
                    }
                )


    return candidates


# ============================================================
# SCORE
# ============================================================

POWER_WORDS = {
    "love",
    "life",
    "world",
    "money",
    "king",
    "queen",
    "sorry",
    "remember",
    "never",
    "always",
    "baby",
    "friend",
    "friends",
    "heart",
    "dream",
    "truth",
    "ਜੱਟ",
    "ਪਿਆਰ",
    "ਦਿਲ",
    "ਸੱਚ",
}


def score_candidate(candidate):

    text = candidate["text"].lower()

    words = re.findall(
        r"\b[\w'-]+\b",
        text
    )

    if not words:
        return 0


    score = 0

    duration = candidate["duration"]


    # Good short-video duration

    if 25 <= duration <= 50:

        score += 20

    elif 20 <= duration <= 60:

        score += 10


    # More useful words

    score += min(
        len(words) / 2,
        20
    )


    # Power words

    score += sum(
        1
        for word in words
        if word in POWER_WORDS
    ) * 5


    # Vocabulary variety

    unique_ratio = (
        len(set(words))
        /
        max(len(words), 1)
    )


    if unique_ratio > 0.65:

        score += 10

    elif unique_ratio < 0.35:

        score -= 10


    return round(score, 2)


# ============================================================
# SELECT BEST SHORTS
# ============================================================

def select_best_shorts(
    candidates,
    number_of_shorts=5
):

    scored = []

    for candidate in candidates:

        item = dict(candidate)

        item["score"] = score_candidate(
            candidate
        )

        scored.append(item)


    scored.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    selected = []


    for candidate in scored:

        overlaps = False

        for existing in selected:

            if not (
                candidate["end"] <= existing["start"]
                or
                candidate["start"] >= existing["end"]
            ):

                overlaps = True

                break


        if not overlaps:

            selected.append(candidate)


        if len(selected) >= number_of_shorts:

            break


    selected.sort(
        key=lambda x: x["start"]
    )


    for i, item in enumerate(
        selected,
        1
    ):

        item["short_number"] = i


    with open(
        PROJECT / "candidates.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            scored,
            f,
            ensure_ascii=False,
            indent=2
        )


    with open(
        PROJECT / "selected_shorts.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            selected,
            f,
            ensure_ascii=False,
            indent=2
        )


    return selected


# ============================================================
# CUT SHORTS
# ============================================================

def cut_shorts(
    video_path,
    selected_shorts
):

    video_path = str(video_path)

    created = []

    for i, short in enumerate(
        selected_shorts,
        1
    ):

        output = (
            SHORTS_DIR /
            f"short_{i:02d}.mp4"
        )

        start = short["start"]

        duration = (
            short["end"]
            -
            short["start"]
        )


        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            video_path,
            "-t",
            str(duration),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output),
        ]


        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )


        created.append(output)


    return created


# ============================================================
# ASPECT RATIO
# ============================================================

def convert_vertical(
    short_files,
    aspect_ratio="9:16"
):

    created = []

    for i, source in enumerate(
        short_files,
        1
    ):

        output = (
            VERTICAL_DIR /
            f"short_{i:02d}_{aspect_ratio.replace(':', 'x')}.mp4"
        )


        if aspect_ratio == "9:16":

            vf = (
                "scale=768:1344:"
                "force_original_aspect_ratio=decrease,"
                "pad=768:1344:(ow-iw)/2:(oh-ih)/2"
            )

        elif aspect_ratio == "16:9":

            vf = (
                "scale=1344:768:"
                "force_original_aspect_ratio=decrease,"
                "pad=1344:768:(ow-iw)/2:(oh-ih)/2"
            )

        else:

            vf = (
                "scale=1024:1024:"
                "force_original_aspect_ratio=decrease,"
                "pad=1024:1024:(ow-iw)/2:(oh-ih)/2"
            )


        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output),
        ]


        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )


        created.append(output)


    return created


# ============================================================
# SRT
# ============================================================

def srt_time(seconds):

    total_ms = round(
        seconds * 1000
    )

    hours = total_ms // 3600000

    total_ms %= 3600000

    minutes = total_ms // 60000

    total_ms %= 60000

    secs = total_ms // 1000

    milliseconds = total_ms % 1000


    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d},"
        f"{milliseconds:03d}"
    )


def create_captions(
    whisper_result,
    selected_shorts
):

    files = []


    for i, short in enumerate(
        selected_shorts,
        1
    ):

        short_start = float(
            short["start"]
        )

        short_end = float(
            short["end"]
        )


        srt_file = (
            CAPTION_DIR /
            f"short_{i:02d}.srt"
        )


        lines = []

        number = 1


        for segment in whisper_result.get(
            "segments",
            []
        ):

            seg_start = float(
                segment["start"]
            )

            seg_end = float(
                segment["end"]
            )

            text = segment.get(
                "text",
                ""
            ).strip()


            if not text:
                continue

            if seg_end <= short_start:
                continue

            if seg_start >= short_end:
                break


            caption_start = (
                max(
                    seg_start,
                    short_start
                )
                -
                short_start
            )


            caption_end = (
                min(
                    seg_end,
                    short_end
                )
                -
                short_start
            )


            if caption_end <= caption_start:
                continue


            lines.append(
                f"{number}\n"
                f"{srt_time(caption_start)} --> "
                f"{srt_time(caption_end)}\n"
                f"{text}\n"
            )


            number += 1


        srt_file.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )


        files.append(srt_file)


    return files


# ============================================================
# COMPLETE PIPELINE
# ============================================================

def generate_shorts(
    video_path,
    number_of_shorts=5,
    aspect_ratio="9:16",
    max_duration=60
):

    print("🎬 Starting AI Shorts pipeline...")


    print("🎤 Transcribing video...")

    whisper_result = transcribe_video(
        video_path
    )


    print("🧠 Finding candidate segments...")

    candidates = build_candidates(
        whisper_result,
        min_duration=20,
        max_duration=max_duration
    )


    print(
        f"🔎 Candidates found: {len(candidates)}"
    )


    print("⭐ Selecting best shorts...")

    selected = select_best_shorts(
        candidates,
        number_of_shorts
    )


    print(
        f"✅ Selected: {len(selected)}"
    )


    print("✂️ Cutting videos...")

    shorts = cut_shorts(
        video_path,
        selected
    )


    print("📱 Creating requested aspect ratio...")

    vertical = convert_vertical(
        shorts,
        aspect_ratio
    )


    print("💬 Creating captions...")

    captions = create_captions(
        whisper_result,
        selected
    )


    print("🎉 Pipeline completed!")


    return {
        "transcript": whisper_result,
        "selected": selected,
        "shorts": shorts,
        "vertical": vertical,
        "captions": captions,
    }
