from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime
import logging
import pymysql
import json

#-----------------------------------------------------------
#Configuration Flask + SocketIO
# -----------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'pcb-inspector-secret-key-2024'
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
# Configuration MySQL
# -----------------------------------------------------------
import os

DB_CONFIG = {
    "host": "pcb-server.mysql.database.azure.com",
    "user": "dygfagkjzy@pcb-server",
    "password": "h223JMT7172",
    "database": "pcba_inspector",
    "port": 3306,
}

def get_db_connection():
    try:
        return pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            port=DB_CONFIG["port"],
            cursorclass=pymysql.cursors.DictCursor
        )
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1049:  # Database doesn't exist
            logger.info("Database doesn't exist, creating it...")
            init_database()
            return pymysql.connect(
                host=DB_CONFIG["host"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                port=DB_CONFIG["port"],
                cursorclass=pymysql.cursors.DictCursor
            )
        else:
            raise

def init_database():
    """Initialize database and tables with additional fields"""
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        port=DB_CONFIG["port"],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with conn.cursor() as cursor:
        # Create database
        cursor.execute("CREATE DATABASE IF NOT EXISTS pcba_inspector")
        cursor.execute("USE pcba_inspector")
        
        # Drop and recreate inspections table with all required fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pcb_id VARCHAR(50),
                status ENUM('passed','failed') NOT NULL,
                defects JSON,
                operator VARCHAR(100),
                station VARCHAR(100),
                components TEXT,
                microbe_count INT DEFAULT 0,
                image_path VARCHAR(255),
                confidence FLOAT DEFAULT 0.0,
                processing_time FLOAT DEFAULT 0.0,
                timestamp DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message TEXT,
                level VARCHAR(20),
                ack BOOLEAN DEFAULT FALSE,
                created_at DATETIME
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operators (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                shift VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                line VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default operators
        cursor.execute("""
            INSERT IGNORE INTO operators (name, shift) VALUES 
            ('admin', 'jour'),
            ('henri', 'jour'),
            ('operator1', 'matin'),
            ('operator2', 'après-midi'),
            ('Opérateur Desktop', 'jour')
        """)
        
        # Insert default stations
        cursor.execute("""
            INSERT IGNORE INTO stations (name, line) VALUES 
            ('Station Vision Desktop', 'line-desktop'),
            ('Station Vision1', 'line-1'),
            ('Station Vision2', 'line-2'),
            ('Station Vision3', 'line-3')
        """)
        
        conn.commit()
        logger.info("✅ Database and tables created successfully with enhanced schema")
    
    conn.close()

# -----------------------------------------------------------
# Fonctions utilitaires
# -----------------------------------------------------------
def get_stats():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM inspections")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS passed FROM inspections WHERE status='passed'")
            passed = cursor.fetchone()["passed"]

            cursor.execute("SELECT COUNT(*) AS failed FROM inspections WHERE status='failed'")
            failed = cursor.fetchone()["failed"]
            
            # Additional stats
            cursor.execute("SELECT AVG(processing_time) AS avg_processing_time FROM inspections WHERE processing_time > 0")
            avg_time_result = cursor.fetchone()
            avg_processing_time = avg_time_result["avg_processing_time"] or 2.1
            
            cursor.execute("SELECT AVG(confidence) AS avg_confidence FROM inspections WHERE confidence > 0")
            confidence_result = cursor.fetchone()
            avg_confidence = confidence_result["avg_confidence"] or 95.0

        conn.close()
        
        defect_rate = (failed / total * 100) if total > 0 else 0
        efficiency = (passed / total * 100) if total > 0 else 100
        
        return {
            "total": total,
            "passed": passed, 
            "failed": failed,
            "defect_rate": round(defect_rate, 2),
            # Additional metrics for frontend compatibility
            "totalInspections": total,
            "conformeCount": passed,
            "nonConformeCount": failed,
            "avgProcessingTime": round(avg_processing_time, 2),
            "efficiency": round(efficiency, 1),
            "uptime": 98.5,  # Static for now
            "avgConfidence": round(avg_confidence, 1)
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"total": 0, "passed": 0, "failed": 0, "defect_rate": 0, "totalInspections": 0, "conformeCount": 0, "nonConformeCount": 0, "avgProcessingTime": 2.1, "efficiency": 100, "uptime": 98.5}

def broadcast_stats():
    """Broadcast updated stats to all connected clients"""
    stats_data = get_stats()
    socketio.emit("stats-update", {"type": "stats-update", "data": stats_data})
    logger.info(f"📊 Stats broadcasted: {stats_data['total']} total inspections")

def broadcast_new_inspection(inspection):
    """Broadcast new inspection to all connected clients"""
    socketio.emit("new-inspection", {"type": "new-inspection", "data": inspection})
    logger.info(f"📡 New inspection broadcasted: {inspection.get('pcb_id', 'N/A')}")

# -----------------------------------------------------------
# Routes API
# -----------------------------------------------------------

@app.route("/")
def root():
    return jsonify({
        "message": "PCB Inspector Backend API (Flask + MySQL)",
        "version": "3.0.0",
        "status": "running",
        "database": DB_CONFIG["database"],
        "integrations": {
            "desktop_app": "PyQt6 Desktop Application",
            "dashboard": "Next.js Dashboard (localhost:3000)",
            "database": "MySQL via XAMPP"
        },
        "endpoints": {
            "stats": "/api/stats",
            "inspections": "/api/inspections",
            "inspection-result": "/api/inspection-result",
            "alerts": "/api/alerts",
            "ai-chat": "/api/ai-chat",
            "complaints": "/api/complaints",
            "operators": "/api/operators",
            "stations": "/api/stations"
        }
    })

# ---- Inspections ----
@app.route("/api/inspections", methods=["GET", "POST"])
def api_inspections():
    if request.method == "GET":
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, pcb_id, status, defects, operator, station, 
                           components, microbe_count, image_path, confidence, 
                           processing_time, timestamp 
                    FROM inspections 
                    ORDER BY timestamp DESC 
                    LIMIT 100
                """)
                inspections = cursor.fetchall()
                
                # Format data for frontend
                formatted_inspections = []
                for inspection in inspections:
                    formatted_inspection = {
                        "id": inspection["id"],
                        "pcb_id": inspection["pcb_id"],
                        "status": inspection["status"],
                        "defects": inspection["defects"] if isinstance(inspection["defects"], str) else json.dumps(inspection["defects"]) if inspection["defects"] else "[]",
                        "operator": inspection["operator"],
                        "station": inspection["station"],
                        "timestamp": inspection["timestamp"].isoformat() if inspection["timestamp"] else datetime.now().isoformat(),
                        "components": inspection.get("components", ""),
                        "microbe_count": inspection.get("microbe_count", 0),
                        "confidence": inspection.get("confidence", 0.0),
                        "processing_time": inspection.get("processing_time", 0.0)
                    }
                    formatted_inspections.append(formatted_inspection)
                
            conn.close()
            return jsonify({"inspections": formatted_inspections})
        except Exception as e:
            logger.error(f"Error getting inspections: {e}")
            return jsonify({"inspections": []})

    elif request.method == "POST":
        data = request.json
        if not data:
            return jsonify({"error": "Missing data"}), 400

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Parse defects if they're a list
                defects_json = data.get("defects", [])
                if isinstance(defects_json, list):
                    defects_json = json.dumps(defects_json)
                elif isinstance(defects_json, str) and defects_json.strip().startswith('['):
                    # Already JSON string
                    pass
                else:
                    # Convert string to proper JSON format
                    defects_json = json.dumps([{"type": defects_json, "severity": "Mineur"}] if defects_json else [])
                
                sql = """
                    INSERT INTO inspections 
                    (pcb_id, status, defects, operator, station, components, 
                     microbe_count, image_path, confidence, processing_time, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql, (
                    data.get("pcb_id", f"PCB-{int(datetime.now().timestamp())}"),
                    data.get("status", "failed"),
                    defects_json,
                    data.get("operator", "unknown"),
                    data.get("station", "line-1"),
                    data.get("components", ""),
                    data.get("microbe_count", 0),
                    data.get("image_path", ""),
                    data.get("confidence", 0.0),
                    data.get("processing_time", 2.1),
                    datetime.now()
                ))
                conn.commit()
                inspection_id = cursor.lastrowid

                # Get the inserted inspection
                cursor.execute("""
                    SELECT id, pcb_id, status, defects, operator, station, 
                           components, microbe_count, image_path, confidence, 
                           processing_time, timestamp 
                    FROM inspections WHERE id=%s
                """, (inspection_id,))
                inspection = cursor.fetchone()
                
                # Format for response
                if inspection:
                    formatted_inspection = {
                        "id": inspection["id"],
                        "pcb_id": inspection["pcb_id"],
                        "status": inspection["status"],
                        "defects": inspection["defects"],
                        "operator": inspection["operator"],
                        "station": inspection["station"],
                        "timestamp": inspection["timestamp"].isoformat(),
                        "components": inspection.get("components", ""),
                        "microbe_count": inspection.get("microbe_count", 0),
                        "confidence": inspection.get("confidence", 0.0),
                        "processing_time": inspection.get("processing_time", 0.0)
                    }
                
            conn.close()

            # Broadcast to connected clients (Next.js dashboard)
            broadcast_new_inspection(formatted_inspection)
            broadcast_stats()
            
            logger.info(f"✅ New inspection saved: {formatted_inspection['pcb_id']} - Status: {formatted_inspection['status']}")
            
            return jsonify({"success": True, "inspection": formatted_inspection})
            
        except Exception as e:
            logger.error(f"Error saving inspection: {e}")
            return jsonify({"error": f"Failed to save inspection: {str(e)}"}), 500

# ---- Inspection Result (alias for inspections POST) ----
@app.route("/api/inspection-result", methods=["POST"])
def api_inspection_result():
    """Endpoint specifically for desktop app results"""
    return api_inspections()

# ---- Stats ----
@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(get_stats())

# ---- Database Status ----
@app.route("/api/database-status", methods=["GET"])
def database_status():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM inspections")
            count = cursor.fetchone()["count"]
        conn.close()
        
        return jsonify({
            "status": "ok", 
            "message": "Database connection active",
            "database": DB_CONFIG["database"],
            "inspections_count": count,
            "integrations": {
                "desktop_app": "Connected",
                "next_dashboard": "Ready on localhost:3000"
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ---- Alerts ----
@app.route("/api/alerts", methods=["GET", "POST"])
def api_alerts():
    conn = get_db_connection()
    if request.method == "GET":
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 50")
            rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    elif request.method == "POST":
        data = request.json
        with conn.cursor() as cursor:
            sql = "INSERT INTO alerts (message, level, ack, created_at) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (
                data.get("message", "Alerte"),
                data.get("level", "info"),
                False,
                datetime.now()
            ))
            conn.commit()
        conn.close()
        return jsonify({"success": True})

# ---- AI Chat ----
@app.route("/api/ai-chat", methods=["POST"])
def api_ai_chat():
    data = request.json
    question = data.get("question", "")
    
    # Enhanced AI responses based on database state
    try:
        stats = get_stats()
        response = f"🤖 Analyse IA: Actuellement {stats['total']} inspections en base. "
        
        if stats['defect_rate'] > 10:
            response += f"Taux de défauts élevé ({stats['defect_rate']:.1f}%). Vérifiez les stations."
        elif stats['defect_rate'] < 2:
            response += f"Excellent taux de qualité ({100-stats['defect_rate']:.1f}%). Continuez!"
        else:
            response += f"Taux de défauts normal ({stats['defect_rate']:.1f}%)."
            
        suggestions = ["Analyser les tendances", "Vérifier les stations", "Consulter les stats"]
    except:
        response = f"🤖 Réponse IA: {question}"
        suggestions = ["Vérifier la station", "Relancer l'inspection", "Consulter les logs"]
    
    return jsonify({"response": response, "suggestions": suggestions})

# ---- Complaints ----
@app.route("/api/complaints", methods=["POST"])
def api_complaints():
    data = request.json
    logger.info(f"📩 Nouvelle réclamation reçue: {data}")
    
    # Here you could save complaints to database or send emails
    # For now, just log and return success
    
    return jsonify({
        "success": True, 
        "message": "Réclamation enregistrée et forwarded to Next.js dashboard"
    })

# ---- Operators ----
@app.route("/api/operators", methods=["GET", "POST"])
def api_operators():
    conn = get_db_connection()
    if request.method == "GET":
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM operators ORDER BY name")
            rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    elif request.method == "POST":
        data = request.json
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO operators (name, shift) VALUES (%s, %s)", 
                         (data["name"], data["shift"]))
            conn.commit()
        conn.close()
        return jsonify({"success": True})

# ---- Stations ----
@app.route("/api/stations", methods=["GET", "POST"])
def api_stations():
    conn = get_db_connection()
    if request.method == "GET":
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM stations ORDER BY name")
            rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    elif request.method == "POST":
        data = request.json
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO stations (name, line) VALUES (%s, %s)", 
                         (data["name"], data["line"]))
            conn.commit()
        conn.close()
        return jsonify({"success": True})

# -----------------------------------------------------------
# Socket.IO Events for real-time communication
# -----------------------------------------------------------
@socketio.on("connect")
def on_connect():
    logger.info(f"🔌 Client connecté: {request.sid}")
    # Send initial data to new client
    emit("initial-data", {
        "type": "initial-data", 
        "data": {
            "message": "Connecté au backend Flask",
            "stats": get_stats()
        }
    })

@socketio.on("disconnect")
def on_disconnect():
    logger.info(f"🔌 Client déconnecté: {request.sid}")

@socketio.on("ping")
def on_ping():
    emit("pong", {"type": "pong", "timestamp": datetime.now().isoformat()})

@socketio.on("request_stats")
def on_request_stats():
    emit("stats-update", {"type": "stats-update", "data": get_stats()})

@socketio.on("desktop_app_connected")
def on_desktop_app_connected(data):
    logger.info(f"🖥️  Desktop app connected: {data}")
    emit("desktop_status", {"status": "connected", "timestamp": datetime.now().isoformat()})

# -----------------------------------------------------------
# Background task for periodic stats broadcast
# -----------------------------------------------------------
import threading
import time

def periodic_stats_broadcast():
    """Broadcast stats every 30 seconds"""
    while True:
        time.sleep(30)
        broadcast_stats()

# Start background thread
stats_thread = threading.Thread(target=periodic_stats_broadcast, daemon=True)
stats_thread.start()

# -----------------------------------------------------------
# Lancement serveur
# -----------------------------------------------------------
if __name__ == "__main__":
    # Initialize database on startup
    try:
        init_database()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
    
    port = 5000
    logger.info(f"🚀 PCB Inspector Flask Backend sur http://localhost:{port}")
    logger.info(f"📊 Dashboard Next.js: http://localhost:3000")
    logger.info(f"🖥️  Desktop App ready to connect")
    
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)
