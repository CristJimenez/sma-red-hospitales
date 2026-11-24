"""Prueba de humo del panel Streamlit."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent


def test_panel_arranca_sin_excepciones() -> None:
    app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120).run()

    assert not app.exception, app.exception
    assert app.title[0].value.startswith("SMA")
    assert len(app.metric) >= 6
