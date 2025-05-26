# ecommerce-dbms
An academic project simulating an e-commerce platform, focusing on database management and web application development. Built using Python's Flask framework and MySQL, it offers functionalities for both buyers and sellers, including product browsing, cart management, and order processing.

Features
User Roles:

Buyer: Browse products, add items to the cart, and place orders.

Seller: Manage product listings and view orders.
GitHub
+1
GitHub
+1

Product Management: Add, update, and delete products with associated images.

Cart Functionality: Buyers can add products to the cart, view cart contents, and proceed to checkout.
GitHub

Order Processing: Handle order placements and maintain order history.

Responsive Design: User-friendly interfaces for both buyers and sellers.

Technologies Used
Backend: Python, Flask
GitHub
+1
GitHub
+1

Database: MySQL

Frontend: HTML, CSS

Setup Instructions
Clone the Repository:

bash
Copy
Edit
git clone https://github.com/gtanu13/ecommerce-dbms.git
cd ecommerce-dbms
Set Up a Virtual Environment:

bash
Copy
Edit
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install Dependencies:

bash
Copy
Edit
pip install -r requirements.txt
Configure the Database:

Ensure MySQL is installed and running.

Create a new database (e.g., ecommerce_db).

Update the config.py file with your database credentials:

python
Copy
Edit
DB_HOST = 'localhost'
DB_USER = 'your_username'
DB_PASSWORD = 'your_password'
DB_NAME = 'ecommerce_db'
Initialize the Database:

Run the provided SQL scripts or use the application's database initialization functions to set up the necessary tables.

Run the Application:

bash
Copy
Edit
python app.py
Access the application at http://localhost:5000/.

Project Structure
plaintext
Copy
Edit
ecommerce-dbms/
├── app.py                 # Main Flask application
├── config.py              # Database configuration
├── db.py                  # Database connection and queries
├── templates/             # HTML templates
│   ├── buyer_home.html
│   ├── cart.html
│   └── ...
├── static/                # Static files (CSS, images)
│   ├── cart.jpg
│   ├── earbuds.jpg
│   └── ...
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation
