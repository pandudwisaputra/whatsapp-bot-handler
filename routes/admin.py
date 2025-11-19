"""
Admin routes untuk web dashboard
WhatsApp Bot Kemenag Kabupaten Madiun
SECURE VERSION with Flask-Login
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Message, UserSession, AdminUser
from datetime import datetime, timedelta
from sqlalchemy import func, desc

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ============================================
# Authentication Routes
# ============================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    # Jika sudah login, redirect ke dashboard
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        admin = AdminUser.query.filter_by(username=username).first()
        
        # Verify credentials
        if admin and admin.check_password(password):
            if not admin.is_active:
                flash('Akun Anda tidak aktif. Hubungi administrator.', 'danger')
                return redirect(url_for('admin.login'))
            
            # ✅ LOGIN dengan Flask-Login
            login_user(admin, remember=bool(remember))
            
            # Update last login
            admin.last_login = datetime.utcnow()
            db.session.commit()
            
            flash(f'Selamat datang, {admin.username}!', 'success')
            
            # Redirect ke halaman yang diminta atau dashboard
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
    # ✅ LOGOUT dengan Flask-Login
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
    """Dashboard utama"""
    today = datetime.utcnow().date()
    
    # Statistics
    total_users = User.query.count()
    total_messages = Message.query.count()
    
    # Today's stats
    today_start = datetime.combine(today, datetime.min.time())
    today_messages_in = Message.query.filter(
        Message.direction == 'incoming',
        Message.timestamp >= today_start
    ).count()
    
    today_messages_out = Message.query.filter(
        Message.direction == 'outgoing',
        Message.timestamp >= today_start
    ).count()
    
    # Active users (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    active_users = User.query.filter(User.last_interaction >= yesterday).count()
    
    # Recent messages
    recent_messages = Message.query.order_by(desc(Message.timestamp)).limit(10).all()
    
    # Popular services (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    popular_services = db.session.query(
        Message.service_type,
        func.count(Message.id).label('count')
    ).filter(
        Message.service_type.isnot(None),
        Message.timestamp >= week_ago
    ).group_by(Message.service_type).order_by(desc('count')).limit(5).all()
    
    # Chart data - Messages per day (last 7 days)
    chart_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())
        
        incoming = Message.query.filter(
            Message.direction == 'incoming',
            Message.timestamp >= date_start,
            Message.timestamp <= date_end
        ).count()
        
        outgoing = Message.query.filter(
            Message.direction == 'outgoing',
            Message.timestamp >= date_start,
            Message.timestamp <= date_end
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
    messages = Message.query.filter_by(user_id=user_id).order_by(desc(Message.timestamp)).limit(50).all()
    
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
    """Daftar pesan"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    direction = request.args.get('direction', '')
    message_type = request.args.get('type', '')
    date_filter = request.args.get('date', '')
    
    query = Message.query
    
    if direction:
        query = query.filter_by(direction=direction)
    
    if message_type:
        query = query.filter_by(message_type=message_type)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            date_start = datetime.combine(filter_date, datetime.min.time())
            date_end = datetime.combine(filter_date, datetime.max.time())
            query = query.filter(Message.timestamp >= date_start, Message.timestamp <= date_end)
        except:
            pass
    
    messages_paginated = query.order_by(desc(Message.timestamp)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/messages.html', 
        messages=messages_paginated,
        direction=direction,
        message_type=message_type,
        date_filter=date_filter
    )


# ============================================
# Analytics Routes
# ============================================

@admin_bp.route('/analytics')
@login_required
def analytics():
    """Analytics page"""
    # Date range
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    
    # Daily analytics
    daily_data = []
    current_date = start_date
    while current_date <= end_date:
        date_start = datetime.combine(current_date, datetime.min.time())
        date_end = datetime.combine(current_date, datetime.max.time())
        
        # Count messages
        incoming = Message.query.filter(
            Message.direction == 'incoming',
            Message.timestamp >= date_start,
            Message.timestamp <= date_end
        ).count()
        
        outgoing = Message.query.filter(
            Message.direction == 'outgoing',
            Message.timestamp >= date_start,
            Message.timestamp <= date_end
        ).count()
        
        # Count new users
        new_users = User.query.filter(
            User.first_interaction >= date_start,
            User.first_interaction <= date_end
        ).count()
        
        daily_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'incoming': incoming,
            'outgoing': outgoing,
            'new_users': new_users
        })
        
        current_date += timedelta(days=1)
    
    # Service popularity
    service_stats = db.session.query(
        Message.service_type,
        func.count(Message.id).label('count')
    ).filter(
        Message.service_type.isnot(None)
    ).group_by(Message.service_type).order_by(desc('count')).all()
    
    return render_template('admin/analytics.html',
        daily_data=daily_data,
        service_stats=service_stats,
        days=days
    )


# ============================================
# API Routes
# ============================================

@admin_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint untuk real-time stats"""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    stats = {
        'total_users': User.query.count(),
        'total_messages': Message.query.count(),
        'today_incoming': Message.query.filter(
            Message.direction == 'incoming',
            Message.timestamp >= today_start
        ).count(),
        'today_outgoing': Message.query.filter(
            Message.direction == 'outgoing',
            Message.timestamp >= today_start
        ).count(),
        'active_now': User.query.filter(
            User.last_interaction >= datetime.utcnow() - timedelta(minutes=5)
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
        # Update password
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # ✅ Gunakan current_user dari Flask-Login
        if current_user.check_password(current_password):
            if len(new_password) < 8:
                flash('Password baru minimal 8 karakter', 'danger')
            elif new_password == confirm_password:
                # Update password
                current_user.set_password(new_password)
                db.session.commit()
                flash('Password berhasil diupdate', 'success')
                
                # Optional: Log activity
                from decorators import log_admin_activity
                log_admin_activity('password_change', description=f'Admin {current_user.username} changed password')
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
        # Update profile info
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        
        if email:
            current_user.email = email
        if full_name:
            current_user.full_name = full_name
        
        db.session.commit()
        flash('Profil berhasil diupdate', 'success')
        
        return redirect(url_for('admin.profile'))
    
    return render_template('admin/profile.html')