from flask import Flask, render_template, request, redirect, session, jsonify, url_for, flash
import mysql.connector
import os
import time
from threading import Thread
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from decimal import Decimal

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Payment tracking
payment_status_cache = {}

# Upload folder setup
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="technest"
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create tables if they don't exist
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            user_type ENUM('buyer', 'seller') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            image VARCHAR(255),
            seller_id INT NOT NULL,
            category VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Create cart table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE KEY unique_cart_item (user_id, product_id)
        )
    """)
    
    # Create orders table - UPDATED
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            address_id INT,
            payment_status ENUM('pending', 'paid', 'failed') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (address_id) REFERENCES addresses(id) ON DELETE SET NULL
        )
    """)
    
    # Create addresses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            phone VARCHAR(15) NOT NULL,
            address TEXT NOT NULL,
            city VARCHAR(50) NOT NULL,
            state VARCHAR(50) NOT NULL,
            pincode VARCHAR(10) NOT NULL,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

create_tables()

# ------------------- HELPER FUNCTIONS ------------------- #

def verify_payment_and_create_order(payment_id):
    """Simulate payment verification and create order"""
    time.sleep(5)  # Reduced from 30 to 5 seconds for testing
    
    payment_data = payment_status_cache.get(payment_id)
    if not payment_data:
        return

    # In a real app, you would verify with payment gateway here
    payment_data['status'] = 'paid'
    create_order(payment_id)

def create_order(payment_id):
    """Create order after successful payment"""
    payment_data = payment_status_cache.get(payment_id)
    if not payment_data:
        return

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get cart items
        cursor.execute("""
            SELECT c.product_id, c.quantity, CAST(p.price AS DECIMAL(10,2)) as price, p.name, p.image
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        """, (payment_data['user_id'],))
        items = cursor.fetchall()

        # Create orders for each item
        for item in items:
            cursor.execute("""
                INSERT INTO orders (user_id, product_id, quantity, price, address_id, payment_status)
                VALUES (%s, %s, %s, %s, %s, 'paid')
            """, (payment_data['user_id'], item['product_id'], item['quantity'], 
                 item['price'], payment_data['address_id']))

        # Clear cart
        cursor.execute("DELETE FROM cart WHERE user_id = %s", (payment_data['user_id'],))
        conn.commit()
        session['cart_count'] = 0
        
    except Exception as e:
        conn.rollback()
        print(f"Error creating order: {str(e)}")
    finally:
        conn.close()

# ------------------- AUTHENTICATION ROUTES ------------------- #

@app.route('/')
def home():
    if 'user_type' in session:
        if session['user_type'] == 'buyer':
            return redirect(url_for('buyer_home'))
        else:
            return redirect(url_for('seller_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        user_type = request.form['user_type']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, email, user_type) VALUES (%s, %s, %s, %s)",
                         (username, password, email, user_type))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Registration failed: {err.msg}', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password_input):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            return redirect(url_for('buyer_home') if user['user_type'] == 'buyer' else url_for('seller_dashboard'))
        
        flash('Invalid username or password', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))

# ------------------- BUYER ROUTES ------------------- #

@app.route('/buyer')
def buyer_home():
    if 'user_type' not in session or session['user_type'] != 'buyer':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template('buyer_home.html', products=products)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    product_id = request.form.get('product_id')
    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID missing'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if product exists
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Product not found'})
        
        # Check if item already in cart
        cursor.execute("""
            SELECT id, quantity FROM cart 
            WHERE user_id = %s AND product_id = %s
        """, (session['user_id'], product_id))
        existing_item = cursor.fetchone()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item['quantity'] + 1
            cursor.execute("""
                UPDATE cart SET quantity = %s 
                WHERE id = %s
            """, (new_quantity, existing_item['id']))
        else:
            # Add new item
            cursor.execute("""
                INSERT INTO cart (user_id, product_id, quantity)
                VALUES (%s, %s, 1)
            """, (session['user_id'], product_id))
        
        conn.commit()
        
        # Get updated cart count
        cursor.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = %s", (session['user_id'],))
        cart_count = cursor.fetchone()['count'] or 0
        session['cart_count'] = cart_count
        
        return jsonify({
            'success': True,
            'cart_count': cart_count,
            'message': 'Product added to cart'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get cart items with product details
    cursor.execute("""
        SELECT c.id, p.id as product_id, p.name, p.price, p.image, c.quantity 
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = %s
    """, (session['user_id'],))
    items = cursor.fetchall()
    
    # Calculate total price with proper decimal handling
    total_price = Decimal('0.00')
    for item in items:
        total_price += Decimal(str(item['price'])) * Decimal(str(item['quantity']))
    
    # Get cart count for the badge
    cursor.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = %s", (session['user_id'],))
    cart_count = cursor.fetchone()['count'] or 0
    session['cart_count'] = cart_count
    
    conn.close()
    
    return render_template('cart.html', items=items, total_price=float(total_price))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.get_json()
    item_id = data.get('item_id')
    action = data.get('action')
    
    if not item_id or not action:
        return jsonify({'success': False, 'message': 'Missing parameters'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get current quantity
        cursor.execute("""
            SELECT quantity FROM cart 
            WHERE id = %s AND user_id = %s
        """, (item_id, session['user_id']))
        item = cursor.fetchone()
        
        if not item:
            return jsonify({'success': False, 'message': 'Item not found in cart'})
        
        current_quantity = item['quantity']
        new_quantity = current_quantity
        
        # Update quantity based on action
        if action == 'increase':
            new_quantity = current_quantity + 1
        elif action == 'decrease' and current_quantity > 1:
            new_quantity = current_quantity - 1
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})
        
        # Update in database
        cursor.execute("""
            UPDATE cart SET quantity = %s 
            WHERE id = %s
        """, (new_quantity, item_id))
        
        # Get product price for total calculation
        cursor.execute("""
            SELECT CAST(p.price AS DECIMAL(10,2)) as price FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.id = %s
        """, (item_id,))
        price = Decimal(str(cursor.fetchone()['price']))
        
        conn.commit()
        
        # Get updated cart count
        cursor.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = %s", (session['user_id'],))
        cart_count = cursor.fetchone()['count'] or 0
        session['cart_count'] = cart_count
        
        return jsonify({
            'success': True,
            'quantity': new_quantity,
            'total_price': float(price * Decimal(str(new_quantity))),
            'cart_count': cart_count
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/delete_cart_item', methods=['POST'])
def delete_cart_item():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.get_json()
    item_id = data.get('item_id')
    
    if not item_id:
        return jsonify({'success': False, 'message': 'Item ID missing'})

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM cart 
            WHERE id = %s AND user_id = %s
        """, (item_id, session['user_id']))
        
        cursor.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = %s", (session['user_id'],))
        result = cursor.fetchone()
        cart_count = result[0] if result[0] else 0
        session['cart_count'] = cart_count
        
        conn.commit()
        return jsonify({
            'success': True,
            'cart_count': cart_count,
            'message': 'Item removed from cart'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/checkout')
def checkout():
    if 'user_type' not in session or session['user_type'] != 'buyer':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get cart items
    cursor.execute("""
        SELECT c.product_id, c.quantity, CAST(p.price AS DECIMAL(10,2)) as price, p.name, p.image
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = %s
    """, (session['user_id'],))
    items = cursor.fetchall()
    
    # Calculate total
    total = Decimal('0.00')
    for item in items:
        total += Decimal(str(item['price'])) * Decimal(str(item['quantity']))
    
    # Get user addresses
    cursor.execute("""
        SELECT * FROM addresses 
        WHERE user_id = %s
        ORDER BY is_default DESC
    """, (session['user_id'],))
    addresses = cursor.fetchall()
    
    conn.close()
    
    return render_template('checkout.html', 
                         items=items, 
                         total=float(total),
                         addresses=addresses)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'user_type' not in session or session['user_type'] != 'buyer':
        return redirect(url_for('login'))

    address_id = request.form.get('address_id')
    if not address_id:
        flash('Please select a delivery address', 'error')
        return redirect(url_for('checkout'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get cart items to calculate total
        cursor.execute("""
            SELECT SUM(CAST(p.price AS DECIMAL(10,2)) * c.quantity) as total
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        """, (session['user_id'],))
        total = cursor.fetchone()['total']
        
        # Store payment attempt
        payment_id = f"payment_{int(time.time())}"
        payment_status_cache[payment_id] = {
            'user_id': session['user_id'],
            'status': 'pending',
            'timestamp': time.time(),
            'address_id': address_id,
            'total': float(total)
        }

        # Start payment verification in background
        Thread(target=verify_payment_and_create_order, args=(payment_id,)).start()
        return redirect(url_for('payment_page', payment_id=payment_id))
        
    except Exception as e:
        conn.rollback()
        flash(f'Error processing payment: {str(e)}', 'error')
        return redirect(url_for('checkout'))
    finally:
        conn.close()

@app.route('/payment/<payment_id>')
def payment_page(payment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    payment_data = payment_status_cache.get(payment_id)
    if not payment_data or payment_data['user_id'] != session['user_id']:
        flash('Invalid payment session', 'error')
        return redirect(url_for('checkout'))

    return render_template('payment.html', 
                         payment_id=payment_id,
                         payment_status=payment_data['status'],
                         total=float(payment_data['total']))

@app.route('/check_payment/<payment_id>')
def check_payment(payment_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    payment_data = payment_status_cache.get(payment_id)
    if not payment_data or payment_data['user_id'] != session['user_id']:
        return jsonify({'success': False, 'message': 'Invalid payment session'})
    
    return jsonify({
        'success': True,
        'status': payment_data['status'],
        'timestamp': payment_data['timestamp']
    })

@app.route('/orders')
def orders():
    if 'user_type' not in session or session['user_type'] != 'buyer':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get all orders with product details
        cursor.execute("""
            SELECT 
                o.id as order_id,
                o.created_at,
                o.payment_status,
                p.id as product_id,
                p.name,
                p.image,
                o.quantity,
                o.price,
                (o.quantity * o.price) as item_total
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC
        """, (session['user_id'],))
        orders = cursor.fetchall()

        # Group items by order ID
        orders_dict = {}
        for order in orders:
            order_id = order['order_id']
            if order_id not in orders_dict:
                orders_dict[order_id] = {
                    'order_id': order_id,
                    'created_at': order['created_at'],
                    'payment_status': order['payment_status'],
                    'items': [],
                    'total': 0
                }
            orders_dict[order_id]['items'].append(order)
            orders_dict[order_id]['total'] += order['item_total']

        # Convert to list for template
        orders_list = list(orders_dict.values())
        
        return render_template('orders.html', orders=orders_list)
        
    except Exception as e:
        print(f"Error fetching orders: {str(e)}")
        return render_template('orders.html', orders=[])
    finally:
        conn.close()

# ------------------- SELLER ROUTES ------------------- #

@app.route('/seller')
def seller_dashboard():
    if 'user_type' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM products WHERE seller_id=%s
    """, (session['user_id'],))
    products = cursor.fetchall()

    cursor.execute("""
        SELECT o.*, p.name, u.username AS buyer, CAST(p.price AS DECIMAL(10,2)) as price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.user_id = u.id
        WHERE p.seller_id = %s
    """, (session['user_id'],))
    orders = cursor.fetchall()

    total_earnings = Decimal('0.00')
    for order in orders:
        total_earnings += Decimal(str(order['price'])) * Decimal(str(order['quantity']))

    conn.close()
    return render_template('seller_dashboard.html', 
                         products=products, 
                         orders=orders, 
                         total_earnings=float(total_earnings))

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_type' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        files = request.files.getlist('images')

        if files:
            filenames = []
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    filenames.append(filename)

            filenames_str = ','.join(filenames)

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO products (name, description, price, image, seller_id, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, description, price, filenames_str, session['user_id'], category))
                conn.commit()
                flash('Product added successfully!', 'success')
                return redirect(url_for('seller_dashboard'))
            except Exception as e:
                conn.rollback()
                flash(f'Error adding product: {str(e)}', 'error')
            finally:
                conn.close()

    return render_template('add_product.html')

@app.route('/edit_product', methods=['GET', 'POST'])
def edit_product():
    if 'user_type' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))

    if request.method == 'POST':
        product_id = request.form['product_id']
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category = request.form['category']
        images = request.files.getlist('images')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT image FROM products WHERE id=%s", (product_id,))
            product = cursor.fetchone()
            existing_images = product['image'].split(',') if product and product['image'] else []

            new_images = []
            for file in images:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    new_images.append(filename)

            all_images = existing_images + new_images
            image_str = ','.join(all_images)

            cursor.execute("""
                UPDATE products 
                SET name=%s, description=%s, price=%s, image=%s, category=%s
                WHERE id=%s AND seller_id=%s
            """, (name, description, price, image_str, category, product_id, session['user_id']))
            conn.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('seller_dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f'Error updating product: {str(e)}', 'error')
        finally:
            conn.close()
    
    product_id = request.args.get('product_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    product = cursor.fetchone()
    
    if product and product['image']:
        product['images'] = product['image'].split(',')
    else:
        product['images'] = []
    
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/delete_product', methods=['POST'])
def delete_product():
    if 'user_id' not in session or session['user_type'] != 'seller':
        return redirect(url_for('login'))

    product_id = request.form.get('product_id')
    if not product_id:
        flash('Product ID is required', 'error')
        return redirect(url_for('seller_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT seller_id, image FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        
        if not product:
            flash('Product not found', 'error')
            return redirect(url_for('seller_dashboard'))
            
        if product[0] != session['user_id']:
            flash('You can only delete your own products', 'error')
            return redirect(url_for('seller_dashboard'))
        
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        
        if product[1]:
            for image in product[1].split(','):
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image))
                except OSError:
                    pass
        
        conn.commit()
        flash('Product deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('seller_dashboard'))

# ------------------- ADDRESS MANAGEMENT ROUTES ------------------- #

@app.route('/save_address', methods=['POST'])
def save_address():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.get_json()
    full_name = data.get('full_name')
    phone = data.get('phone')
    address = data.get('address')
    city = data.get('city')
    state = data.get('state')
    pincode = data.get('pincode')
    is_default = data.get('is_default', False)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # If setting as default, first unset any existing defaults
        if is_default:
            cursor.execute("""
                UPDATE addresses 
                SET is_default = FALSE 
                WHERE user_id = %s
            """, (session['user_id'],))
        
        cursor.execute("""
            INSERT INTO addresses 
            (user_id, full_name, phone, address, city, state, pincode, is_default)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (session['user_id'], full_name, phone, address, city, state, pincode, is_default))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Address saved successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/set_default_address', methods=['POST'])
def set_default_address():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.get_json()
    address_id = data.get('address_id')
    
    if not address_id:
        return jsonify({'success': False, 'message': 'Address ID missing'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First unset any existing defaults
        cursor.execute("""
            UPDATE addresses 
            SET is_default = FALSE 
            WHERE user_id = %s
        """, (session['user_id'],))
        
        # Set the new default
        cursor.execute("""
            UPDATE addresses 
            SET is_default = TRUE 
            WHERE id = %s AND user_id = %s
        """, (address_id, session['user_id']))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Default address updated'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# ------------------- UTILITY ROUTES ------------------- #

@app.route('/get_cart_count')
def get_cart_count():
    if 'user_id' not in session:
        return jsonify({'cart_count': 0})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = %s", (session['user_id'],))
        result = cursor.fetchone()
        cart_count = result['count'] if result['count'] else 0
        session['cart_count'] = cart_count
        return jsonify({'cart_count': cart_count})
    except Exception as e:
        return jsonify({'cart_count': 0, 'error': str(e)})
    finally:
        conn.close()

@app.route('/update_session_cart_count', methods=['POST'])
def update_session_cart_count():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    data = request.get_json()
    session['cart_count'] = data.get('count', 0)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)