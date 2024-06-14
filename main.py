from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import aiofiles

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def main():
  async with aiofiles.open("index.html", "r") as f:
    content = await f.read()
  return HTMLResponse(content=content)


@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...)):
  file_urls = []

  for file in files:
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    async with aiofiles.open(file_path, 'wb') as out_file:
      content = await file.read()
      await out_file.write(content)

    file_url = f"http://url-solrikk/uploads/{unique_filename}"
    file_urls.append(file_url)

  return JSONResponse(content={"file_urls": file_urls})


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)
