from sqlalchemy import Column, Integer, String,Enum,TIMESTAMP,ForeignKey,Text
from sqlalchemy import func
from sqlalchemy.orm import relationship
import enum
from database import Base

class UserRole(enum.Enum):
    user = 'user'
    admin = 'admin'

class User(Base):
    __tablename__='users'

    id=Column(Integer, primary_key=True, index=True)
    fullname=Column(String(50), nullable=False)
    username=Column(String(50), unique=True, nullable=False)
    email=Column(String(100), unique=True, nullable=False)
    password=Column(String(255), nullable=False)
    role=Column(Enum(UserRole), default=UserRole.user,nullable=False)
    phone_number=Column(String(50))
    created_at=Column(TIMESTAMP, server_default=func.now())
    updated_at=Column(TIMESTAMP,server_default=func.now(), onupdate=func.now())

    documents = relationship("Document", back_populates="user")
    summaries = relationship("Summary", back_populates="user")
    videos = relationship("Video", back_populates="user")
    downloads = relationship("Download", back_populates="user")

class Document(Base):
    __tablename__="documents"

    id=Column(Integer, primary_key=True, index=True)
    user_id=Column(Integer, ForeignKey("users.id",ondelete="CASCADE"),nullable=False)
    doc_name=Column(String(255), nullable=False)
    file_path=Column(String(255), nullable=False)
    uploaded_at=Column(TIMESTAMP, server_default=func.now())

    user=relationship("User", back_populates="documents")
    summaries = relationship("Summary", back_populates="document")
    videos = relationship("Video", back_populates="document")

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"))
    summary_text = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="summaries")
    document = relationship("Document", back_populates="summaries")
    videos = relationship("Video", back_populates="summary")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"))
    summary_id = Column(Integer, ForeignKey("summaries.id", ondelete="SET NULL"))
    video_name = Column(String(255), nullable=False)
    video_path = Column(String(255), nullable=False)
    generated_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="videos")
    document = relationship("Document", back_populates="videos")
    summary = relationship("Summary", back_populates="videos")
    downloads = relationship("Download", back_populates="video")


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    download_date = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="downloads")
    video = relationship("Video", back_populates="downloads")