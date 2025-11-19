from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def super_admin_required(f):
    """Decorator untuk membatasi akses hanya untuk super admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Silakan login terlebih dahulu!', 'warning')
            return redirect(url_for('auth.login'))
        
        # ✅ UBAH BARIS INI - Tanpa () karena is_super_admin adalah @property
        if not current_user.is_super_admin:  # ← TANPA ()
            flash('Akses ditolak! Anda bukan Super Admin.', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function