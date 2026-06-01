"""JARVIS — local owner assistant for RO Guard (not deployed to dealerships)."""

from __future__ import annotations

import streamlit as st

from jarvis.assistant import ask_jarvis
from jarvis.config import JARVIS_PORT, OLLAMA_MODEL, REPO_ROOT
from jarvis.context import build_context
from jarvis.ollama import list_models, ping
from jarvis.supabase_client import load_metrics, load_review_dataframe
from jarvis.voice import list_mac_voices, speak_text, transcribe_audio, voice_stack_status

st.set_page_config(
    page_title="JARVIS · RO Guard",
    page_icon="🛡️",
    layout="wide",
)

QUICK_PROMPTS = [
    "Summarize our warranty audit performance in plain English.",
    "Which advisors need coaching based on hard stops and scores?",
    "What rejection patterns should we fix first?",
    "How many claims are still pending an OEM outcome?",
    "What should I focus on this week as warranty manager?",
]


@st.cache_data(ttl=120, show_spinner="Loading reviews from Supabase…")
def _cached_reviews():
    return load_review_dataframe()


def _ensure_chat_state() -> None:
    if "jarvis_messages" not in st.session_state:
        st.session_state.jarvis_messages = []


def _append_exchange(prompt: str, answer: str) -> None:
    st.session_state.jarvis_messages.append({"role": "user", "content": prompt})
    st.session_state.jarvis_messages.append({"role": "assistant", "content": answer})


def _render_chat_tab(*, context: str, selected_model: str, disabled: bool) -> None:
    st.markdown("#### Quick questions")
    qcols = st.columns(2)
    for idx, prompt in enumerate(QUICK_PROMPTS):
        with qcols[idx % 2]:
            if st.button(prompt, key=f"quick_{idx}", disabled=disabled, use_container_width=True):
                st.session_state["_jarvis_pending_prompt"] = prompt

    for message in st.session_state.jarvis_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending = st.session_state.pop("_jarvis_pending_prompt", None)
    user_input = st.chat_input(
        "Ask about reviews, advisors, rejections, ROI…",
        disabled=disabled,
    )
    prompt = pending or user_input

    if prompt and not disabled:
        with st.spinner("Thinking locally via Ollama…"):
            answer, err = ask_jarvis(
                prompt,
                context,
                model=selected_model,
                history=st.session_state.jarvis_messages[-6:],
            )
        if err:
            _append_exchange(prompt, f"⚠️ {err}")
        else:
            _append_exchange(prompt, answer)
        st.rerun()


def _render_voice_tab(
    *,
    context: str,
    selected_model: str,
    disabled: bool,
    whisper_size: str,
    speak_answers: bool,
    voice_name: str,
) -> None:
    voice_ok, voice_msg = voice_stack_status()

    st.markdown("#### Voice command")
    st.caption(
        "Record a question with your microphone. Speech is transcribed **on this Mac** "
        "(Whisper). Answers can be read aloud with macOS **say** — no cloud voice API."
    )

    if not voice_ok:
        st.warning(voice_msg)
        st.code("python3 -m pip install -r jarvis/requirements.txt\nbrew install ffmpeg", language="bash")
    elif not disabled:
        st.success(voice_msg)

    recording = st.audio_input(
        "Tap to record, then click **Ask with voice**",
        key="jarvis_voice_input",
    )

    if recording is not None:
        st.audio(recording, format="audio/wav")

    ask_voice = st.button(
        "Ask with voice",
        type="primary",
        disabled=disabled or not voice_ok or recording is None,
        use_container_width=True,
    )

    if ask_voice and recording is not None:
        audio_bytes = recording.getvalue()
        with st.spinner("Transcribing locally…"):
            transcript, tx_err = transcribe_audio(audio_bytes, model_size=whisper_size)
        if tx_err:
            st.error(tx_err)
            return

        st.markdown("**You said:**")
        st.info(transcript)

        with st.spinner("Thinking locally via Ollama…"):
            answer, err = ask_jarvis(
                transcript,
                context,
                model=selected_model,
                history=st.session_state.jarvis_messages[-6:],
            )
        if err:
            st.error(err)
            _append_exchange(transcript, f"⚠️ {err}")
            st.rerun()
            return

        st.markdown("**JARVIS:**")
        st.success(answer)
        _append_exchange(transcript, answer)

        if speak_answers:
            with st.spinner("Speaking answer…"):
                audio_out, sp_err = speak_text(answer, voice=voice_name)
            if sp_err:
                st.warning(sp_err)
            elif audio_out:
                st.audio(audio_out, format="audio/aiff")
        st.rerun()

    st.markdown("---")
    st.markdown("**Example voice questions**")
    st.markdown(
        "- *How many reviews are pending an OEM outcome?*\n"
        "- *Which advisor has the most hard stops?*\n"
        "- *What's our first-pass paid rate?*\n"
        "- *Summarize this week in one minute.*"
    )


def main() -> None:
    _ensure_chat_state()

    st.title("JARVIS")
    st.caption(
        "Private, local assistant for RO Guard owners. Runs on **your Mac only** — "
        "not part of the dealership Streamlit app and not deployed to store networks."
    )
    st.info(
        "**Hands-free (no buttons):** in Terminal run `./jarvis/listen.sh`, then say "
        '**"Hey Jarvis"**, pause, and ask your question. JARVIS listens continuously on this Mac.'
    )

    df, data_err = _cached_reviews()
    metrics = load_metrics(df) if not df.empty else {}
    context = build_context(df, metrics)

    ollama_ok, ollama_msg = ping()
    models, models_err = list_models()
    model_options = models or [OLLAMA_MODEL]

    with st.sidebar:
        st.markdown("### Status")
        if data_err:
            st.error(data_err)
        else:
            st.success(f"Supabase · {len(df):,} reviews loaded")

        if ollama_ok:
            st.success(ollama_msg)
        else:
            st.error(ollama_msg)
            st.markdown(
                "**Setup:** install [Ollama](https://ollama.com), then run:\n"
                "```bash\nollama pull llama3.2\n```"
            )

        voice_ok, voice_note = voice_stack_status()
        if voice_ok:
            st.success(voice_note)
        else:
            st.warning("Voice optional — text chat still works.")

        selected_model = st.selectbox(
            "Ollama model",
            options=model_options,
            index=0,
            help="Inference stays on this computer.",
        )
        if models_err and models:
            st.caption(models_err)

        st.markdown("---")
        st.markdown("### Voice settings")
        whisper_size = st.selectbox(
            "Whisper size",
            ["tiny", "base", "small"],
            index=1,
            help="Smaller = faster. First use downloads the model once.",
        )
        speak_answers = st.checkbox("Speak answers aloud (macOS)", value=True)
        voice_name = st.selectbox("Voice", list_mac_voices())

        st.markdown("---")
        st.markdown("### Data scope")
        st.caption(f"Repo: `{REPO_ROOT.name}`")
        st.caption("Uses the same Supabase project as RO Guard (read-only usage).")
        if st.button("Refresh data", use_container_width=True):
            _cached_reviews.clear()
            st.rerun()

        if st.button("Clear chat", use_container_width=True):
            st.session_state.jarvis_messages = []
            st.rerun()

        with st.expander("Preview data snapshot"):
            st.text(context[:4000] + ("…" if len(context) > 4000 else ""))

    disabled = bool(data_err) or not ollama_ok

    chat_tab, voice_tab = st.tabs(["Chat", "Voice"])

    with chat_tab:
        _render_chat_tab(context=context, selected_model=selected_model, disabled=disabled)

    with voice_tab:
        _render_voice_tab(
            context=context,
            selected_model=selected_model,
            disabled=disabled,
            whisper_size=whisper_size,
            speak_answers=speak_answers,
            voice_name=voice_name,
        )

    if disabled:
        st.info(
            "Connect Supabase (parent `.env`) and start Ollama on this Mac to use JARVIS. "
            f"Default URL: http://localhost:{JARVIS_PORT}"
        )


if __name__ == "__main__":
    main()
