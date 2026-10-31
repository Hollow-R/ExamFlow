
from examflow import create_app


app = create_app()


def start_server():
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
