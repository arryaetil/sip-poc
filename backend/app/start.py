import logging
import os

import uvicorn


if __name__ == "__main__":
    # The app's own info lines (model calls, lead lists, purges) reach the Railway logs.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
