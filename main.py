import os
import uvicorn
from app.main import app, CheckCompanyRequest, CheckCompanyResponse

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
