
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiofiles
import uuid
import re
app = FastAPI()

PHOTO_DIR = "photo"
UPLOAD_DIR = "static/uploads"
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
        try:
            if not file.filename.lower().endswith(supported_file_types):
                continue

            unique_id = uuid.uuid4().hex[:8]
            sanitized_filename = sanitize_filename(file.filename.rsplit('.', 1)[0])
            file_extension = file.filename.rsplit('.', 1)[1]
            new_filename = f"{unique_id}-{sanitized_filename}.{file_extension}"
            
            content = await file.read()
            photo_path = os.path.join(PHOTO_DIR, new_filename)
            async with aiofiles.open(photo_path, 'wb') as photo_file:
                await photo_file.write(content)

            file_url = f"/photos/{new_filename}"
            file_urls.append(file_url)
        except Exception as e:
            print(f"Error processing file {file.filename}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing file {file.filename}")

    return JSONResponse(content={"file_urls": file_urls})

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/photos", StaticFiles(directory=PHOTO_DIR), name="photos")

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
