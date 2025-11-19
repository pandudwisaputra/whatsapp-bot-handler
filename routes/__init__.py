"""
Routes package for WhatsApp Bot Kemenag
"""

from routes.admin import admin_bp, login_required
from routes.layanan_routes import layanan_bp

__all__ = ['admin_bp', 'layanan_bp', 'login_required']