import os
import csv
import io
import aiohttp
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiofiles
import uuid
import re
import logging
from fastapi.responses import FileResponse
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def download_yandex_file(url):
    try:
        file_id = url.split('/')[-1]
        api_url = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={url}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    direct_url = data.get('href')
                    
                    if direct_url:
                        async with session.get(direct_url) as download_response:
                            if download_response.status == 200:
                                return await download_response.read()
                    
        logger.error(f"Failed to download from Yandex.Disk: {url}")
        return None
    except Exception as e:
        logger.error(f"Error downloading from Yandex.Disk: {str(e)}")
        return None

@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...), columns: str = Form(None)):
    logger.info("Starting file upload process")
    supported_file_types = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov',
                           '.avi', '.mkv', '.zip', '.rar', '.csv', '.txt')
    file_urls = []
    link_replacements = {}

    csv_columns = None
    for file in files:
        if file.filename.lower().endswith('.csv'):
            content = (await file.read()).decode('utf-8-sig')
            csv_reader = csv.DictReader(io.StringIO(content), delimiter=';')
            csv_columns = list(next(csv_reader).keys())
            await file.seek(0)
            break

    for file in files:
        try:
            if file.filename.lower().endswith('.csv'):
                if not columns and csv_columns:
                    columns = ",".join(csv_columns)
                if not columns:
                    columns = "Образец ткани,Фотоконтент,Техническая информация"
                process_columns = [col.strip() for col in columns.split(',')]

                content = await file.read()
                csv_content = content.decode('utf-8-sig')
                csv_reader = csv.DictReader(io.StringIO(csv_content), delimiter=';')

                for row in csv_reader:
                    for col in process_columns:
                        if col in row and row[col]:
                            urls = re.findall(r'https://disk\.yandex\.ru/[^\s,"\']+', row[col])
                            for url in urls:
                                if url not in link_replacements:
                                    content = await download_yandex_file(url)
                                    if content:
                                        unique_id = uuid.uuid4().hex[:8]
                                        new_filename = f"{unique_id}.jpg"
                                        photo_path = os.path.join(PHOTO_DIR, new_filename)

                                        async with aiofiles.open(photo_path, 'wb') as photo_file:
                                            await photo_file.write(content)

                                        new_url = f"https://media-drop-sollrikk.replit.app/photos/{new_filename}"
                                        link_replacements[url] = new_url
                                        file_urls.append(new_url)

            elif file.filename.lower().endswith(supported_file_types):
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

            elif file.filename.lower().endswith(".txt"):
                content = (await file.read()).decode("utf-8")
                urls = re.findall(r"https?://\S+", content)
                for url in urls:
                    if url not in link_replacements:
                        content = await download_yandex_file(url)
                        if content:
                            unique_id = uuid.uuid4().hex[:8]
                            new_filename = f"{unique_id}.jpg"
                            photo_path = os.path.join(PHOTO_DIR, new_filename)

                            async with aiofiles.open(photo_path, 'wb') as photo_file:
                                await photo_file.write(content)

                            new_url = f"https://media-drop-sollrikk.replit.app/photos/{new_filename}"
                            link_replacements[url] = new_url
                            file_urls.append(new_url)

        except Exception as e:
            print(f"Error processing file {file.filename}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing file {file.filename}")

    return JSONResponse(content={"file_urls": file_urls, "link_replacements": link_replacements})

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


@app.post("/process_text_file/")
async def process_text_file(file: UploadFile = File(...)):
    try:
        logger.info("Starting text file processing")
        if not file.filename.lower().endswith('.txt'):
            raise HTTPException(status_code=400, detail="Only .txt files are supported")

        content = (await file.read()).decode('utf-8')
        urls = re.findall(r'https://disk\.yandex\.ru/[^\s,"\']+', content)
        new_content = content
        processed_urls = {}

        for url in urls:
            if url not in processed_urls:
                file_content = await download_yandex_file(url)
                if file_content:
                    unique_id = uuid.uuid4().hex[:8]
                    new_filename = f"{unique_id}.jpg"
                    photo_path = os.path.join(PHOTO_DIR, new_filename)

                    async with aiofiles.open(photo_path, 'wb') as photo_file:
                        await photo_file.write(file_content)

                    new_url = f"https://media-drop-sollrikk.replit.app/photos/{new_filename}"
                    processed_urls[url] = new_url
                    new_content = new_content.replace(url, new_url)

        output_filename = f"processed_{file.filename}"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        
        async with aiofiles.open(output_path, 'w') as f:
            await f.write(new_content)

        return FileResponse(output_path, filename=output_filename)

    except Exception as e:
        logger.error(f"Error processing text file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_processed_csv/{filename}")
async def download_processed_csv(filename: str):
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            return FileResponse(file_path, filename=f"processed_{filename}")
        return {"error": "File not found"}
    except Exception as e:
        logger.error(f"Error downloading CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading file")
