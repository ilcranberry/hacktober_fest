"""Run the local UI: python app.py."""

from nikitosik.app import build_app

if __name__ == "__main__":
    build_app().queue().launch(server_name="127.0.0.1", share=False)
