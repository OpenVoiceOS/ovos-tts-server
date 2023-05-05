import json
import tempfile
import gradio as gr

from os.path import join, dirname
from ovos_utils import LOG

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

    languages = list(tts_engine.available_languages or [default_lang])
    languages.sort()
    LOG.debug(languages)

    if default_lang not in languages:
        LOG.warning(f"{default_lang} not in languages, trying ISO 639-1 code")
        default_lang = default_lang.split('-')[0]
    if default_lang not in languages:
        LOG.warning(f"{default_lang} not in languages, choosing first lang")
        default_lang = languages[0]

    try:
        example_file = "rainbow.json"
        with open(join(dirname(__file__), "examples", example_file), 'r') as f:
            examples = json.load(f)
    except Exception as e:
        LOG.error(e)
        examples = dict()

    with gr.Blocks() as blocks:
        gr.Markdown("<h1 style='text-align: center; margin-bottom: 1rem'>"
                    + title
                    + "</h1>")
        gr.Markdown(description)
        with gr.Row():  # equal_height=False
            with gr.Column():  # variant="panel"
                textbox = gr.Textbox(
                    label="Input",
                    value=examples.get(default_lang),
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
        radio.change(lambda lang: examples.get(lang), radio, textbox)
    LOG.info(f"Mounting app to /gradio")
    gr.mount_gradio_app(app, blocks, path="/gradio")
