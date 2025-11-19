from flask import Flask, request, jsonify
import requests
import json
import os
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from models import (
    db,
    User,
    Message,
    UserSession,
    AdminUser,
    Kategori,
    Layanan,
    Persyaratan,
    SOP,
)
import time
from dotenv import load_dotenv
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate

# ✅ IMPORT FLASK-LOGIN
from flask_login import LoginManager, current_user, login_required

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Config
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "whatsapp_bot_kemenag")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Build MySQL connection string
if os.getenv("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        "?charset=utf8mb4"
    )

# ✅ INISIALISASI FLASK-LOGIN
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin.login'  # route untuk login
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'

# ✅ USER LOADER untuk Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# inisialisasi SQLAlchemy dengan Flask app
db.init_app(app)
migrate = Migrate(app, db)

# ✅ Context processor SETELAH app didefinisikan
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# Register blueprints setelah db di-init
from routes.admin import admin_bp
from routes.layanan_routes import layanan_bp
from routes.admin_management import admin_mgmt_bp

# Register blueprint
app.register_blueprint(admin_mgmt_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(layanan_bp)

# WhatsApp Config
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "your_verify_token_123")
WHATSAPP_API_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"


# ============================================
# HELPER: Load Data from MySQL
# ============================================


def get_kategori_data():
    """Get all kategori from database"""
    kategoris = Kategori.query.filter_by(is_active=True).order_by(Kategori.urutan).all()

    result = {}
    for kat in kategoris:
        result[kat.kode] = {
            "nama": kat.nama,
            "icon": kat.icon,
            "layanan": [
                lay.to_dict()
                for lay in kat.layanan.filter_by(is_active=True)
                .order_by(Layanan.urutan)
                .all()
            ],
        }

    return result


def get_link_video():
    """Get link video from settings"""
    setting = Settings.query.filter_by(key="link_video_youtube").first()
    return setting.value if setting else ""


def find_layanan_by_id(layanan_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Cari layanan berdasarkan ID"""
    layanan = Layanan.query.filter_by(layanan_id=layanan_id, is_active=True).first()

    if layanan:
        return layanan.to_dict(), layanan.kategori.kode

    return None, None


# ============================================
# Database Helper Functions
# ============================================


def get_or_create_user(phone_number: str) -> User:
    """Get atau create user di database"""
    user = User.query.filter_by(phone_number=phone_number).first()

    if not user:
        user = User(phone_number=phone_number)
        db.session.add(user)
        db.session.commit()
        logger.info(f"✨ New user created: {phone_number}")

    user.last_interaction = datetime.utcnow()
    user.total_messages += 1
    db.session.commit()

    return user


def save_message(
    user: User,
    message_id: str,
    direction: str,
    message_type: str,
    content: str = None,
    service_type: str = None,
    status: str = "sent",
):
    """Save message ke database"""
    try:
        msg = Message(
            message_id=message_id,
            user_id=user.id,
            direction=direction,
            message_type=message_type,
            content=content,
            service_type=service_type,
            status=status,
        )
        db.session.add(msg)
        db.session.commit()
        logger.info(f"💾 Message saved: {message_id}")
    except Exception as e:
        logger.error(f"❌ Error saving message: {e}")
        db.session.rollback()


def update_session(user: User, category: str = None, layanan_id: str = None):
    """Update user session"""
    try:
        session_obj = UserSession.query.filter_by(user_id=user.id).first()

        if not session_obj:
            session_obj = UserSession(user_id=user.id)
            db.session.add(session_obj)

        if category:
            session_obj.current_category = category
        if layanan_id:
            session_obj.last_interaction = layanan_id

        session_obj.updated_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        logger.error(f"❌ Error updating session: {e}")
        db.session.rollback()


def send_whatsapp_message(to: str, payload: Dict) -> Optional[Dict]:
    """Kirim pesan WhatsApp dan save ke database"""
    try:
        if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
            logger.error("❌ Token atau Phone ID tidak diset!")
            return None

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }

        data = {"messaging_product": "whatsapp", "to": to, **payload}

        response = requests.post(
            WHATSAPP_API_URL, headers=headers, json=data, timeout=10
        )
        response.raise_for_status()
        result = response.json()

        user = get_or_create_user(to)
        message_id = result.get("messages", [{}])[0].get("id", "unknown")

        content = None
        if payload.get("type") == "text":
            content = payload.get("text", {}).get("body")
        elif payload.get("type") == "interactive":
            interactive = payload.get("interactive", {})
            content = interactive.get("body", {}).get("text")

        save_message(user, message_id, "outgoing", payload.get("type"), content)

        logger.info(f"✅ Message sent to {to}")
        return result

    except Exception as e:
        logger.error(f"❌ Error sending: {e}")
        return None


# ============================================
# WhatsApp Message Builders
# ============================================


def get_menu_utama() -> Dict:
    """Generate menu utama dari database MySQL tanpa pengelompokan"""
    
    KATEGORI_DATA = get_kategori_data()
    
    # Buat list rows dari semua kategori
    rows = []
    for kat_key, kat_data in KATEGORI_DATA.items():
        rows.append(
            {
                "id": f"kat_{kat_key}",
                "title": f"{kat_data['icon']} {kat_data['nama']}",
            }
        )
    
    # Sort berdasarkan urutan (jika ada) atau nama
    # Anda bisa menyesuaikan sorting sesuai kebutuhan
    
    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "Kemenag Kab. Madiun"},
            "body": {
                "text": "Assalamualaikum! Selamat datang di layanan informasi Kemenag Kabupaten Madiun.\n\nSilakan pilih kategori layanan:"
            },
            "footer": {"text": "PTSP Kemenag Kab. Madiun"},
            "action": {
                "button": "Pilih Kategori", 
                "sections": [
                    {
                        "title": "Kategori Layanan",
                        "rows": rows
                    }
                ]
            },
        },
    }

def get_daftar_layanan(kategori_id: str) -> Dict:
    """Generate daftar layanan per kategori dari database"""
    try:
        kategori_key = kategori_id.replace("kat_", "")

        # Get from database
        kategori = Kategori.query.filter_by(kode=kategori_key, is_active=True).first()

        if not kategori:
            logger.warning(f"⚠️ Kategori {kategori_key} tidak ditemukan")
            return get_menu_utama()

        layanan_list = (
            kategori.layanan.filter_by(is_active=True)
            .order_by(Layanan.urutan)
            .limit(10)
            .all()
        )

        rows = []
        for layanan in layanan_list:
            judul = layanan.judul
            rows.append(
                {
                    "id": layanan.layanan_id,
                    "title": judul[:24],
                    "description": (
                        judul[24:72] if len(judul) > 24 else "Klik untuk detail"
                    ),
                }
            )

        if not rows:
            rows.append(
                {
                    "id": "none",
                    "title": "Tidak ada layanan",
                    "description": "Belum ada layanan tersedia",
                }
            )

        return {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": f"{kategori.icon} {kategori.nama}",
                },
                "body": {
                    "text": "Pilih layanan yang Anda butuhkan untuk melihat persyaratan dan prosedur:"
                },
                "footer": {"text": "PTSP Kemenag Kab. Madiun"},
                "action": {
                    "button": "Pilih Layanan",
                    "sections": [{"title": "Layanan Tersedia", "rows": rows}],
                },
            },
        }
    except Exception as e:
        logger.error(f"❌ Error get_daftar_layanan: {e}")
        return get_menu_utama()


def get_detail_layanan(layanan_id: str) -> Dict:
    """Generate detail layanan berdasarkan ID dari database"""
    try:
        layanan, kategori_key = find_layanan_by_id(layanan_id)

        if not layanan:
            logger.warning(f"⚠️ Layanan {layanan_id} tidak ditemukan")
            return get_menu_utama()

        body_text = f"*{layanan.get('judul', '')}*\n\n"
        body_text += "*📋 PERSYARATAN:*\n"

        persyaratan = layanan.get("PERSYARATAN", [])
        for i, req in enumerate(persyaratan[:5], 1):
            body_text += f"{i}. {req[:100]}\n"

        if len(persyaratan) > 5:
            body_text += f"... dan {len(persyaratan) - 5} persyaratan lainnya\n"

        body_text += f"\n*⏱️ WAKTU:* {layanan.get('Jangka Waktu Pelayanan', '-')}\n"
        body_text += f"*💰 BIAYA:* {layanan.get('Biaya/Tarif', '-')}\n"

        if "qrcode" in layanan and layanan["qrcode"]:
            body_text += f"\n*🔗 Link Pendukung:*\n{layanan['qrcode']}\n"

        LINK_VIDEO = get_link_video()
        if LINK_VIDEO:
            body_text += f"\n📹 Tutorial: {LINK_VIDEO}"

        # Batasi panjang
        body_text = body_text[:1024]

        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "footer": {"text": "PTSP Kemenag Kab. Madiun"},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": f"btn_sop_{layanan_id}",
                                "title": "📄 Lihat SOP",
                            },
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": f"btn_back_{kategori_key}",
                                "title": "⬅️ Kembali",
                            },
                        },
                        {
                            "type": "reply",
                            "reply": {"id": "btn_menu", "title": "🏠 Menu"},
                        },
                    ]
                },
            },
        }
    except Exception as e:
        logger.error(f"❌ Error get_detail_layanan: {e}")
        import traceback

        traceback.print_exc()
        return get_menu_utama()


def get_detail_sop(layanan_id: str) -> Dict:
    """Generate detail SOP berdasarkan ID dari database"""
    try:
        layanan, _ = find_layanan_by_id(layanan_id)

        if not layanan:
            return {"type": "text", "text": {"body": "SOP tidak ditemukan"}}

        body_text = f"*ALUR SOP*\n{layanan.get('judul', '')[:50]}...\n\n"

        sop = layanan.get("SOP", [])
        if sop:
            for i, step in enumerate(sop[:10], 1):
                body_text += f"*Langkah {i}:*\n{step[:150]}\n\n"
        else:
            body_text += "SOP untuk layanan ini sedang dalam proses penyusunan.\n\n"

        body_text += f"*⏱️ Total Waktu:* {layanan.get('Jangka Waktu Pelayanan', '-')}\n"
        body_text += f"*💰 Biaya:* {layanan.get('Biaya/Tarif', '-')}"

        body_text = body_text[:4096]

        return {"type": "text", "text": {"body": body_text}}
    except Exception as e:
        logger.error(f"❌ Error get_detail_sop: {e}")
        return {"type": "text", "text": {"body": "Error mengambil SOP"}}


def get_button_wa_lain() -> Dict:
    """Pesan teks untuk hubungi admin"""
    return {
        "type": "text",
        "text": {
            "body": f"*Ingin langsung menghubungi admin?*\n\nKlik tautan di bawah untuk menghubungi kami melalui WhatsApp:\nhttps://wa.me/6282245552687?text=Assalamualaikum,%20saya%20butuh%20bantuan\n\nTim support kami siap membantu Anda sesuai jam pelayanan 🙏"
        },
    }


def handle_message(message: Dict, from_number: str):
    """Handle incoming message"""
    try:
        message_type = message.get("type")
        message_id = message.get("id")

        user = get_or_create_user(from_number)

        content = None
        if message_type == "text":
            content = message.get("text", {}).get("body")

        save_message(user, message_id, "incoming", message_type, content)

        valid_types = ["text", "interactive"]
        if message_type not in valid_types:
            logger.info(f"⏭️ Skipping message type: {message_type}")
            return

        logger.info(f"📨 Processing {message_type} from {from_number}")

        if message_type == "text":
            text = content.lower() if content else ""
            logger.info(f"💬 Text: {text}")

            if any(word in text for word in ["halo", "hi", "menu", "mulai", "start"]):
                send_whatsapp_message(from_number, get_menu_utama())
                time.sleep(1)
                send_whatsapp_message(from_number, get_button_wa_lain())
                update_session(user)
            else:
                send_whatsapp_message(
                    from_number,
                    {
                        "type": "text",
                        "text": {
                            "body": "Ketik *menu* untuk melihat layanan yang tersedia."
                        },
                    },
                )

        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            response_id = interactive.get("list_reply", {}).get(
                "id"
            ) or interactive.get("button_reply", {}).get("id")

            if not response_id:
                logger.warning("⚠️ No response_id found")
                return

            logger.info(f"🔘 Button/List clicked: {response_id}")

            if response_id.startswith("kat_"):
                kategori_key = response_id.replace("kat_", "")
                send_whatsapp_message(from_number, get_daftar_layanan(response_id))
                update_session(user, category=kategori_key)

            elif any(
                response_id.startswith(prefix)
                for prefix in [
                    "kepeg_",
                    "umum_",
                    "pendidikan_",
                    "pontren_",
                    "haji_",
                    "zakat_",
                    "bimas_",
                    "konsultasi_",
                ]
            ):
                send_whatsapp_message(from_number, get_detail_layanan(response_id))
                update_session(user, layanan_id=response_id)

                _, kategori_key = find_layanan_by_id(response_id)
                if kategori_key:
                    save_message(
                        user,
                        f"view_{response_id}",
                        "outgoing",
                        "interactive",
                        service_type=kategori_key,
                        status="viewed",
                    )

            elif response_id.startswith("btn_sop_"):
                layanan_id = response_id.replace("btn_sop_", "")
                send_whatsapp_message(from_number, get_detail_sop(layanan_id))

            elif response_id.startswith("btn_back_"):
                kategori_key = response_id.replace("btn_back_", "")
                send_whatsapp_message(
                    from_number, get_daftar_layanan(f"kat_{kategori_key}")
                )

            elif response_id == "btn_menu":
                send_whatsapp_message(from_number, get_menu_utama())
                time.sleep(1)
                send_whatsapp_message(from_number, get_button_wa_lain())
                update_session(user)

            elif response_id == "none":
                send_whatsapp_message(
                    from_number,
                    {
                        "type": "text",
                        "text": {
                            "body": "Maaf, belum ada layanan tersedia untuk kategori ini. Ketik *menu* untuk kembali."
                        },
                    },
                )

    except Exception as e:
        logger.error(f"❌ Error handling message: {e}")
        import traceback

        traceback.print_exc()


# ============================================
# Flask Routes
# ============================================


@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """Verify webhook"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    logger.info(f"🔍 Verification request - Token: {token}")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified!")
        return challenge, 200
    else:
        logger.warning("❌ Verification failed!")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_handler():
    """Handle incoming webhooks"""
    try:
        body = request.get_json()
        logger.debug(f"📥 Webhook: {json.dumps(body, indent=2)}")

        if body.get("object") != "whatsapp_business_account":
            return jsonify({"status": "ignored"}), 200

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                if "statuses" in value:
                    logger.info("ℹ️ Status update (ignored)")
                    continue

                if "messages" not in value:
                    continue

                messages = value.get("messages", [])

                for message in messages:
                    from_number = message.get("from")
                    message_id = message.get("id")

                    existing = Message.query.filter_by(message_id=message_id).first()
                    if existing:
                        logger.info(f"⏭️ Message {message_id} already processed")
                        continue

                    logger.info(f"✅ New message {message_id} from {from_number}")
                    handle_message(message, from_number)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check"""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    kategori_count = Kategori.query.filter_by(is_active=True).count()
    layanan_count = Layanan.query.filter_by(is_active=True).count()

    return (
        jsonify(
            {
                "status": "healthy",
                "service": "WhatsApp Bot Kemenag Madiun",
                "timestamp": datetime.utcnow().isoformat(),
                "database": db_status,
                "database_type": "MySQL",
                "categories": kategori_count,
                "total_services": layanan_count,
            }
        ),
        200,
    )


@app.route("/send-test", methods=["POST"])
def send_test_message():
    """Test endpoint"""
    data = request.get_json()
    to = data.get("to")

    if not to:
        return jsonify({"error": "Phone number required"}), 400

    result = send_whatsapp_message(to, get_menu_utama())

    if result:
        return jsonify({"status": "success", "result": result}), 200
    else:
        return jsonify({"status": "error"}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found", "message": str(e)}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error", "message": str(e)}), 500


# ============================================
# CLI Commands
# ============================================


@app.cli.command()
def init_db():
    """Initialize database tables"""
    print("=" * 60)
    print("⚠️  WARNING: This will DROP ALL TABLES and data!")
    print("=" * 60)
    confirm = input("Type 'yes' to confirm: ")

    if confirm.lower() != "yes":
        print("❌ Operation cancelled")
        return

    try:
        db.drop_all()
        db.create_all()
        print("✅ Database tables created successfully!")
        print("\nNext steps:")
        print("1. Run 'flask create-admin' to create admin user")
        print("2. Run 'flask import-layanan' to import service data")
    except Exception as e:
        print(f"❌ Error: {e}")


@app.cli.command()
def create_admin():
    """Create admin user"""
    print("=" * 60)
    print("🔐 Creating Admin User")
    print("=" * 60)

    existing_admin = AdminUser.query.first()
    if existing_admin:
        print(f"⚠️  Admin user already exists: {existing_admin.username}")
        overwrite = input("Overwrite? (yes/no): ")
        if overwrite.lower() != "yes":
            print("❌ Operation cancelled")
            return
        db.session.delete(existing_admin)
        db.session.commit()

    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    email = os.getenv("ADMIN_EMAIL", "admin@kemenagmadiun.go.id")

    if not username:
        username = input("Enter admin username: ").strip()
        if not username:
            print("❌ Username cannot be empty")
            return

    if not password:
        import getpass

        password = getpass.getpass("Enter admin password (min 8 chars): ").strip()
        if len(password) < 8:
            print("❌ Password must be at least 8 characters")
            return

        password_confirm = getpass.getpass("Confirm password: ").strip()
        if password != password_confirm:
            print("❌ Passwords do not match")
            return

    try:
        admin = AdminUser(
            username=username,
            password_hash=hash_password(password),
            email=email,
            is_active=True,
        )
        db.session.add(admin)
        db.session.commit()

        print("\n✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")

    except Exception as e:
        print(f"❌ Error creating admin: {e}")
        db.session.rollback()


@app.cli.command()
def import_layanan():
    """Import data layanan dari JSON ke MySQL"""
    from import_layanan import import_layanan_from_json, verify_import

    success = import_layanan_from_json()
    if success:
        verify_import()


@app.cli.command()
def setup():
    """First-time setup: Create tables only"""
    print("=" * 60)
    print("🚀 Database Setup")
    print("=" * 60)

    try:
        db.create_all()
        print("✅ Database tables created!")
        print()
        print("Next steps:")
        print("1. Run: flask create-admin")
        print("2. Run: flask import-layanan")
        print("3. Start app: python app.py")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    with app.app_context():
        try:
            # Create tables if not exist
            db.create_all()
            logger.info("✅ Database tables ready")

            # Check admin
            admin_count = AdminUser.query.count()
            if admin_count == 0:
                logger.warning("⚠️  No admin user found!")
                logger.warning("⚠️  Run 'flask create-admin' to create admin user")

            # Check service data
            kategori_count = Kategori.query.count()
            layanan_count = Layanan.query.count()

            if kategori_count == 0:
                logger.warning("⚠️  No service data found!")
                logger.warning("⚠️  Run 'flask import-layanan' to import data")

        except Exception as e:
            logger.error(f"⚠️  Database init error: {e}")
            kategori_count = 0
            layanan_count = 0

        print("=" * 60)
        print("🚀 WhatsApp Bot Kemenag Madiun - MySQL Version")
        print("=" * 60)
        print(f"📱 WhatsApp Token: {'✅ Set' if WHATSAPP_TOKEN else '❌ Not Set'}")
        print(f"📞 Phone ID: {'✅ Set' if PHONE_NUMBER_ID else '❌ Not Set'}")
        print(f"🗄️  Database: MySQL ({DB_HOST}:{DB_PORT}/{DB_NAME}")

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=True)
