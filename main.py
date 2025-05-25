import uvicorn

from fastapi import FastAPI

from requests.routers import requests_router

# from shared.database import engine, Base

# from requests.models.request import Request

# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root() -> dict:
    return {"Hello": "World"}

app.include_router(requests_router.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)