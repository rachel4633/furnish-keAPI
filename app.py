from flask import *
from flask_cors import CORS
import pymysql
import requests
from datetime import datetime  # CHANGED: Fixed typo from 'datatime' to 'datetime'
import base64
import json

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]

}})  # Allow CORS for all API routes

# Handle OPTIONS preflight for all routes
@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
# ═══════════════════════════════════════════
# M-PESA DARAJA CONFIGURATION
# Get these from https://developer.safaricom.co.ke
# ═══════════════════════════════════════════
MPESA_CONSUMER_KEY = "H6qZA1X2g4LQjLbKRfAui2MFeFA33fUUfpmdb8xekedt4vHK"  # Replace with your key
MPESA_CONSUMER_SECRET = "KAeN9yDs4uJ5yYtpAfuAR6dM0Y2G9FY5JKKQxxmceDRMkkRhzsZHYMmMQXwUEkxm"  # Replace with your secret
MPESA_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919
"  
MPESA_SHORTCODE = "174379"  # Test shortcode (replace with your business shortcode)
MPESA_CALLBACK_URL = "https://furnish-ke-api.com/api/payment/callback"  # Replace with your callback URL

# ═══════════════════════════════════════════
# DATABASE CONNECTION — Railway MySQL
# Think of this as the phone line to our database
# Every time we need data we open, use, then close it
# ═══════════════════════════════════════════
def get_db_connection():
    return pymysql.connect(
        host="zephyr.proxy.rlwy.net",
        port=13142,
        user="root",
        password="yZoJFhpqzVHJrsxOWggXsvoiLoVmjJBl",
        database="railway",
        cursorclass=pymysql.cursors.DictCursor
    )

# ═══════════════════════════════════════════
# HELPER — CHECK IF USER IS ADMIN
# Security guard that checks role before
# allowing add/edit/delete on products
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
# HELPER — GET M-PESA ACCESS TOKEN
# Daraja API requires authentication token
# ═══════════════════════════════════════════
def get_mpesa_token():
    try:
        auth_string = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            return None
    except Exception as e:
        print(f"Error getting token: {str(e)}")
        return None

# ═══════════════════════════════════════════
# SIGN UP
# New customers register here
# Everyone gets role = 'customer' by default
# ═══════════════════════════════════════════
@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")

        connection = get_db_connection()
        cursor = connection.cursor()
        sql = """INSERT INTO furniture_users 
                 (username, email, password, phone, role) 
                 VALUES (%s, %s, %s, %s, 'customer')"""
        cursor.execute(sql, (username, email, password, phone))
        connection.commit()
        connection.close()

        return jsonify({
            "message": "Account created successfully!",
            "status": "success"
        })
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

# ═══════════════════════════════════════════
# SIGN IN
# Returns user info including role
# Frontend uses role to show/hide admin panel
# ═══════════════════════════════════════════
@app.route("/api/signin", methods=["POST"])
def signin():
    try:
        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM furniture_users WHERE email = %s AND password = %s",
            (email, password)
        )
        user = cursor.fetchone()
        connection.close()

        if user:
            return jsonify({
                "message": "Login successful",
                "status": "success",
                "user": {
                    "id": user['id'],
                    "username": user['username'],
                    "email": user['email'],
                    "phone": user['phone'],
                    "role": user['role'],
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
# Anyone can see products — no admin check
# Used on the Shop page
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
# Used on Product Detail page
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
# ADD PRODUCT — ADMIN ONLY
# Only admin can add new furniture
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

        name = request.form.get("name")
        price = request.form.get("price")
        category = request.form.get("category")
        image = request.form.get("image")
        description = request.form.get("description")
        material = request.form.get("material")
        dimensions = request.form.get("dimensions")

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
# EDIT PRODUCT — ADMIN ONLY
# Admin can update any product details
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

        name = request.form.get("name")
        price = request.form.get("price")
        category = request.form.get("category")
        image = request.form.get("image")
        description = request.form.get("description")
        material = request.form.get("material")
        dimensions = request.form.get("dimensions")

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
# DELETE PRODUCT — ADMIN ONLY
# Admin can permanently remove a product
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

# ═══════════════════════════════════════════
# INITIATE M-PESA STK PUSH PAYMENT
# This sends M-Pesa prompt to user's phone
# ═══════════════════════════════════════════
@app.route("/api/payment/mpesa", methods=["POST"])
def initiate_mpesa_payment():
    try:
        data = request.get_json()
        phone = data.get('phone')
        amount = int(data.get('amount'))
        account_ref = data.get('accountReference')
        description = data.get('description')
        user_id = data.get('userId')
        items = data.get('items', [])

        # Validate inputs
        if not phone or not amount or amount < 1:
            return jsonify({
                "status": "error",
                "message": "Invalid phone or amount"
            }), 400

        # Get access token
        access_token = get_mpesa_token()
        if not access_token:
            return jsonify({
                "status": "error",
                "message": "Failed to authenticate with M-Pesa. Check your Daraja credentials."
            }), 500

        # Prepare STK Push request
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_string = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": account_ref,
            "TransactionDesc": description
        }

        # Send STK Push request
        response = requests.post(
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
            timeout=10
        )

        response_data = response.json()

        # Save order to database (for tracking)
        if response_data.get('ResponseCode') == '0':
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Create orders table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    user_id VARCHAR(50),
                    phone VARCHAR(20),
                    amount DECIMAL(10, 2),
                    account_reference VARCHAR(100),
                    checkout_request_id VARCHAR(200),
                    status VARCHAR(50) DEFAULT 'pending',
                    items JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            sql = """INSERT INTO orders 
                     (user_id, phone, amount, account_reference, checkout_request_id, items)
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            
            cursor.execute(sql, (
                user_id,
                phone,
                amount,
                account_ref,
                response_data.get('CheckoutRequestID', ''),
                json.dumps(items)
            ))
            
            connection.commit()
            connection.close()

        return jsonify({
            "status": "success",
            "message": "M-Pesa prompt sent to your phone",
            "ResponseCode": response_data.get('ResponseCode'),
            "CheckoutRequestID": response_data.get('CheckoutRequestID', '')
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ═══════════════════════════════════════════
# M-PESA CALLBACK (For webhook - optional)
# Safaricom sends payment confirmation here
# ═══════════════════════════════════════════
@app.route("/api/payment/callback", methods=["POST"])
def mpesa_callback():
    try:
        data = request.get_json()
        callback_data = data.get('Body', {}).get('stkCallback', {})
        
        result_code = callback_data.get('ResultCode')
        checkout_request_id = callback_data.get('CheckoutRequestID')
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if result_code == 0:  # Payment successful
            cursor.execute(
                "UPDATE orders SET status = 'completed' WHERE checkout_request_id = %s",
                (checkout_request_id,)
            )
        else:  # Payment failed
            cursor.execute(
                "UPDATE orders SET status = 'failed' WHERE checkout_request_id = %s",
                (checkout_request_id,)
            )
        
        connection.commit()
        connection.close()
        
        return jsonify({"ResultCode": 0})
    except Exception as e:
        print(f"Callback error: {str(e)}")
        return jsonify({"ResultCode": 1}), 500

# ═══════════════════════════════════════════
# CHECK PAYMENT STATUS (Optional)
# Frontend can check if payment went through
# ═══════════════════════════════════════════
@app.route("/api/payment/status/<reference>", methods=["GET"])
def check_payment_status(reference):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM orders WHERE account_reference = %s",
            (reference,)
        )
        order = cursor.fetchone()
        connection.close()
        
        if order:
            return jsonify({
                "status": order['status'],
                "reference": reference,
                "amount": order['amount'],
                "phone": order['phone']
            })
        else:
            return jsonify({
                "status": "not_found",
                "message": "Order not found"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
