from sqlalchemy.orm import Session#import Session from SQLAlchemy
import schemas#import schemas.py
from models import User, Document, Summary, Video, Download#import models.py
from passlib.context import CryptContext#import passlib for hashing passwords
from typing import Optional


pwd_context= CryptContext(schemes=["bcrypt"], deprecated="auto")#set up password hashing context

#hash user password before saving to db
def hash_password(password:str):
    return pwd_context.hash(password)

#verify user password during login
def verify_password(plain:str, hashed:str):
    return pwd_context.verify(plain, hashed)

#create new user
def create_user(db:Session, user: schemas.UserCreate):
    hashed_password=hash_password(user.password)

    db_user=User(
        fullname=user.fullname,
        username=user.username,
        email=user.email,
        password=hashed_password,
        phone_number=user.phone_number
        role=user.role or "user"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


#get all users
def get_all_users(db: Session):
    return db.query(User).all()

#allow users to login with either username or email
#get user by username
def get_user_by_username(db:Session, username:str) ->Optional[User]:
    return db.query(User).filter(User.username==username).first()

#get user by email
def get_user_by_email(db :Session, email:str) ->Optional[User]:
    return db.query(User).filter(User.email==email).first()


#get user by id
def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

#create new document
def create_document(db: Session, doc: schema.DocumentCreate):
    db_doc = Document(
        user_id=doc.user_id,
        doc_name=doc.doc_name,
        file_path=doc.file_path,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

#get document by id
def get_document(db: Session, doc_id: int):
    return db.query(Document).filter(Document.id == doc_id).first()

#get documents by user id
def get_documents_by_user(db: Session, user_id: int):
    return db.query(Document).filter(Document.user_id == user_id).all()

#create new summary
def create_summary(db: Session, data: schema.SummaryCreate):
    db_summary = Summary(
        summary_text=data.summary_text,
        user_id=data.user_id,
        document_id=data.document_id
    )
    db.add(db_summary)
    db.commit()
    db.refresh(db_summary)
    return db_summary

#get summary by id
def get_summary(db: Session, summary_id: int):
    return db.query(Summary).filter(Summary.id == summary_id).first()

#get summaries by user id
def get_summaries_by_user(db: Session, user_id: int):
    return db.query(Summary).filter(Summary.user_id == user_id).all()

#create new video
def create_video(db: Session, v: schema.VideoCreate):
    db_video = Video(
        user_id=v.user_id,
        document_id=v.document_id,
        summary_id=v.summary_id,
        video_name=v.video_name,
        video_path=v.video_path,
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

#get video by id
def get_video(db: Session, video_id: int):
    return db.query(Video).filter(Video.id == video_id).first()

#get videos by user id
def get_videos_by_user(db: Session, user_id: int):
    return db.query(Video).filter(Video.user_id == user_id).all()

#create new download record
def create_download(db: Session, data: schema.DownloadCreate):
    db_download = Download(
        user_id=data.user_id,
        video_id=data.video_id
    )
    db.add(db_download)
    db.commit()
    db.refresh(db_download)
    return db_download

#get downloads by user id
def get_downloads_by_user(db: Session, user_id: int):
    return db.query(Download).filter(Download.user_id == user_id).all()

#user registration service
def register_user_service(db: Session, user: schema.UserCreate):
    # Check email
    if get_user_by_email(db, user.email):
        raise Exception("Email already registered")

    # Optional: check username
    if get_user_by_username(db, user.username):
        raise Exception("Username already exists")

    return create_user(db, user)

#upload document service
def upload_document_service(db: Session, doc_data: schema.DocumentCreate):
    return create_document(db, doc_data)

#summarize document service
def summarize_document_service(db: Session, summary_data: schema.SummaryCreate):
    return create_summary(db, summary_data)

#generate video service
def generate_video_service(db: Session, video_data: schema.VideoCreate):
    return create_video(db, video_data)

#record video download service
def record_video_download_service(db: Session, download_data: schema.DownloadCreate):
    return create_download(db, download_data)
