from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, AdminUser
from decorators import super_admin_required
from datetime import datetime
from sqlalchemy import or_  # ✅ IMPORT INI

admin_mgmt_bp = Blueprint('admin_mgmt', __name__, url_prefix='/super-admin')

@admin_mgmt_bp.route('/admins')
@login_required
@super_admin_required
def admin_list():
    """List semua admin"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    search = request.args.get('search', '').strip()  # ✅ Tambah strip()
    
    query = AdminUser.query
    
    # ✅ CARA YANG BENAR - Tanpa db.or_()
    if search:
        search_filter = f'%{search}%'
        query = query.filter(
            or_(
                AdminUser.username.ilike(search_filter),
            )
        )
    
    admins = query.order_by(AdminUser.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin_mgmt/admin_list.html', admins=admins, search=search)

@admin_mgmt_bp.route('/admins/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def admin_create():
    """Buat admin baru"""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', 'admin')
            is_active = request.form.get('is_active') == 'on'
            
            # Validasi username sudah ada
            if AdminUser.query.filter_by(username=username).first():  # ✅ UBAH
                flash(f'Username "{username}" sudah digunakan!', 'danger')
                return redirect(url_for('admin_mgmt.admin_create'))
            
            # Buat user baru
            user = AdminUser(  # ✅ UBAH
                username=username,
                role=role,
                is_active=is_active
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash(f'Admin berhasil ditambahkan!', 'success')
            return redirect(url_for('admin_mgmt.admin_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('admin_mgmt/admin_form.html', admin=None)


@admin_mgmt_bp.route('/admins/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def admin_edit(id):
    """Edit admin"""
    admin = AdminUser.query.get_or_404(id)  # ✅ UBAH
    
    # Tidak bisa edit diri sendiri
    if admin.id == current_user.id:
        flash('Tidak dapat mengedit akun Anda sendiri di sini!', 'warning')
        return redirect(url_for('admin_mgmt.admin_list'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', 'admin')
            is_active = request.form.get('is_active') == 'on'
            
            # Validasi username (kecuali milik sendiri)
            existing_user = AdminUser.query.filter_by(username=username).first()  # ✅ UBAH
            if existing_user and existing_user.id != admin.id:
                flash(f'Username "{username}" sudah digunakan!', 'danger')
                return redirect(url_for('admin_mgmt.admin_edit', id=id))
            
            # Update data
            admin.username = username
            admin.role = role
            admin.is_active = is_active
            admin.updated_at = datetime.utcnow()
            
            # Update password jika diisi
            if password:
                admin.set_password(password)
            
            db.session.commit()
            
            flash(f'Admin berhasil diupdate!', 'success')
            return redirect(url_for('admin_mgmt.admin_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('admin_mgmt/admin_form.html', admin=admin)


@admin_mgmt_bp.route('/admins/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def admin_delete(id):
    """Hapus admin"""
    admin = AdminUser.query.get_or_404(id)  # ✅ UBAH
    
    # Tidak bisa hapus diri sendiri
    if admin.id == current_user.id:
        flash('Tidak dapat menghapus akun Anda sendiri!', 'danger')
        return redirect(url_for('admin_mgmt.admin_list'))
    
    # Tidak bisa hapus super admin lain
    # ✅ UBAH: is_super_admin sekarang adalah property, bukan method
    if admin.is_super_admin:  # Tanpa ()
        flash('Tidak dapat menghapus Super Admin!', 'danger')
        return redirect(url_for('admin_mgmt.admin_list'))
    
    try:
        username = admin.username
        db.session.delete(admin)
        db.session.commit()
        
        flash(f'Admin "{username}" berhasil dihapus!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin_mgmt.admin_list'))


@admin_mgmt_bp.route('/admins/<int:id>/toggle-status', methods=['POST'])
@login_required
@super_admin_required
def admin_toggle_status(id):
    """Toggle status aktif/nonaktif admin"""
    admin = AdminUser.query.get_or_404(id)  # ✅ UBAH
    
    # Tidak bisa toggle diri sendiri
    if admin.id == current_user.id:
        flash('Tidak dapat mengubah status akun Anda sendiri!', 'danger')
        return redirect(url_for('admin_mgmt.admin_list'))
    
    try:
        admin.is_active = not admin.is_active
        admin.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'diaktifkan' if admin.is_active else 'dinonaktifkan'
        flash(f'Admin "{admin.username}" berhasil {status}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin_mgmt.admin_list'))