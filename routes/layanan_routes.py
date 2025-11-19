"""
CRUD Routes untuk Manajemen Layanan
WhatsApp Bot Kemenag Kabupaten Madiun
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from models import db, Kategori, Layanan, Persyaratan, SOP
from datetime import datetime
from sqlalchemy import desc
from routes import login_required  # ✅ Import dari package
from routes.admin import login_required
from .admin import login_required  # ✅ Relative import

layanan_bp = Blueprint('layanan', __name__, url_prefix='/admin/layanan')


# ============================================
# KATEGORI CRUD
# ============================================

@layanan_bp.route('/kategori')
@login_required
def kategori_list():
    """List semua kategori"""
    kategoris = Kategori.query.order_by(Kategori.urutan).all()
    return render_template('layanan/kategori_list.html', kategoris=kategoris)


@layanan_bp.route('/kategori/create', methods=['GET', 'POST'])
@login_required
def kategori_create():
    """Create kategori baru"""
    if request.method == 'POST':
        try:
            kode = request.form.get('kode')
            nama = request.form.get('nama')
            icon = request.form.get('icon')
            urutan = request.form.get('urutan', 0, type=int)
            is_active = request.form.get('is_active') == 'on'
            
            # Check if kode already exists
            existing = Kategori.query.filter_by(kode=kode).first()
            if existing:
                flash(f'Kategori dengan kode "{kode}" sudah ada!', 'danger')
                return redirect(url_for('layanan.kategori_create'))
            
            kategori = Kategori(
                kode=kode,
                nama=nama,
                icon=icon,
                urutan=urutan,
                is_active=is_active
            )
            
            db.session.add(kategori)
            db.session.commit()
            
            flash(f'Kategori "{nama}" berhasil ditambahkan!', 'success')
            return redirect(url_for('layanan.kategori_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('layanan/kategori_form.html', kategori=None)


@layanan_bp.route('/kategori/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def kategori_edit(id):
    """Edit kategori"""
    kategori = Kategori.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            kategori.nama = request.form.get('nama')
            kategori.icon = request.form.get('icon')
            kategori.urutan = request.form.get('urutan', 0, type=int)
            kategori.is_active = request.form.get('is_active') == 'on'
            
            db.session.commit()
            
            flash(f'Kategori "{kategori.nama}" berhasil diupdate!', 'success')
            return redirect(url_for('layanan.kategori_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('layanan/kategori_form.html', kategori=kategori)


@layanan_bp.route('/kategori/<int:id>/delete', methods=['POST'])
@login_required
def kategori_delete(id):
    """Delete kategori"""
    try:
        kategori = Kategori.query.get_or_404(id)
        
        # Check if has layanan
        layanan_count = kategori.layanan.count()
        if layanan_count > 0:
            flash(f'Tidak bisa hapus! Kategori memiliki {layanan_count} layanan.', 'danger')
            return redirect(url_for('layanan.kategori_list'))
        
        nama = kategori.nama
        db.session.delete(kategori)
        db.session.commit()
        
        flash(f'Kategori "{nama}" berhasil dihapus!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('layanan.kategori_list'))


# ============================================
# LAYANAN CRUD
# ============================================

@layanan_bp.route('/')
@login_required
def layanan_list():
    """List semua layanan"""
    kategori_id = request.args.get('kategori_id', type=int)
    search = request.args.get('search', '')
    
    query = Layanan.query
    
    if kategori_id:
        query = query.filter_by(kategori_id=kategori_id)
    
    if search:
        query = query.filter(Layanan.judul.contains(search))
    
    layanans = query.order_by(Layanan.kategori_id, Layanan.urutan).all()
    kategoris = Kategori.query.order_by(Kategori.urutan).all()
    
    return render_template('layanan/layanan_list.html', 
                         layanans=layanans, 
                         kategoris=kategoris,
                         selected_kategori=kategori_id,
                         search=search)


@layanan_bp.route('/create', methods=['GET', 'POST'])
@login_required
def layanan_create():
    """Create layanan baru"""
    kategoris = Kategori.query.order_by(Kategori.urutan).all()
    
    if request.method == 'POST':
        try:
            # Ambil kategori_id terlebih dahulu
            kategori_id = request.form.get('kategori_id', type=int)
            kategori = Kategori.query.get(kategori_id)
            
            if not kategori:
                flash('Kategori tidak ditemukan!', 'danger')
                return redirect(url_for('layanan.layanan_create'))
            
            # Generate layanan_id otomatis berdasarkan kode kategori
            kode_kategori = kategori.kode  # Misal: 'kepeg', 'umum', dll
            
            # Cari layanan terakhir dengan prefix yang sama
            last_layanan = Layanan.query.filter(
                Layanan.layanan_id.like(f'{kode_kategori}_%')
            ).order_by(
                Layanan.layanan_id.desc()
            ).first()
            
            # Generate nomor urut baru
            if last_layanan:
                # Extract nomor dari layanan_id terakhir (misal: kepeg_5 -> 5)
                try:
                    last_number = int(last_layanan.layanan_id.split('_')[-1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            
            # Buat layanan_id baru
            layanan_id = f"{kode_kategori}_{new_number}"
            
            # Double check apakah ID sudah ada (untuk keamanan)
            while Layanan.query.filter_by(layanan_id=layanan_id).first():
                new_number += 1
                layanan_id = f"{kode_kategori}_{new_number}"
            
            # Ambil data form lainnya
            judul = request.form.get('judul')
            jangka_waktu = request.form.get('jangka_waktu')
            biaya = request.form.get('biaya')
            qrcode = request.form.get('qrcode')
            urutan = request.form.get('urutan', 0, type=int)
            is_active = request.form.get('is_active') == 'on'
            
            # Buat layanan baru
            layanan = Layanan(
                layanan_id=layanan_id,  # ID otomatis
                kategori_id=kategori_id,
                judul=judul,
                jangka_waktu=jangka_waktu,
                biaya=biaya,
                qrcode=qrcode,
                urutan=urutan,
                is_active=is_active
            )
            
            db.session.add(layanan)
            db.session.flush()  # Get ID
            
            # Add persyaratan
            persyaratan_list = request.form.getlist('persyaratan[]')
            for idx, syarat in enumerate(persyaratan_list, 1):
                if syarat.strip():
                    persyaratan = Persyaratan(
                        layanan_id=layanan.id,
                        teks=syarat.strip(),
                        urutan=idx
                    )
                    db.session.add(persyaratan)
            
            # Add SOP
            sop_list = request.form.getlist('sop[]')
            for idx, sop_text in enumerate(sop_list, 1):
                if sop_text.strip():
                    sop = SOP(
                        layanan_id=layanan.id,
                        teks=sop_text.strip(),
                        urutan=idx
                    )
                    db.session.add(sop)
            
            db.session.commit()
            
            flash(f'Layanan "{judul}" berhasil ditambahkan dengan ID: {layanan_id}!', 'success')
            return redirect(url_for('layanan.layanan_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('layanan/layanan_form.html', layanan=None, kategoris=kategoris)

@layanan_bp.route('/<int:id>')
@login_required
def layanan_detail(id):
    """Detail layanan"""
    layanan = Layanan.query.get_or_404(id)
    persyaratans = layanan.persyaratan.order_by(Persyaratan.urutan).all()
    sops = layanan.sop.order_by(SOP.urutan).all()
    
    return render_template('layanan/layanan_detail.html', 
                         layanan=layanan,
                         persyaratans=persyaratans,
                         sops=sops)


@layanan_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def layanan_edit(id):
    """Edit layanan"""
    layanan = Layanan.query.get_or_404(id)
    kategoris = Kategori.query.order_by(Kategori.urutan).all()
    
    if request.method == 'POST':
        try:
            layanan.kategori_id = request.form.get('kategori_id', type=int)
            layanan.judul = request.form.get('judul')
            layanan.jangka_waktu = request.form.get('jangka_waktu')
            layanan.biaya = request.form.get('biaya')
            layanan.qrcode = request.form.get('qrcode')
            layanan.urutan = request.form.get('urutan', 0, type=int)
            layanan.is_active = request.form.get('is_active') == 'on'
            
            # Delete old persyaratan & sop
            Persyaratan.query.filter_by(layanan_id=layanan.id).delete()
            SOP.query.filter_by(layanan_id=layanan.id).delete()
            
            # Add new persyaratan
            persyaratan_list = request.form.getlist('persyaratan[]')
            for idx, syarat in enumerate(persyaratan_list, 1):
                if syarat.strip():
                    persyaratan = Persyaratan(
                        layanan_id=layanan.id,
                        teks=syarat.strip(),
                        urutan=idx
                    )
                    db.session.add(persyaratan)
            
            # Add new SOP
            sop_list = request.form.getlist('sop[]')
            for idx, sop_text in enumerate(sop_list, 1):
                if sop_text.strip():
                    sop = SOP(
                        layanan_id=layanan.id,
                        teks=sop_text.strip(),
                        urutan=idx
                    )
                    db.session.add(sop)
            
            db.session.commit()
            
            flash(f'Layanan "{layanan.judul}" berhasil diupdate!', 'success')
            return redirect(url_for('layanan.layanan_detail', id=layanan.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    persyaratans = layanan.persyaratan.order_by(Persyaratan.urutan).all()
    sops = layanan.sop.order_by(SOP.urutan).all()
    
    return render_template('layanan/layanan_form.html', 
                         layanan=layanan, 
                         kategoris=kategoris,
                         persyaratans=persyaratans,
                         sops=sops)


@layanan_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def layanan_delete(id):
    """Delete layanan"""
    try:
        layanan = Layanan.query.get_or_404(id)
        judul = layanan.judul
        
        # Cascade delete akan hapus persyaratan & sop otomatis
        db.session.delete(layanan)
        db.session.commit()
        
        flash(f'Layanan "{judul}" berhasil dihapus!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('layanan.layanan_list'))


@layanan_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def layanan_toggle(id):
    """Toggle active status"""
    try:
        layanan = Layanan.query.get_or_404(id)
        layanan.is_active = not layanan.is_active
        db.session.commit()
        
        status = "diaktifkan" if layanan.is_active else "dinonaktifkan"
        flash(f'Layanan "{layanan.judul}" berhasil {status}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('layanan.layanan_list'))


# ============================================
# API Endpoints for AJAX
# ============================================

@layanan_bp.route('/api/kategori/<int:id>')
@login_required
def api_kategori_detail(id):
    """Get kategori detail as JSON"""
    kategori = Kategori.query.get_or_404(id)
    return jsonify({
        'id': kategori.id,
        'kode': kategori.kode,
        'nama': kategori.nama,
        'icon': kategori.icon,
        'urutan': kategori.urutan,
        'is_active': kategori.is_active,
        'layanan_count': kategori.layanan.count()
    })


@layanan_bp.route('/api/layanan/<int:id>')
@login_required
def api_layanan_detail(id):
    """Get layanan detail as JSON"""
    layanan = Layanan.query.get_or_404(id)
    return jsonify({
        'id': layanan.id,
        'layanan_id': layanan.layanan_id,
        'kategori': layanan.kategori.nama,
        'judul': layanan.judul,
        'jangka_waktu': layanan.jangka_waktu,
        'biaya': layanan.biaya,
        'qrcode': layanan.qrcode,
        'persyaratan': [p.teks for p in layanan.persyaratan.order_by(Persyaratan.urutan).all()],
        'sop': [s.teks for s in layanan.sop.order_by(SOP.urutan).all()],
        'is_active': layanan.is_active
    })