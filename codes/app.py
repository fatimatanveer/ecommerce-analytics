from flask import Flask, jsonify, render_template_string
import happybase
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)

# HBase connection configuration
HBASE_HOST = 'localhost'
HBASE_PORT = 9090
TABLE_NAME = 'ecommerce_table'

# Function to typecast and clean the DataFrame
def typecast_dataframe(df):
    try:
        df['transaction_info:timestamp'] = pd.to_datetime(df['transaction_info:timestamp'], errors='coerce')
        df['product_details:price'] = pd.to_numeric(df['product_details:price'], errors='coerce')
        df['product_details:quantity'] = pd.to_numeric(df['product_details:quantity'], errors='coerce')
        df['customer_feedback:user_rating'] = pd.to_numeric(df['customer_feedback:user_rating'], errors='coerce')
        df['customer_feedback:is_prime'] = df['customer_feedback:is_prime'].astype(bool)
        return df
    except Exception as e:
        raise ValueError(f"Error in typecasting: {e}")

# Function to generate a base64-encoded chart
def generate_chart(plt_obj):
    img = io.BytesIO()
    plt_obj.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode('utf-8')

@app.route('/')
def eda_dashboard():
    try:
        # Connect to HBase Thrift Server
        connection = happybase.Connection(host=HBASE_HOST, port=HBASE_PORT)
        table = connection.table(TABLE_NAME)

        # Fetch data from HBase
        rows = table.scan(limit=1000)
        data = [
            {**{k.decode('utf-8'): v.decode('utf-8') for k, v in row.items()}, 'row_key': key.decode('utf-8')}
            for key, row in rows
        ]
        dataframe = pd.DataFrame(data)
        dataframe = typecast_dataframe(dataframe)

        # Check the column names
        print("Columns in the DataFrame:", dataframe.columns)

        # Aggregations and Charts
        # 1. Sales Over Time
        sales_over_time = dataframe.groupby(dataframe['transaction_info:timestamp'].dt.date)['product_details:price'].sum()
        plt.figure(figsize=(10, 6))
        sales_over_time.plot(kind='line', marker='o', color='green', title='Sales Over Time')
        plt.xlabel('Date')
        plt.ylabel('Total Sales')
        sales_over_time_chart = generate_chart(plt)

        # 2. Prime vs Non-Prime Sales
        prime_sales = dataframe.groupby('customer_feedback:is_prime')['product_details:price'].sum()
        plt.figure(figsize=(10, 6))
        prime_sales.plot(kind='bar', color=['purple', 'pink'], title='Prime vs Non-Prime Sales')
        plt.xticks(ticks=[0, 1], labels=['Non-Prime', 'Prime'], rotation=0)
        plt.ylabel('Total Sales')
        prime_sales_chart = generate_chart(plt)

        # 3. Sales by Category
        sales_by_category = dataframe.groupby('product_details:category')['product_details:price'].sum()
        plt.figure(figsize=(10, 6))
        sales_by_category.plot(kind='bar', color='blue', title='Sales by Category')
        plt.xlabel('Category')
        plt.ylabel('Total Sales')
        sales_by_category_chart = generate_chart(plt)

        # 4. User Ratings Distribution
        plt.figure(figsize=(10, 6))
        dataframe['customer_feedback:user_rating'].plot(kind='hist', bins=10, color='orange', title='User Ratings Distribution')
        plt.xlabel('Ratings')
        plt.ylabel('Frequency')
        user_ratings_chart = generate_chart(plt)

        # 5. Top 10 Selling Products
        # Check if the 'product_details:product_id' column exists
        if 'product_details:product_id' in dataframe.columns:
            top_10_products = dataframe.groupby('product_details:product_id')['product_details:price'].sum().sort_values(ascending=False).head(10)
            plt.figure(figsize=(10, 6))
            top_10_products.plot(kind='bar', color='teal', title='Top 10 Selling Products')
            plt.xlabel('Product ID')
            plt.ylabel('Total Sales')
            top_10_products_chart = generate_chart(plt)
        else:
            top_10_products_chart = None

        # Render the dashboard
        html_template = f"""
        <html>
        <head><title>E-Commerce Analytics Dashboard</title></head>
        <body>
            <h1>E-Commerce Analytics Dashboard</h1>
            <h2>Sales Over Time</h2>
            <img src="data:image/png;base64,{sales_over_time_chart}" alt="Sales Over Time">
            <h2>Prime vs Non-Prime Sales</h2>
            <img src="data:image/png;base64,{prime_sales_chart}" alt="Prime vs Non-Prime Sales">
            <h2>Sales by Category</h2>
            <img src="data:image/png;base64,{sales_by_category_chart}" alt="Sales by Category">
            <h2>User Ratings Distribution</h2>
            <img src="data:image/png;base64,{user_ratings_chart}" alt="User Ratings Distribution">
        """
        if top_10_products_chart:
            html_template += f"""
            <h2>Top 10 Selling Products</h2>
            <img src="data:image/png;base64,{top_10_products_chart}" alt="Top 10 Selling Products">
            """
        html_template += """
        </body>
        </html>
        """
        return render_template_string(html_template)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
