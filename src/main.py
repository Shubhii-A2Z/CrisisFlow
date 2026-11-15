from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app=FastAPI(
    title="CrisisFlow"
)

@app.get("/")
async def hello()->dict[str, str]:
    return {
        "message": "Welcome to Crisis_Flow"
    }


def main()->None:
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)