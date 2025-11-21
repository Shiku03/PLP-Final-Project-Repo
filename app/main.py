from fastapi import FastAPI, Form, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import User, UserRole
from passlib.context import CryptContext
import os
from dotenv import load_dotenv
from google import genai
import time
from typing import Optional
import schemas

# initialize
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
@app.post("/signup", response_model=schemas.UserOut)
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
        raise HTTPException(status_code=400, detail="Username already exists")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

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
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")

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

    return schemas.UserOut.from_orm(db_user)

# Login route
@app.post("/login")
def login(user: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if "@" in user:
        db_user = db.query(User).filter(User.email == user).first()
    else:
        db_user = db.query(User).filter(User.username == user).first()

    if not db_user or not verify_password(password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    return RedirectResponse(url="/dashboard", status_code=303)

# Serve signup/login pages
@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("sign-in.html", {"request": request})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# upload files endpoint and logic
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content_bytes = await file.read()

    # forward to Gemini for text extraction
    client = genai.Client(api_key=GEMINI_API_KEY)

    uploaded_file = client.files.upload(file=content_bytes, file_name=file.filename)

    prompt = "Extract all the text from the uploaded file and return it as a single block of text, adding paragraphs where necessary"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file, prompt]
    )

    extracted_text = getattr(response, "text", None) or getattr(response, "content", None) or ""

    # use extracted text as the prompt for video generation using Veo3
    VEOS_MODEL = "veo-2.0-generate-001"
    output_filename = f"{os.path.splitext(file.filename)[0]}_generated_video.mp4"
    video_prompt = extracted_text

    print("Starting video generation...")

    operation = client.models.generate_video(
        model=VEOS_MODEL,
        prompt=video_prompt,
        output_file_name=output_filename,
        config={
            "aspectRatio": "16:9",
            "durationSeconds": 6
        }
    )

    # Poll the operation status until the video is ready
    # The exact polling/get API may vary by SDK version; adjust if needed.
    while not getattr(operation, "done", False):
        print("Waiting for video generation to complete... (Checking status in 10s)")
        time.sleep(10)  # Wait 10 seconds before checking again
        # Refresh the operation object status; use operation.name if required by SDK
        try:
            operation = client.operations.get(getattr(operation, "name", operation))
        except Exception:
            # fallback: try to re-use the operation object or break to avoid infinite loop on SDK mismatch
            break

    print("\nVideo generation complete!")

    # The generated video object is located in the operation's response
    generated_video = operation.response.generated_videos[0]

    # Attempt to download the video bytes; SDKs vary, so we handle common fields
    video_bytes = None
    if hasattr(generated_video.video, "video_bytes"):
        video_bytes = generated_video.video.video_bytes
    elif hasattr(generated_video.video, "content"):
        video_bytes = generated_video.video.content
    else:
        # try SDK download helper
        try:
            downloaded = client.files.download(file=generated_video.video)
            video_bytes = getattr(downloaded, "content", None) or getattr(downloaded, "data", None)
        except Exception:
            video_bytes = None

    if video_bytes:
        with open(output_filename, "wb") as f:
            f.write(video_bytes)
        print(f"Video successfully saved to {output_filename}")
    else:
        print("Failed to retrieve video bytes from the operation response.")

    return {
        "filename": file.filename,
        "extracted_text": extracted_text,
        "generated_video": output_filename if video_bytes else None
    }








