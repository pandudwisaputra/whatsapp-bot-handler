"""
Admin routes untuk web dashboard
WhatsApp Bot Kemenag Kabupaten Madiun
SECURE VERSION with Flask-Login
UPDATED: Menghapus semua referensi ke service_type
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Message, User, UserSession, AdminUser, Layanan, Kategori, get_wib_time
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from collections import defaultdict

admin_bp = Blueprint('admin', __name__)


# ============================================
# Authentication Routes
# ============================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        admin = AdminUser.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            if not admin.is_active:
                flash('Akun Anda tidak aktif. Hubungi administrator.', 'danger')
                return redirect(url_for('admin.login'))
            
            login_user(admin, remember=bool(remember))
            admin.last_login = get_wib_time()
            db.session.commit()
            
            flash(f'Selamat datang, {admin.username}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin.dashboard'))
        else:
            flash('Username atau password salah', 'danger')
    
    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    """Logout"""
    username = current_user.username
    logout_user()
    flash(f'Logout berhasil. Sampai jumpa, {username}!', 'info')
    return redirect(url_for('admin.login'))


# ============================================
# Dashboard Routes
# ============================================

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard utama - UPDATED: Hapus referensi service_type"""
    today = get_wib_time().date()
    
    # Statistics
    total_users = User.query.count()
    total_messages = Message.query.count()
    
    # Today's stats
    today_start = datetime.combine(today, datetime.min.time())
    today_start = get_wib_time().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_messages_in = Message.query.filter(
        Message.direction == 'incoming',
        Message.created_at >= today_start
    ).count()
    
    today_messages_out = Message.query.filter(
        Message.direction == 'outgoing',
        Message.created_at >= today_start
    ).count()
    
    # Active users (last 24 hours)
    yesterday = get_wib_time() - timedelta(days=1)
    active_users = User.query.filter(User.last_interaction >= yesterday).count()
    
    # Recent messages
    recent_messages = Message.query.order_by(desc(Message.created_at)).limit(10).all()
    
    # UPDATED: Popular services dengan JOIN ke Layanan (last 7 days)
    week_ago = get_wib_time() - timedelta(days=7)
    popular_services = db.session.query(
        Layanan.judul,
        func.count(Message.id).label('count')
    ).join(
        Message, Message.layanan_id == Layanan.layanan_id
    ).filter(
        Message.layanan_id.isnot(None),
        Message.created_at >= week_ago
    ).group_by(
        Layanan.judul
    ).order_by(desc('count')).limit(5).all()
    
    # Chart data - Messages per day (last 7 days)
    chart_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())
        
        incoming = Message.query.filter(
            Message.direction == 'incoming',
            Message.created_at >= date_start,
            Message.created_at <= date_end
        ).count()
        
        outgoing = Message.query.filter(
            Message.direction == 'outgoing',
            Message.created_at >= date_start,
            Message.created_at <= date_end
        ).count()
        
        chart_data.append({
            'date': date.strftime('%d/%m'),
            'incoming': incoming,
            'outgoing': outgoing
        })
    
    return render_template('admin/dashboard.html',
        total_users=total_users,
        total_messages=total_messages,
        today_messages_in=today_messages_in,
        today_messages_out=today_messages_out,
        active_users=active_users,
        recent_messages=recent_messages,
        popular_services=popular_services,
        chart_data=chart_data
    )


# ============================================
# User Management Routes
# ============================================

@admin_bp.route('/users')
@login_required
def users():
    """Daftar user"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    search = request.args.get('search', '')
    
    query = User.query
    if search:
        query = query.filter(User.phone_number.contains(search))
    
    users_paginated = query.order_by(desc(User.last_interaction)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users_paginated, search=search)


@admin_bp.route('/users/<int:user_id>')
@login_required
def user_detail(user_id):
    """Detail user"""
    user = User.query.get_or_404(user_id)
    
    # Get user messages
    messages = Message.query.filter_by(user_id=user_id).order_by(desc(Message.created_at)).limit(50).all()
    
    # Get session info
    session_info = UserSession.query.filter_by(user_id=user_id).first()
    
    return render_template('admin/user_detail.html', 
        user=user, 
        messages=messages,
        session_info=session_info
    )


# ============================================
# Message Management Routes
# ============================================

@admin_bp.route('/messages')
@login_required
def messages():
    """Message history - UPDATED: Tampilkan nama layanan"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        direction = request.args.get('direction', '')
        search = request.args.get('search', '')
        
        query = Message.query
        
        # Filter by direction
        if direction in ['incoming', 'outgoing']:
            query = query.filter_by(direction=direction)
        
        # Search by phone number
        if search:
            query = query.join(User).filter(
                User.phone_number.like(f'%{search}%')
            )
        
        # Order by newest first
        query = query.order_by(Message.created_at.desc())
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        messages = pagination.items
        
        # UPDATED: Convert to dict dengan nama layanan
        messages_data = []
        for msg in messages:
            msg_dict = {
                'id': msg.id,
                'message_id': msg.message_id,
                'direction': msg.direction,
                'message_type': msg.message_type,
                'content': msg.content[:100] + '...' if msg.content and len(msg.content) > 100 else msg.content,
                'layanan_nama': msg.layanan.judul if msg.layanan else None,
                'layanan_id': msg.layanan_id,
                'phone_number': msg.user.phone_number,
                'status': msg.status,
                'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else None
            }
            messages_data.append(msg_dict)
        
        return render_template(
            'admin/messages.html',
            messages=messages_data,
            pagination=pagination,
            direction=direction,
            search=search
        )
        
    except Exception as e:
        flash(f'Error loading messages: {str(e)}', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/api/layanan/<layanan_id>')
@login_required
def get_layanan_detail(layanan_id):
    """API untuk mendapatkan detail layanan"""
    try:
        layanan = Layanan.query.get(layanan_id)
        if not layanan:
            return jsonify({'error': 'Layanan tidak ditemukan'}), 404
        
        return jsonify({
            'layanan_id': layanan.layanan_id,
            'judul': layanan.judul,
            'kategori': layanan.kategori.nama,
            'jangka_waktu': layanan.jangka_waktu,
            'biaya': layanan.biaya
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# Analytics Routes
# ============================================

@admin_bp.route('/analytics')
@login_required
def analytics():
    """Analytics dashboard - UPDATED: Tampilkan nama layanan"""
    try:
        days = int(request.args.get('days', 30))
        days = min(max(days, 1), 365)
        
        start_date = get_wib_time() - timedelta(days=days)
        
        # Daily statistics
        daily_data = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            next_date = date + timedelta(days=1)
            
            incoming = Message.query.filter(
                Message.direction == 'incoming',
                Message.created_at >= date,
                Message.created_at < next_date
            ).count()
            
            outgoing = Message.query.filter(
                Message.direction == 'outgoing',
                Message.created_at >= date,
                Message.created_at < next_date
            ).count()
            
            new_users = User.query.filter(
                User.created_at >= date,
                User.created_at < next_date
            ).count()
            
            daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'incoming': incoming,
                'outgoing': outgoing,
                'new_users': new_users
            })
        
        # UPDATED: Service statistics dengan JOIN ke tabel Layanan
        service_stats_query = db.session.query(
            Layanan.judul,
            func.count(Message.id).label('count')
        ).join(
            Message, Message.layanan_id == Layanan.layanan_id
        ).filter(
            Message.created_at >= start_date,
            Message.layanan_id.isnot(None)
        ).group_by(
            Layanan.judul
        ).order_by(
            desc('count')
        ).all()
        
        # Convert to list of tuples
        service_stats = [(row.judul, row.count) for row in service_stats_query]
        
        return render_template(
            'admin/analytics.html',
            daily_data=daily_data,
            service_stats=service_stats,
            days=days
        )
        
    except Exception as e:
        flash(f'Error loading analytics: {str(e)}', 'danger')
        return redirect(url_for('admin.dashboard'))


# ============================================
# API Routes
# ============================================

@admin_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint untuk real-time stats"""
    today_start = get_wib_time().replace(hour=0, minute=0, second=0, microsecond=0)
    
    stats = {
        'total_users': User.query.count(),
        'total_messages': Message.query.count(),
        'today_incoming': Message.query.filter(
            Message.direction == 'incoming',
            Message.created_at >= today_start
        ).count(),
        'today_outgoing': Message.query.filter(
            Message.direction == 'outgoing',
            Message.created_at >= today_start
        ).count(),
        'active_now': User.query.filter(
            User.last_interaction >= get_wib_time() - timedelta(minutes=5)
        ).count()
    }
    
    return jsonify(stats)


# ============================================
# Settings Routes
# ============================================

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Settings page"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_user.check_password(current_password):
            if len(new_password) < 8:
                flash('Password baru minimal 8 karakter', 'danger')
            elif new_password == confirm_password:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Password berhasil diupdate', 'success')
            else:
                flash('Password baru tidak cocok', 'danger')
        else:
            flash('Password lama salah', 'danger')
        
        return redirect(url_for('admin.settings'))
    
    return render_template('admin/settings.html')


# ============================================
# Profile Routes
# ============================================

@admin_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Admin profile page"""
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        
        if full_name:
            current_user.full_name = full_name
        
        db.session.commit()
        flash('Profil berhasil diupdate', 'success')
        
        return redirect(url_for('admin.profile'))
    
    return render_template('admin/profile.html')