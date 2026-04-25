"""
SQLAlchemy DB 모델 — Week 1~2: users, sessions, groups, repos_registry
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, BigInteger, ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


class User(Base):
    """사용자 테이블"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(100))
    email = Column(String(200))
    role = Column(String(20), default="user")  # admin / user
    status = Column(String(20), default="active")  # active / locked / inactive
    last_heartbeat = Column(DateTime, nullable=True)
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    group_memberships = relationship("UserGroup", back_populates="user", cascade="all, delete-orphan")
    owned_repos = relationship("RepoRegistry", back_populates="owner", foreign_keys="RepoRegistry.owner_user_id")


class Session(Base):
    """세션 테이블 — Refresh Token 관리"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(128), unique=True, nullable=False)
    device_info = Column(String(200), nullable=True)
    ip_address = Column(String(45), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계
    user = relationship("User", back_populates="sessions")


class LoginAttempt(Base):
    """로그인 시도 추적 — 브루트포스 방어"""
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    success = Column(Boolean, default=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    """활동 로그"""
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ═══ Week 2: 그룹 + 저장소 레지스트리 ═══


class Group(Base):
    """그룹 테이블"""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    members = relationship("UserGroup", back_populates="group", cascade="all, delete-orphan")
    repos = relationship("RepoRegistry", back_populates="group")


class UserGroup(Base):
    """그룹-사용자 연결 테이블"""
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), default="member")  # owner / admin / member
    joined_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )

    # 관계
    user = relationship("User", back_populates="group_memberships")
    group = relationship("Group", back_populates="members")


class RepoRegistry(Base):
    """저장소 레지스트리 — 메타데이터만 (파일 저장 안 함)"""
    __tablename__ = "repos_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(20), default="personal")  # personal / team
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    latest_revision = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    last_sync_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="active")  # active / archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    owner = relationship("User", back_populates="owned_repos", foreign_keys=[owner_user_id])
    group = relationship("Group", back_populates="repos")
    commits = relationship("CommitLog", back_populates="repo", cascade="all, delete-orphan")
    file_tree = relationship("FileTree", back_populates="repo", cascade="all, delete-orphan")


# ═══ Week 3: 커밋 로그 + 파일 트리 ═══


class CommitLog(Base):
    """커밋 로그 — 클라이언트에서 push된 메타데이터"""
    __tablename__ = "commit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    author = Column(String(100), nullable=False)
    message = Column(Text, nullable=True)
    committed_at = Column(DateTime, nullable=False)
    changed_files = Column(Text, nullable=True)  # JSON: [{action, path, size}, ...]
    received_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repo_id", "revision", name="uq_commit_repo_rev"),
    )

    # 관계
    repo = relationship("RepoRegistry", back_populates="commits")


class FileTree(Base):
    """파일 트리 스냅샷 — 저장소의 현재 파일 구조"""
    __tablename__ = "file_tree"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(1000), nullable=False)
    is_directory = Column(Boolean, default=False)
    file_size = Column(BigInteger, default=0)
    last_revision = Column(Integer, nullable=True)
    last_author = Column(String(100), nullable=True)
    last_modified = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("repo_id", "file_path", name="uq_filetree_repo_path"),
    )

    # 관계
    repo = relationship("RepoRegistry", back_populates="file_tree")


# ═══ Week 4: 미리보기 캐시 + 태그 ═══


class PreviewCacheMeta(Base):
    """미리보기 캐시 메타데이터"""
    __tablename__ = "preview_cache_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(1000), nullable=False)
    revision = Column(Integer, nullable=False)
    cache_file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repo_id", "file_path", "revision", name="uq_preview_cache"),
    )


class Tag(Base):
    """태그 (시스템 전역)"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    file_tags = relationship("FileTag", back_populates="tag", cascade="all, delete-orphan")


class FileTag(Base):
    """파일-태그 연결"""
    __tablename__ = "file_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(1000), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    attached_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    attached_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repo_id", "file_path", "tag_id", name="uq_file_tag"),
    )

    tag = relationship("Tag", back_populates="file_tags")


# ═══ Week 5: 공유 + 알림 ═══


class Share(Base):
    """공유 링크"""
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(1000), nullable=True)  # NULL이면 저장소 전체
    share_token = Column(String(64), unique=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission = Column(String(20), default="view")  # view / download / edit
    password_hash = Column(String(128), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    recipients = relationship("ShareRecipient", back_populates="share", cascade="all, delete-orphan")


class ShareRecipient(Base):
    """공유 수신자"""
    __tablename__ = "share_recipients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    share_id = Column(Integer, ForeignKey("shares.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")  # pending / accepted / rejected
    accessed_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("share_id", "user_id", name="uq_share_recipient"),
    )

    share = relationship("Share", back_populates="recipients")


class Notification(Base):
    """알림"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(30), nullable=False)  # share / approval / mention / system
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)  # 클릭 시 이동 경로
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ═══ Week 6: 승인 워크플로우 ═══


class ApprovalRule(Base):
    """승인 규칙 — 경로 패턴 매칭"""
    __tablename__ = "approval_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=True)  # NULL이면 전체
    path_pattern = Column(String(500), nullable=False)  # 예: /최종본/**
    required_reviewers = Column(Integer, default=1)
    auto_assign_user_ids = Column(Text, nullable=True)  # JSON: [1, 2, 3]
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Approval(Base):
    """승인 요청"""
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(1000), nullable=False)
    revision = Column(Integer, nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending / approved / rejected
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    reviewers = relationship("ApprovalReviewer", back_populates="approval", cascade="all, delete-orphan")


class ApprovalReviewer(Base):
    """승인 검토자"""
    __tablename__ = "approval_reviewers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    approval_id = Column(Integer, ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")  # pending / approved / rejected
    comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    approval = relationship("Approval", back_populates="reviewers")
