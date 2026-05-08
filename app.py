"""
Streamlit web interface for the Bedtime Story Generator.

Run with:
    streamlit run app.py
"""

import html
import streamlit as st
from graph import run_pipeline
from utils import StoryConfig

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="✨ Bedtime Story Generator",
    page_icon="🌙",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@400;600;700&display=swap');

  /* ── Base ── */
  .stApp {
    background: linear-gradient(160deg, #12111f 0%, #1c1b35 55%, #1a1a2e 100%);
    color: #ddd5f0;
    min-height: 100vh;
  }

  /* ── Hide "Press Command to apply" helper text on textarea ── */
  .stTextArea [data-baseweb="textarea"] + div,
  .stTextArea ~ small,
  small[data-testid="stWidgetLabel"] { display: none !important; }
  [data-testid="InputInstructions"] { display: none !important; }

  /* ── Stars background ── */
  .stApp::before {
    content: "· ✧ · ★ · ✦ · ✧ · ★ · ✦ · ✧ · ★ ·";
    position: fixed;
    top: 8px;
    left: 0; right: 0;
    text-align: center;
    font-size: 0.7rem;
    color: rgba(255,255,255,0.1);
    letter-spacing: 1.4rem;
    pointer-events: none;
    z-index: 0;
  }

  /* ── Title ── */
  .hero-title {
    font-family: 'Fredoka One', cursive, Georgia, serif;
    font-size: 3rem;
    color: #c4b5e8;
    text-align: center;
    text-shadow: 0 0 30px rgba(160,130,220,0.3), 0 2px 8px rgba(0,0,0,0.5);
    margin-bottom: 0.1rem;
    line-height: 1.15;
  }

  .hero-sub {
    font-family: 'Nunito', sans-serif;
    font-size: 1rem;
    color: #8a7fb0;
    text-align: center;
    margin-bottom: 1.5rem;
  }

  /* ── Moon deco ── */
  .moon-deco {
    text-align: center;
    font-size: 3.6rem;
    line-height: 1;
    margin-bottom: 0.4rem;
    filter: drop-shadow(0 0 16px rgba(180,160,255,0.35));
  }

  /* ── Input area ── */
  .stTextArea label {
    font-family: 'Nunito', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #b8aad6 !important;
  }
  .stTextArea textarea {
    background: rgba(255,255,255,0.04) !important;
    color: #ddd5f0 !important;
    border: 1.5px solid rgba(140,110,200,0.3) !important;
    border-radius: 16px !important;
    font-family: 'Nunito', sans-serif !important;
    font-size: 1rem !important;
    caret-color: #c4b5e8;
  }
  .stTextArea textarea:focus {
    border-color: rgba(180,150,240,0.55) !important;
    box-shadow: 0 0 10px rgba(160,130,220,0.15) !important;
  }
  .stTextArea textarea::placeholder { color: rgba(180,160,220,0.35) !important; }

  /* ── Generate button ── */
  .stButton > button {
    background: linear-gradient(135deg, #5b4a8a, #7c6aad) !important;
    color: #ede8ff !important;
    font-family: 'Fredoka One', cursive !important;
    font-size: 1.2rem !important;
    border: 1px solid rgba(180,150,255,0.25) !important;
    border-radius: 50px !important;
    padding: 0.65rem 2.5rem !important;
    box-shadow: 0 4px 18px rgba(90,70,150,0.4) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    width: 100% !important;
  }
  .stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(100,80,170,0.5) !important;
    background: linear-gradient(135deg, #6a5799, #8d7bbf) !important;
  }

  /* ── Story card ── */
  .story-card {
    background: linear-gradient(150deg, rgba(28,22,52,0.97), rgba(20,16,40,0.97));
    border: 1px solid rgba(140,110,200,0.2);
    border-radius: 24px;
    padding: 2.2rem 2.8rem;
    font-family: 'Nunito', Georgia, serif;
    font-size: 1.08rem;
    line-height: 2;
    color: #ddd5f0;
    white-space: pre-wrap;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.03);
    position: relative;
  }

  .story-card::before {
    content: "✦";
    position: absolute;
    top: 14px; left: 20px;
    color: rgba(180,160,255,0.18);
    font-size: 1.1rem;
  }
  .story-card::after {
    content: "✦";
    position: absolute;
    bottom: 14px; right: 20px;
    color: rgba(180,160,255,0.18);
    font-size: 1.1rem;
  }

  .story-title {
    font-family: 'Fredoka One', cursive, Georgia, serif;
    font-size: 1.6rem;
    color: #c4b5e8;
    text-align: center;
    margin-bottom: 1.4rem;
    text-shadow: 0 0 10px rgba(160,130,220,0.25);
  }

  /* ── Badge row ── */
  .badge-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
    margin: 1.2rem 0;
  }
  .badge {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(140,110,200,0.25);
    border-radius: 20px;
    padding: 4px 13px;
    font-family: 'Nunito', sans-serif;
    font-size: 0.82rem;
    color: #a89cc8;
  }

  /* ── Expander ── */
  .stExpander {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(140,110,200,0.2) !important;
    border-radius: 16px !important;
  }
  .stExpander summary {
    font-family: 'Nunito', sans-serif !important;
    font-weight: 700 !important;
    color: #a89cc8 !important;
    font-size: 0.95rem !important;
  }

  /* ── Progress bars ── */
  .stProgress > div > div {
    background: linear-gradient(90deg, #6b52a8, #8b72c8) !important;
    border-radius: 8px !important;
  }
  .stProgress > div {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 8px !important;
  }

  /* ── Download button ── */
  .stDownloadButton > button {
    background: rgba(255,255,255,0.04) !important;
    color: #a89cc8 !important;
    border: 1px solid rgba(140,110,200,0.3) !important;
    border-radius: 50px !important;
    font-family: 'Nunito', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    width: 100% !important;
  }

  /* ── Divider ── */
  hr { border-color: rgba(140,110,200,0.15) !important; margin: 1.4rem 0 !important; }

  /* ── Score pill ── */
  .score-pill {
    display: inline-block;
    font-family: 'Fredoka One', cursive;
    font-size: 1.4rem;
    padding: 6px 24px;
    border-radius: 40px;
    margin-bottom: 1rem;
  }
  .score-label-text {
    font-family: 'Nunito', sans-serif;
    font-size: 0.86rem;
    color: #8a7fb0;
    margin-bottom: 2px;
  }

  /* ── Alert ── */
  .stAlert {
    border-radius: 14px !important;
    font-family: 'Nunito', sans-serif !important;
  }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown("<div class='moon-deco'>🌙</div>", unsafe_allow_html=True)
st.markdown("<div class='hero-title'>Bedtime Story Generator</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='hero-sub'>Tell us what kind of story you'd like, and we'll write one just for you.</div>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Input ──────────────────────────────────────────────────────────────────────

prompt = st.text_area(
    "What kind of story would you like tonight? 🌟",
    placeholder="e.g. A brave little fox who is scared of thunderstorms but saves her forest friends…",
    height=110,
)

col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    generate = st.button("🪄 Generate My Story!", use_container_width=True)

# ── Pipeline ───────────────────────────────────────────────────────────────────

if generate:
    if not prompt.strip():
        st.warning("Oops! Please tell us what kind of story you'd like first 😊")
    else:
        with st.spinner("Crafting your story… sit tight, this takes about 30 seconds."):
            cfg = StoryConfig()
            try:
                state = run_pipeline(prompt.strip(), cfg)
            except EnvironmentError:
                st.error(
                    "**OPENAI_API_KEY not set.**  \n"
                    "Start the app with your key exported:  \n"
                    "`OPENAI_API_KEY=your-key streamlit run app.py`"
                )
                st.stop()

        st.markdown("---")

        # ── Story ──────────────────────────────────────────────────────────────

        story      = state.get("final_story") or state.get("story", "")
        plan       = state.get("plan", {})
        evaluation = state.get("evaluation", {})
        classif    = state.get("classification", {})

        title      = plan.get("title", "Your Story")

        st.markdown(
            f"<div class='story-card'>"
            f"<div class='story-title'>{html.escape(title)}</div>"
            f"{html.escape(story)}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── Badges ────────────────────────────────────────────────────────────

        genre      = classif.get("genre", "—").capitalize()
        tone       = classif.get("tone", "—").capitalize()
        age_target = plan.get("estimated_age_target", "—")
        word_count = len(story.split())
        iterations = state.get("iteration_count", 1)
        fk_grade   = evaluation.get("reading_level_grade", "—")

        st.markdown(
            "<div class='badge-row'>"
            f"<span class='badge'>📖 {genre}</span>"
            f"<span class='badge'>🎭 {tone}</span>"
            f"<span class='badge'>👧 Ages {age_target}+</span>"
            f"<span class='badge'>📝 {word_count} words</span>"
            f"<span class='badge'>🎓 Grade {fk_grade}</span>"
            f"<span class='badge'>🔄 {max(0, iterations - 1)} refinement(s)</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Download ──────────────────────────────────────────────────────────

        st.download_button(
            label="⬇️ Save this story as a .txt file",
            data=f"{title}\n\n{story}",
            file_name=f"{title.lower().replace(' ', '_')}.txt",
            mime="text/plain",
        )

        st.markdown("---")

        # ── Scorecard (collapsed) ─────────────────────────────────────────────

        overall = evaluation.get("overall", 0)
        scores  = evaluation.get("scores", {})

        with st.expander("📊 View Quality Scorecard"):
            score_color = (
                "#4ade80" if overall >= 8.5 else
                "#facc15" if overall >= 7.0 else
                "#f87171"
            )
            st.markdown(
                f"<div style='text-align:center;margin-bottom:1rem;'>"
                f"<span class='score-pill' style='background:{score_color}22;"
                f"color:{score_color};border:2px solid {score_color}55;'>"
                f"Overall &nbsp; {overall:.2f} / 10"
                f"</span></div>",
                unsafe_allow_html=True,
            )

            dim_labels = {
                "content_safety":           "🛡️  Content Safety (25%)",
                "vocabulary_accessibility": "📚  Vocabulary (20%)",
                "coherence":                "🔗  Coherence (20%)",
                "narrative_arc":            "🌈  Narrative Arc (20%)",
                "engagement":               "⚡  Engagement (15%)",
            }

            for key, label in dim_labels.items():
                score = scores.get(key, 0)
                st.markdown(f"<div class='score-label-text'>{label}</div>", unsafe_allow_html=True)
                st.progress(score / 10.0, text=f"{score:.1f} / 10")

            critique = evaluation.get("critique", "")
            if critique:
                st.markdown("---")
                st.markdown(
                    f"<p style='color:#b8a9e0;font-size:0.88rem;font-family:Nunito,sans-serif;'>"
                    f"<strong style='color:#d4bfff;'>Judge's notes:</strong> {html.escape(critique)}"
                    f"</p>",
                    unsafe_allow_html=True,
                )

        st.markdown(
            "<p style='text-align:center;color:#4e4570;font-size:0.82rem;"
            "font-family:Nunito,sans-serif;margin-top:1.5rem;'>Sweet dreams 🌙</p>",
            unsafe_allow_html=True,
        )
