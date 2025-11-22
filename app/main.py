from fastapi import FastAPI, Form, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User, UserRole, Document, Summary, Video, Download
from passlib.context import CryptContext
import os
import uuid
from dotenv import load_dotenv
from google import genai
import time
from typing import Optional
from app import schemas
import asyncio
from fastapi import Depends, HTTPException
from pathlib import Path
from fastapi.responses import JSONResponse

# initialize
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

load_dotenv()
GEMINI_API_KEY = os.getenv("GenEd_Gemini_API_KEY")

# dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# hash password
def hash_password(password: str):
    return pwd_context.hash(password)

# Password verification
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

test = hash_password("mypassword")
print("HASHED:", test)
print("VERIFY:", verify_password("mypassword", test))

# Routes
# home page
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# dashboard page
@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Signup endpoint
@app.post("/signup")
def signup(
    fullname: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: Optional[str] = Form("user"),
    phone_number: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # check uniqueness
    if db.query(User).filter(User.username == username).first():
           return JSONResponse(
        status_code=400,
        content={"message": "Username already exists", "redirect": "/login"}
    )
    if db.query(User).filter(User.email == email).first():
           return JSONResponse(
        status_code=400,
        content={"message": "Email already exists", "redirect": "/login"}
    )

    # validate with pydantic schema (will coerce enum if provided)
    try:
        user_in = schemas.UserCreate(
            fullname=fullname,
            username=username,
            email=email,
            password=password,
            role=UserRole(role) if role else UserRole.user,
            phone_number=phone_number,
        )
    except Exception as e:
           return JSONResponse(
        status_code=400,
        content={"message": f"Invalid input: {e}"}
    )

    # create DB user
    db_user = User(
        fullname=user_in.fullname,
        username=user_in.username,
        email=user_in.email,
        password=hash_password(user_in.password),
        role=user_in.role,
        phone_number=user_in.phone_number,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return JSONResponse(
    status_code=200,
    content={
        "message": "Signup successful",
        "redirect": "/dashboard"
    }
)

# Login route
@app.post("/login")
def login(user: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if "@" in user:
        db_user = db.query(User).filter(User.email == user).first()
    else:
        db_user = db.query(User).filter(User.username == user).first()
    
    print("DB User:", db_user)
    
    if not db_user:
              print("User not found for identifier:", user)
              return JSONResponse(
          status_code=404,
          content={"message": "User not found. Please sign up first", 
            "redirect": "/signup"}
     )
    


    if not verify_password(password, db_user.password):
         print("Password verification failed for user:", user)
         return JSONResponse(
        status_code=400,
        content={"message": "Invalid credentials. Please try again", "redirect": "/login"}
    )
    print("User logged in successfully:", user)

    return JSONResponse(
    status_code=200,
    content={
        "message": "Login successful",
        "redirect": "/dashboard"
    }
    )

@app.post("/change-password")
def change_password(
    username: str = Form(...),                 # or user_id from session/JWT
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    # 1. Get the user
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        return JSONResponse(
            status_code=404,
            content={"message": "User not found"}
        )

    # 2. Verify old password
    if not verify_password(old_password, db_user.password):
        return JSONResponse(
            status_code=400,
            content={"message": "Old password is incorrect"}
        )

    # 3. Update password
    db_user.password = hash_password(new_password)
    db.commit()

    return JSONResponse(
        status_code=200,
        content={"message": "Password changed successfully", "redirect": "/login"}
    )
  

# Serve signup/login pages
@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("sign-in.html", {"request": request})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/change-password")
def change_password_page(request: Request):
    return templates.TemplateResponse("change-password.html", {"request": request})

# upload files endpoint and logic
@app.post("/upload", response_model=schemas.VideoOut)
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Form(...),                    # or use current_user via auth dependency
    db: Session = Depends(get_db),
):
    # validate user exists
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # ensure storage directory
    media_dir = Path("media/videos")
    media_dir.mkdir(parents=True, exist_ok=True)

    # read uploaded file safely (streaming recommended for large files)
    content_bytes = await file.read()

    # save original uploaded file (optional) — sanitize and uniquify filename
    orig_dir = Path("media/uploads")
    orig_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    orig_path = orig_dir / safe_name
    with open(orig_path, "wb") as f:
        f.write(content_bytes)

    # upload to Gemini (example, adjust to SDK requirements)
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        # pass a file-like object if SDK requires it
        uploaded = client.files.upload(file=content_bytes, file_name=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to GenAI: {e}")

    # get extracted text from model (adjust call to match your SDK)
    try:
        # prefer sending a prompt that asks for text extraction
        extract_prompt = "Extract all text from the uploaded file and return a single block of text."
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[extract_prompt],
            files=[uploaded] if hasattr(uploaded, "id") else None
        )
        extracted_text = getattr(resp, "text", None) or getattr(resp, "content", None) or ""
    except Exception as e:
        extracted_text = ""
        # proceed but warn in logs; or raise depending on requirements

    if not extracted_text:
        raise HTTPException(status_code=500, detail="Failed to extract text from file")

    # create Document row (persist extracted_text)
    doc = Document(
        user_id=user_id,
        doc_name=file.filename,
        file_path=str(orig_path),
        extracted_text=extracted_text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # create Summary (call model to summarize extracted_text)
    try:
        summary_prompt = "Summarize the following text into a concise paragraph:\n\n" + extracted_text
        sum_resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[summary_prompt]
        )
        summary_text = getattr(sum_resp, "text", None) or getattr(sum_resp, "content", None) or extracted_text[:200]
    except Exception:
        summary_text = extracted_text[:200]

    summary = Summary(
        user_id=user_id,
        document_id=doc.id,
        summary_text=summary_text
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)

    # generate video using the summary (use a concise prompt)
    video_name = f"{Path(file.filename).stem}_generated.mp4"
    output_path = media_dir / video_name

    try:
        operation = client.models.generate_video(
            model="veo-2.0-generate-001",
            prompt=summary_text,
            output_file_name=video_name,
            config={"aspectRatio": "16:9", "durationSeconds": 6}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video generation request failed: {e}")

    # poll operation asynchronously
    max_wait = 60 * 5
    waited = 0
    interval = 5
    while not getattr(operation, "done", False) and waited < max_wait:
        await asyncio.sleep(interval)
        waited += interval
        try:
            operation = client.operations.get(getattr(operation, "name", operation))
        except Exception:
            break

    if not getattr(operation, "done", False):
        raise HTTPException(status_code=500, detail="Video generation did not complete in time")

    # extract generated file reference (SDK-specific)
    gen_vid = None
    try:
        gen_vid = operation.response.generated_videos[0]
    except Exception:
        raise HTTPException(status_code=500, detail="No generated video returned")

    # try to download the video bytes
    video_bytes = None
    try:
        # if SDK gives a file id
        if hasattr(gen_vid, "file_id"):
            downloaded = client.files.download(file=gen_vid.file_id)
            video_bytes = getattr(downloaded, "content", None) or getattr(downloaded, "data", None)
        # if SDK returns raw bytes on an attribute
        elif hasattr(gen_vid, "video") and hasattr(gen_vid.video, "content"):
            video_bytes = gen_vid.video.content
    except Exception:
        video_bytes = None

    if not video_bytes:
        raise HTTPException(status_code=500, detail="Failed to download generated video")

    # save to disk and create Video DB row
    with open(output_path, "wb") as f:
        f.write(video_bytes)

    video = Video(
        user_id=user_id,
        document_id=doc.id,
        summary_id=summary.id,
        video_name=video_name,
        video_path=str(output_path)
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # return VideoOut (uses orm_mode)
    return schemas.VideoOut.from_orm(video)

# generate video from summary / document / raw text
@app.post("/generate-video", response_model=schemas.VideoOut)
async def generate_video(
    user_id: int = Form(...),
    summary_id: Optional[int] = Form(None),
    document_id: Optional[int] = Form(None),
    raw_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # validate user
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # determine text source
    source_text = ""
    used_summary_id = summary_id

    if summary_id:
        summary = db.query(Summary).filter(Summary.id == summary_id).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        source_text = summary.summary_text

    elif raw_text:
        source_text = raw_text

    elif document_id:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # read file and ask model to extract text
        try:
            with open(doc.file_path, "rb") as fh:
                file_bytes = fh.read()
            uploaded = client.files.upload(file=file_bytes, file_name=os.path.basename(doc.file_path))
            extract_prompt = "Extract all text from the uploaded file and return a single block of text."
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[extract_prompt],
                files=[uploaded] if hasattr(uploaded, "id") else None
            )
            source_text = getattr(resp, "text", None) or getattr(resp, "content", None) or ""
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to extract text from document: {e}")

    if not source_text:
        raise HTTPException(status_code=400, detail="No source text provided for video generation")

    # if there is no pre-existing summary, create a concise summary to base the video on
    if not summary_id:
        try:
            summary_prompt = "Summarize the following text into a concise paragraph:\n\n" + source_text
            sum_resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[summary_prompt]
            )
            summary_text = getattr(sum_resp, "text", None) or getattr(sum_resp, "content", None) or source_text[:200]
        except Exception:
            summary_text = source_text[:200]

        summary = Summary(user_id=user_id, document_id=document_id if document_id else None, summary_text=summary_text)
        db.add(summary)
        db.commit()
        db.refresh(summary)
        used_summary_id = summary.id
    else:
        summary_text = source_text

    # generate video from the summary_text
    media_dir = Path("media/videos")
    media_dir.mkdir(parents=True, exist_ok=True)
    video_name = f"video_{user_id}_{int(time.time())}.mp4"
    output_path = media_dir / video_name

    try:
        operation = client.models.generate_video(
            model="veo-2.0-generate-001",
            prompt=summary_text,
            output_file_name=video_name,
            config={"aspectRatio": "16:9", "durationSeconds": 6}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video generation request failed: {e}")

    # poll operation (async)
    max_wait = 60 * 5
    waited = 0
    interval = 5
    while not getattr(operation, "done", False) and waited < max_wait:
        await asyncio.sleep(interval)
        waited += interval
        try:
            operation = client.operations.get(getattr(operation, "name", operation))
        except Exception:
            break

    if not getattr(operation, "done", False):
        raise HTTPException(status_code=500, detail="Video generation did not complete in time")

    try:
        gen_vid = operation.response.generated_videos[0]
    except Exception:
        raise HTTPException(status_code=500, detail="No generated video returned by the operation")

    # download video bytes (SDK dependent)
    video_bytes = None
    try:
        if hasattr(gen_vid, "file_id"):
            downloaded = client.files.download(file=gen_vid.file_id)
            video_bytes = getattr(downloaded, "content", None) or getattr(downloaded, "data", None)
        elif hasattr(gen_vid, "video") and hasattr(gen_vid.video, "content"):
            video_bytes = gen_vid.video.content
    except Exception:
        video_bytes = None

    if not video_bytes:
        raise HTTPException(status_code=500, detail="Failed to download generated video")

    with open(output_path, "wb") as f:
        f.write(video_bytes)

    video = Video(
        user_id=user_id,
        document_id=document_id if document_id else None,
        summary_id=used_summary_id,
        video_name=video_name,
        video_path=str(output_path),
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    return schemas.VideoOut.from_orm(video)


# endpoint to record download and return file
@app.get("/download-video/{video_id}")
def download_video(video_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # optional user validation
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    # create download record if user provided (or skip but best to record if user present)
    if user_id:
        download = Download(user_id=user_id, video_id=video_id)
        db.add(download)
        db.commit()

    if not Path(video.video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found on server")

    return FileResponse(path=video.video_path, media_type="application/octet-stream", filename=video.video_name)






