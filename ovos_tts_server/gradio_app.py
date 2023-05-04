import tempfile
import gradio as gr

from ovos_utils import LOG
from neon_tts_plugin_coqui import CoquiTTS

TTS = None


def tts(text: str, language: str):
    print(text, language)
    # return output
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
        TTS.get_tts(text, fp, speaker={"language": language})
        return fp.name


def bind_gradio_service(app, tts_engine, title, description, info, badge,
                        default_lang="en"):
    global TTS
    TTS = tts_engine

    LOG.info(tts_engine.available_languages)
    languages = list(tts_engine.available_languages or [default_lang])

    with gr.Blocks() as blocks:
        gr.Markdown("<h1 style='text-align: center; margin-bottom: 1rem'>"
                    + title
                    + "</h1>")
        gr.Markdown(description)
        with gr.Row():  # equal_height=False
            with gr.Column():  # variant="panel"
                textbox = gr.Textbox(
                    label="Input",
                    value=CoquiTTS.langs[default_lang]["sentence"],
                    max_lines=3,
                )
                radio = gr.Radio(
                    label="Language",
                    choices=languages,
                    value=default_lang
                )
                with gr.Row():  # mobile_collapse=False
                    submit = gr.Button("Submit", variant="primary")
            audio = gr.Audio(label="Output", interactive=False)
        gr.Markdown(info)
        gr.Markdown("<center>"
                    + f'<img src={badge} alt="visitors badge"/>'
                    + "</center>")

        # actions
        submit.click(
            tts,
            [textbox, radio],
            [audio],
        )
        radio.change(lambda lang: CoquiTTS.langs[lang]["sentence"],
                     radio, textbox)
    LOG.info(f"Mounting app to /gradio")
    gr.mount_gradio_app(app, blocks, path="/gradio")
