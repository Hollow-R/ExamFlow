
import os

from examflow import create_app


app = create_app()


def start_server():
    app.run(
        host=os.environ.get("EXAMFLOW_HOST", "0.0.0.0"),
        port=int(os.environ.get("EXAMFLOW_PORT", "5000")),
        debug=False,
        use_reloader=False
    )
