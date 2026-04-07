import os
import json
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

# ==================== 配置 ====================
# 优先使用 Neon 连接字符串（HF Space / Docker 环境变量）
DATABASE_URL = os.getenv("NEON_DATABASE_URL") or f"sqlite:///{os.path.join('data', 'data.db')}"

IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# 创建引擎
if IS_POSTGRES:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
else:
    os.makedirs("data", exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== 表定义 ====================
class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    token_data = Column(JSON if IS_POSTGRES else Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemKV(Base):
    __tablename__ = "system_kv"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)

# ==================== 初始化 ====================
def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def init_db():
    """初始化数据库表（Neon 或 SQLite）"""
    Base.metadata.create_all(bind=engine)
    db_type = "Neon Postgres" if IS_POSTGRES else "本地 SQLite"
    print(f"[{ts()}] [系统] 数据库模块初始化完成 → {db_type}")

# ==================== 公共 Session ====================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== 8 个核心函数（全部适配） ====================
def save_account_to_db(email: str, password: str, token_json_str: str) -> bool:
    """账号、密码和 Token 数据存入数据库"""
    try:
        db = SessionLocal()
        token_data = json.loads(token_json_str) if token_json_str else None
        account = db.query(Account).filter(Account.email == email).first()
        if account:
            account.password = password
            account.token_data = token_data
        else:
            account = Account(email=email, password=password, token_data=token_data)
            db.add(account)
        db.commit()
        return True
    except SQLAlchemyError as e:
        print(f"[{ts()}] [ERROR] 数据库保存失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def get_all_accounts() -> list:
    """获取所有账号列表，按最新时间倒序"""
    try:
        db = SessionLocal()
        accounts = db.query(Account).order_by(Account.id.desc()).all()
        return [
            {
                "email": a.email,
                "password": a.password,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in accounts
        ]
    except Exception as e:
        print(f"[{ts()}] [ERROR] 获取账号列表失败: {e}")
        return []
    finally:
        db.close()

def get_token_by_email(email: str) -> dict:
    """根据邮箱提取完整的 Token JSON 数据"""
    try:
        db = SessionLocal()
        account = db.query(Account).filter(Account.email == email).first()
        if account and account.token_data:
            return account.token_data if IS_POSTGRES else json.loads(account.token_data)
        return None
    except Exception as e:
        print(f"[{ts()}] [ERROR] 读取 Token 失败: {e}")
        return None
    finally:
        db.close()

def get_tokens_by_emails(emails: list) -> list:
    """根据邮箱列表批量提取 Token"""
    if not emails:
        return []
    try:
        db = SessionLocal()
        accounts = db.query(Account).filter(Account.email.in_(emails)).all()
        export_list = []
        for a in accounts:
            if a.token_data:
                try:
                    data = a.token_data if IS_POSTGRES else json.loads(a.token_data)
                    export_list.append(data)
                except:
                    pass
        return export_list
    except Exception as e:
        print(f"[{ts()}] [ERROR] 批量读取 Token 失败: {e}")
        return []
    finally:
        db.close()

def delete_accounts_by_emails(emails: list) -> bool:
    """批量删除账号"""
    if not emails:
        return True
    try:
        db = SessionLocal()
        db.query(Account).filter(Account.email.in_(emails)).delete()
        db.commit()
        return True
    except Exception as e:
        print(f"[{ts()}] [ERROR] 数据库批量删除账号异常: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def get_accounts_page(page: int = 1, page_size: int = 50) -> dict:
    """带分页的账号拉取功能"""
    try:
        db = SessionLocal()
        total = db.query(Account).count()
        offset = (page - 1) * page_size
        accounts = db.query(Account).order_by(Account.id.desc()).offset(offset).limit(page_size).all()
        
        data = [
            {
                "email": a.email,
                "password": a.password,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in accounts
        ]
        return {"total": total, "data": data}
    except Exception as e:
        print(f"[{ts()}] [ERROR] 分页获取账号列表失败: {e}")
        return {"total": 0, "data": []}
    finally:
        db.close()

def set_sys_kv(key: str, value: Any):
    """保存任意数据到系统表"""
    try:
        val_str = json.dumps(value, ensure_ascii=False)
        db = SessionLocal()
        kv = db.query(SystemKV).filter(SystemKV.key == key).first()
        if kv:
            kv.value = val_str
        else:
            kv = SystemKV(key=key, value=val_str)
            db.add(kv)
        db.commit()
    except Exception as e:
        print(f"[{ts()}] [ERROR] 系统配置保存失败: {e}")
    finally:
        db.close()

def get_sys_kv(key: str, default=None):
    """从系统表读取数据"""
    try:
        db = SessionLocal()
        kv = db.query(SystemKV).filter(SystemKV.key == key).first()
        if kv and kv.value:
            return json.loads(kv.value)
    except Exception:
        pass
    finally:
        db.close()
    return default
