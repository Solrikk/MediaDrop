
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiofiles
import uuid
import re

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/", response_class=HTMLResponse)
async def main():
  async with aiofiles.open("index.html", "r") as f:
    content = await f.read()
  return HTMLResponse(content=content)


def sanitize_filename(filename):
  filename = re.sub(r'[^A-Za-z0-9]+', '-', filename)
  filename = filename[:20].strip('-')
  return filename


@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...)):
  supported_file_types = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov',
                          '.avi', '.mkv', '.zip', '.rar')
  file_urls = []

  for file in files:
    if not file.filename.lower().endswith(supported_file_types):
      continue

    unique_id = uuid.uuid4().hex[:8]
    sanitized_filename = sanitize_filename(file.filename.rsplit('.', 1)[0])
    file_extension = file.filename.rsplit('.', 1)[1]
    new_filename = f"{unique_id}-{sanitized_filename}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    async with aiofiles.open(file_path, 'wb') as out_file:
      content = await file.read()
      await out_file.write(content)

    file_url = f"/uploads/{new_filename}"
    file_urls.append(file_url)

  return JSONResponse(content={"file_urls": file_urls})


@app.get("/files/")
async def get_files():
  files = []
  for filename in os.listdir(UPLOAD_DIR):
    file_url = f"/uploads/{filename}"
    files.append({"filename": filename, "url": file_url})
  return JSONResponse(content={"available_files": files})


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)
