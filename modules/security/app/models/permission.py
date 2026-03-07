from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    code = Column(String(128), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

    module = relationship("Module", back_populates="permissions")
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")
    user_permissions = relationship("UserPermission", back_populates="permission")


class UserPermission(Base):
    __tablename__ = "user_permissions"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    granted = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="direct_permissions")
    permission = relationship("Permission", back_populates="user_permissions")


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    expires_at = Column(String(64), nullable=False)
