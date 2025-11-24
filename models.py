"""
Database models untuk tracking pesan WhatsApp
ENHANCED: Termasuk tabel untuk data layanan dan admin management
UPDATED: Message.service_type diganti dengan layanan_id (Foreign Key)
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz

db = SQLAlchemy()

# Timezone Indonesia Bagian Barat
WIB = pytz.timezone('Asia/Jakarta')

def get_wib_time():
    """Get current time in WIB timezone"""
    return datetime.now(WIB)


class User(db.Model):
    """Model untuk user WhatsApp"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100))
    first_interaction = db.Column(db.DateTime, default=get_wib_time)
    last_interaction = db.Column(db.DateTime, default=get_wib_time)
    total_messages = db.Column(db.Integer, default=0)
    
    # Relationship
    messages = db.relationship('Message', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=get_wib_time)
    updated_at = db.Column(db.DateTime, default=get_wib_time, onupdate=get_wib_time)
    
    def __repr__(self):
        return f'<User {self.phone_number}>'


class Message(db.Model):
    """Model untuk pesan WhatsApp - UPDATED: service_type diganti layanan_id"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Message details
    direction = db.Column(db.String(10), nullable=False)  # 'incoming' atau 'outgoing'
    message_type = db.Column(db.String(20))  # 'text', 'interactive', 'button', dll
    content = db.Column(db.Text)
    
    # UPDATED: Relasi dengan layanan (ganti service_type)
    layanan_id = db.Column(db.String(50), db.ForeignKey('layanan.layanan_id'))
    
    # Status
    status = db.Column(db.String(20), default='sent')  # sent, delivered, read, failed
    error_message = db.Column(db.Text)
    
    # Timestamps
    timestamp = db.Column(db.DateTime, default=get_wib_time)
    created_at = db.Column(db.DateTime, default=get_wib_time)
    
    # Relationship dengan Layanan
    layanan = db.relationship('Layanan', backref='messages', foreign_keys=[layanan_id])
    
    def __repr__(self):
        return f'<Message {self.message_id}>'
    
    def to_dict(self):
        """Convert to dictionary dengan nama layanan"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'direction': self.direction,
            'message_type': self.message_type,
            'content': self.content,
            'layanan_id': self.layanan_id,
            'layanan_nama': self.layanan.judul if self.layanan else None,
            'status': self.status,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserSession(db.Model):
    """Model untuk session user"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Session data - current_layanan now VARCHAR(50)
    current_category = db.Column(db.String(50))
    current_layanan = db.Column(db.String(50))
    last_interaction = db.Column(db.String(50))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_wib_time)
    updated_at = db.Column(db.DateTime, default=get_wib_time, onupdate=get_wib_time)
    
    def __repr__(self):
        return f'<Session User-{self.user_id}>'


class AdminUser(UserMixin, db.Model):
    """Model untuk admin login dengan role management"""
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Role management
    role = db.Column(db.String(20), default='admin')  # 'super_admin' atau 'admin'
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_wib_time)
    updated_at = db.Column(db.DateTime, default=get_wib_time, onupdate=get_wib_time)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        """Hash dan set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifikasi password"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_super_admin(self):
        """Check apakah user adalah super admin"""
        return self.role == 'super_admin'
    
    def __repr__(self):
        return f'<AdminUser {self.username}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'is_super_admin': self.is_super_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class Kategori(db.Model):
    """Model untuk kategori layanan"""
    __tablename__ = 'kategori'
    
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(50), unique=True, nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10))
    urutan = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship
    layanan = db.relationship('Layanan', backref='kategori', lazy='dynamic', cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=get_wib_time)
    updated_at = db.Column(db.DateTime, default=get_wib_time, onupdate=get_wib_time)
    
    def __repr__(self):
        return f'<Kategori {self.kode}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'kode': self.kode,
            'nama': self.nama,
            'icon': self.icon,
            'urutan': self.urutan,
            'is_active': self.is_active
        }


class Layanan(db.Model):
    """Model untuk layanan"""
    __tablename__ = 'layanan'
    
    layanan_id = db.Column(db.String(50), primary_key=True)
    kategori_id = db.Column(db.Integer, db.ForeignKey('kategori.id'), nullable=False)
    
    # Detail layanan
    judul = db.Column(db.String(500), nullable=False)
    jangka_waktu = db.Column(db.String(200))
    biaya = db.Column(db.String(200))
    qrcode = db.Column(db.String(500))
    
    urutan = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship
    persyaratan = db.relationship('Persyaratan', backref='layanan', lazy='dynamic', cascade='all, delete-orphan')
    sop = db.relationship('SOP', backref='layanan', lazy='dynamic', cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=get_wib_time)
    updated_at = db.Column(db.DateTime, default=get_wib_time, onupdate=get_wib_time)
    
    def __repr__(self):
        return f'<Layanan {self.layanan_id}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.layanan_id,
            'layanan_id': self.layanan_id,
            'judul': self.judul,
            'Jangka Waktu Pelayanan': self.jangka_waktu,
            'Biaya/Tarif': self.biaya,
            'qrcode': self.qrcode,
            'PERSYARATAN': [p.teks for p in self.persyaratan.filter_by(is_active=True).order_by(Persyaratan.urutan).all()],
            'SOP': [s.teks for s in self.sop.filter_by(is_active=True).order_by(SOP.urutan).all()]
        }


class Persyaratan(db.Model):
    """Model untuk persyaratan layanan"""
    __tablename__ = 'persyaratan'
    
    id = db.Column(db.Integer, primary_key=True)
    layanan_id = db.Column(db.String(50), db.ForeignKey('layanan.layanan_id'), nullable=False)
    teks = db.Column(db.Text, nullable=False)
    urutan = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=get_wib_time)
    
    def __repr__(self):
        return f'<Persyaratan {self.id}>'


class SOP(db.Model):
    """Model untuk SOP layanan"""
    __tablename__ = 'sop'
    
    id = db.Column(db.Integer, primary_key=True)
    layanan_id = db.Column(db.String(50), db.ForeignKey('layanan.layanan_id'), nullable=False)
    teks = db.Column(db.Text, nullable=False)
    urutan = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=get_wib_time)
    
    def __repr__(self):
        return f'<SOP {self.id}>'