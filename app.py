from flask import *
from flask_cors import CORS
import pymysql
from datetime import datetime
import os
import bcrypt  # Make sure bcrypt is installed in your environment

app = Flask(__name__)

# Allowed frontend origins
ALLOWED_ORIGINS = ["https://youngdigitalfurniture.co.ke", 
                    "https://www.youngdigitalfurniture.co.ke",
                    "http://localhost:5173"]

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        
        # Dynamically mirror the origin if it's in your allowed list
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            response.headers["Access-Control-Allow-Origin"] = "https://youngdigitalfurniture.co.ke"

        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

# ═══════════════════════════════════════════
# DATABASE CONNECTION (WITH RESILIENT FALLBACKS)
# ═══════════════════════════════════════════
def get_db_connection():
    try:
        # Get values from environment variables, or fallback to standard MySQL defaults
        db_host = os.environ.get("DB_HOST") or "localhost"
        
        # Safe integer parsing for the database port
        raw_port = os.environ.get("DB_PORT")
        db_port = int(raw_port) if raw_port and raw_port.isdigit() else 3306
        
        db_user = os.environ.get("DB_USER") or "root"
        db_pass = os.environ.get("DB_PASSWORD") or ""
        db_name = os.environ.get("DB_NAME") or "furniture_db"

        return pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_pass,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10  # Stops the server from hanging forever if Railway goes down
        )
    except Exception as db_err:
        print(f"DATABASE CONNECTION ERROR DETAILS: {str(db_err)}")
        raise db_err

# ═══════════════════════════════════════════
# HELPER CHECK IF USER IS ADMIN
# ═══════════════════════════════════════════
def is_admin(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT role FROM furniture_users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        connection.close()
        return user and user['role'] == 'admin'
    except:
        return False

# ═══════════════════════════════════════════
# SIGN UP 
# ═══════════════════════════════════════════
@app.route("/api/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return handle_options()
        
    try:
        username = request.form.get("username")
        email    = request.form.get("email")
        password = request.form.get("password")
        phone    = request.form.get("phone")

        if not username or not email or not password:
            return jsonify({"message": "Missing required fields", "status": "error"}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if username OR email already exists to prevent database crashes
        cursor.execute(
            "SELECT id FROM furniture_users WHERE username = %s OR email = %s", 
            (username, email)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            connection.close()
            return jsonify({
                "message": "Username or Email already exists. Please choose a different one.",
                "status": "error"
            }), 400

        # Hash password securely
        hashed = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        sql = """INSERT INTO furniture_users 
                 (username, email, password, phone, role) 
                 VALUES (%s, %s, %s, %s, 'customer')"""
        cursor.execute(sql, (username, email, hashed, phone))
        inserted_id = cursor.lastrowid
        connection.commit()
        connection.close()

        return jsonify({
            "message": "Account created successfully!",
            "status": "success",
            "user": {
                "id": inserted_id,
                "username": username,
                "email": email,
                "phone": phone,
                "role": "customer"
            }
        })
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# SIGN IN
# ═══════════════════════════════════════════
@app.route("/api/signin", methods=["POST", "OPTIONS"])
def signin():
    if request.method == "OPTIONS":
        return handle_options()

    try:
        email    = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM furniture_users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        connection.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({
                "message": "Login successful",
                "status": "success",
                "user": {
                    "id":       user['id'],
                    "username": user['username'],
                    "email":    user['email'],
                    "phone":    user['phone'],
                    "role":     user['role'],
                }
            })
        else:
            return jsonify({
                "message": "Invalid email or password",
                "status": "error"
            }), 401
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# GET ALL PRODUCTS
# ═══════════════════════════════════════════
@app.route("/api/products", methods=["GET"])
def get_products():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM furniture_products ORDER BY created_at DESC")
        products = cursor.fetchall()
        connection.close()
        return jsonify(products)
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# GET SINGLE PRODUCT
# ═══════════════════════════════════════════
@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM furniture_products WHERE id = %s",
            (product_id,)
        )
        product = cursor.fetchone()
        connection.close()

        if product:
            return jsonify(product)
        else:
            return jsonify({
                "message": "Product not found",
                "status": "error"
            }), 404
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# ADD PRODUCT (ADMIN ONLY)
# ═══════════════════════════════════════════
@app.route("/api/products", methods=["POST"])
def add_product():
    try:
        user_id = request.form.get("user_id")
        if not is_admin(user_id):
            return jsonify({
                "message": "Access denied. Admins only.",
                "status": "error"
            }), 403

        name        = request.form.get("name")
        price       = request.form.get("price")
        category    = request.form.get("category")
        image       = request.form.get("image")
        description = request.form.get("description")
        material    = request.form.get("material")
        dimensions  = request.form.get("dimensions")

        connection = get_db_connection()
        cursor = connection.cursor()
        sql = """INSERT INTO furniture_products
                 (name, price, category, image, description, material, dimensions)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (name, price, category, image, description, material, dimensions))
        connection.commit()
        new_id = cursor.lastrowid
        connection.close()

        return jsonify({
            "message": "Product added successfully",
            "status": "success",
            "product_id": new_id
        })
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# EDIT PRODUCT (ADMIN ONLY)
# ═══════════════════════════════════════════
@app.route("/api/products/<int:product_id>", methods=["PUT"])
def edit_product(product_id):
    try:
        user_id = request.form.get("user_id")
        if not is_admin(user_id):
            return jsonify({
                "message": "Access denied. Admins only.",
                "status": "error"
            }), 403

        name        = request.form.get("name")
        price       = request.form.get("price")
        category    = request.form.get("category")
        image       = request.form.get("image")
        description = request.form.get("description")
        material    = request.form.get("material")
        dimensions  = request.form.get("dimensions")

        connection = get_db_connection()
        cursor = connection.cursor()
        sql = """UPDATE furniture_products SET
                 name = %s, price = %s, category = %s,
                 image = %s, description = %s,
                 material = %s, dimensions = %s
                 WHERE id = %s"""
        cursor.execute(sql, (name, price, category, image,
                             description, material, dimensions, product_id))
        connection.commit()
        connection.close()

        return jsonify({
            "message": "Product updated successfully",
            "status": "success"
        })
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# DELETE PRODUCT (ADMIN ONLY)
# ═══════════════════════════════════════════
@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    try:
        user_id = request.form.get("user_id")
        if not is_admin(user_id):
            return jsonify({
                "message": "Access denied. Admins only.",
                "status": "error"
            }), 403

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM furniture_products WHERE id = %s",
            (product_id,)
        )
        connection.commit()
        connection.close()

        return jsonify({
            "message": "Product deleted successfully",
            "status": "success"
        })
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

if __name__ == "__main__":
    app.run(debug=True)