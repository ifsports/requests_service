import uvicorn

from fastapi import FastAPI

from requests.routers import requests_router

from shared.exceptions_handler import not_found_exception_handler, conflict_exception_handler
from shared.exceptions import NotFound, Conflict

# from shared.database import engine, Base

# from requests.models.request import Request

# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(requests_router.router)
app.add_exception_handler(NotFound, not_found_exception_handler)
app.add_exception_handler(Conflict, conflict_exception_handler)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)