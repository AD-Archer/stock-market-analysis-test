"""
Stock Market Analysis API Server

This Flask-based API server provides endpoints for fetching, analyzing, and generating AI recommendations
for stock market data. It serves as the backend for a stock market analysis application.

Features:
- Fetch stock data from NASDAQ (limited to a few symbols due to API rate limits)
- Generate mock data for testing
- Run AI analysis on stock data to generate investment recommendations
- Track long-running tasks with progress reporting
- View and download generated recommendation files

Usage:
1. Start the server: python api.py
2. The server will run on http://localhost:5000
3. API Endpoints:
   - GET /api/status: Check if API is online
   - GET /api/data-status: Check if stock data is available
   - POST /api/fetch-data: Fetch stock data (params: max_stocks, use_mock_data)
   - GET /api/task-status: Get status of current background task
   - POST /api/get-recommendations: Generate AI recommendations
   - GET /api/results: Get list of recommendation files
   - GET /api/download/<filename>: Download a recommendation file
   - GET /api/view-recommendation/<filename>: View a recommendation file
   - GET /api/mock-data: Get mock stock data directly
   - GET /api/stocks: Get stock data for the frontend

Dependencies:
- Flask, Flask-CORS
- pandas
- Custom modules: config, stock_data, ai_utils

Note: This server uses background threading for long-running tasks to avoid blocking
the main thread. Only one background task can run at a time.
"""

import os
import pandas as pd
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import threading

# Import our modules
import sys
sys.path.append('..')  # Add parent directory to path
import config
import stock_data
import ai_utils

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.secret_key = os.urandom(24)

# Global variables to store state
current_task = None
task_progress = 0
task_total = 0
task_message = ""
task_complete = False
nasdaq_df = None

def reset_task_status():
    """Reset the task status variables"""
    global current_task, task_progress, task_total, task_message, task_complete
    current_task = None
    task_progress = 0
    task_total = 0
    task_message = ""
    task_complete = False

def save_stock_data(df):
    """Save stock data to a CSV file"""
    try:
        if df is None or df.empty:
            return False
        
        # Save to the data directory
        output_path = os.path.join(config.DATA_DIR, "nasdaq100_mock_data.csv")
        df.to_csv(output_path, index=False)
        print(f"Saved stock data to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving stock data: {e}")
        return False

@app.route('/api/status', methods=['GET'])
def status():
    """API status check"""
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/data-status', methods=['GET'])
def data_status():
    """Check if we have cached data"""
    global nasdaq_df
    if nasdaq_df is None:
        nasdaq_df = stock_data.load_mock_data()
    
    return jsonify({
        'has_data': nasdaq_df is not None and not nasdaq_df.empty
    })

@app.route('/api/fetch-data', methods=['POST'])
def fetch_data():
    """API endpoint to fetch stock data"""
    global current_task
    
    if current_task is not None:
        return jsonify({
            'success': False,
            'message': f'Another task is already running: {current_task}'
        }), 400
    
    data = request.json
    max_stocks = data.get('max_stocks', 100)
    use_mock_data = data.get('use_mock_data', False)
    
    # Start the data fetching in a background thread
    current_task = "Fetching stock data"
    thread = threading.Thread(target=fetch_data_task, args=(max_stocks, use_mock_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Started fetching stock data'
    })

def fetch_data_task(max_stocks, use_mock_data):
    """Background task to fetch stock data"""
    global task_progress, task_total, task_message, task_complete, nasdaq_df
    
    try:
        # Reset progress
        task_progress = 0
        task_total = 100
        task_message = "Initializing..."
        
        # Load NASDAQ symbols
        task_message = "Loading NASDAQ symbols..."
        symbols = stock_data.load_nasdaq100_symbols()
        # Note: We're now only getting the top 3 symbols due to Alpha Vantage API rate limits
        
        # Limit to max_stocks if specified (though we're already limited to 3 in load_nasdaq100_symbols)
        if max_stocks < len(symbols):
            symbols = symbols[:max_stocks]
        task_progress = 10
        
        # Fetch stock data
        task_message = f"Fetching stock data for {len(symbols)} symbols..."
        task_total = len(symbols) + 10  # 10 for initialization steps
        
        if use_mock_data:
            # Use mock data for testing
            data_list = stock_data.generate_mock_data(symbols)
            for i in range(len(symbols)):
                task_progress = 10 + i
                task_message = f"Generating mock data ({i+1}/{len(symbols)})"
        else:
            # Fetch real data
            data_list = []
            for i, symbol in enumerate(symbols):
                try:
                    stock = stock_data.fetch_stock_data(symbol)
                    if stock is not None:
                        data_list.append(stock)
                except Exception as e:
                    print(f"Error fetching {symbol}: {e}")
                
                task_progress = 10 + i
                task_message = f"Fetching {symbol} ({i+1}/{len(symbols)})"
        
        # Create DataFrame
        nasdaq_df = pd.DataFrame(data_list)
        
        # Save to cache
        task_message = "Saving data to cache..."
        save_stock_data(nasdaq_df)
        
        task_progress = task_total
        task_message = "Data fetching complete!"
        task_complete = True
        
    except Exception as e:
        task_message = f"Error: {str(e)}"
        task_complete = True
    finally:
        global current_task
        current_task = None

@app.route('/api/get-recommendations', methods=['POST'])
def get_recommendations():
    """API endpoint to generate AI recommendations"""
    global current_task, task_complete, task_message, task_progress, task_total
    
    try:
        # Check if a task is already running
        if current_task:
            return jsonify({
                'success': False,
                'message': f'Another task is already running: {current_task}',
                'task_info': {
                    'task': current_task,
                    'progress': task_progress,
                    'total': task_total,
                    'message': task_message,
                    'complete': task_complete
                }
            }), 409
        
        # Reset task status
        reset_task_status()
        task_complete = False
        current_task = "Generating recommendations"
        
        # Start the background task
        thread = threading.Thread(target=recommendations_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Started generating recommendations',
            'task': current_task
        })
    except Exception as e:
        # Reset task status in case of error
        current_task = None
        task_complete = True
        task_message = f"Error: {str(e)}"
        
        return jsonify({
            'success': False,
            'message': f'Error starting recommendations task: {str(e)}'
        }), 500

def recommendations_task():
    """Background task to generate recommendations"""
    global task_progress, task_total, task_message, task_complete, nasdaq_df
    
    try:
        # Reset progress
        task_progress = 0
        task_total = 100
        task_message = "Initializing AI analysis..."
        
        # Load NASDAQ data
        task_message = "Loading NASDAQ data..."
        task_progress = 10
        
        try:
            # Load mock data
            nasdaq_df = stock_data.load_mock_data()
            task_message = f"Loaded data for {len(nasdaq_df)} companies."
        except Exception as e:
            task_message = f"Error loading data: {str(e)}"
            raise
        
        if nasdaq_df is None or nasdaq_df.empty:
            raise Exception("No data available for analysis")
        
        # Generate recommendations
        task_message = "Generating AI recommendations..."
        task_progress = 30
        
        output_path = ai_utils.analyze_stocks(nasdaq_df)
        
        task_progress = 100
        task_message = "Recommendations generated successfully!"
        task_complete = True
        
    except Exception as e:
        task_message = f"Error: {str(e)}"
        task_complete = True
    finally:
        global current_task
        current_task = None

@app.route('/api/task-status', methods=['GET'])
def task_status():
    """API endpoint to get the status of the current task"""
    return jsonify({
        'task': current_task,
        'progress': task_progress,
        'total': task_total,
        'message': task_message,
        'complete': task_complete
    })

@app.route('/api/results', methods=['GET'])
def results():
    """API endpoint to get the list of recommendation files"""
    try:
        results_dir = config.RESULTS_DIR
        
        # Create the results directory if it doesn't exist
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            return jsonify({
                'files': []
            })
        
        files = []
        for filename in os.listdir(results_dir):
            if filename.endswith('.md'):  # Only show markdown files
                file_path = os.path.join(results_dir, filename)
                files.append({
                    'name': filename,
                    'date': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                    'size': os.path.getsize(file_path)
                })
        
        # Sort by date, newest first
        files.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({
            'files': files
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving results: {str(e)}',
            'files': []
        }), 500

@app.route('/api/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """API endpoint to download a recommendation file"""
    try:
        results_dir = config.RESULTS_DIR
        
        # Allow downloading both .md and .txt files
        if not filename.endswith(('.md', '.txt')):
            return jsonify({
                'success': False,
                'message': 'Invalid file type'
            }), 400
            
        file_path = os.path.join(results_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'File not found'
            }), 404
            
        return send_from_directory(results_dir, filename, as_attachment=True)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error downloading file: {str(e)}'
        }), 500

@app.route('/api/view-recommendation/<path:filename>', methods=['GET'])
def view_recommendation(filename):
    """API endpoint to view a recommendation file"""
    results_dir = config.RESULTS_DIR
    
    # Allow viewing both .md and .txt files
    if not filename.endswith(('.md', '.txt')):
        return jsonify({
            'success': False,
            'message': 'Invalid file type'
        }), 400
        
    file_path = os.path.join(results_dir, filename)
    
    if not os.path.exists(file_path):
        return jsonify({
            'success': False,
            'message': 'File not found'
        }), 404
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content,
            'is_markdown': filename.endswith('.md')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error reading file: {str(e)}'
        }), 500

@app.route('/api/mock-data', methods=['GET'])
def get_mock_data():
    """Get mock stock data directly"""
    global nasdaq_df
    if nasdaq_df is None:
        nasdaq_df = stock_data.load_mock_data()
    
    if nasdaq_df is None or nasdaq_df.empty:
        return jsonify({
            'success': False,
            'message': 'No mock data available'
        })
    
    return jsonify(nasdaq_df.to_dict(orient='records'))

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get stock data for the frontend"""
    global nasdaq_df
    if nasdaq_df is None:
        nasdaq_df = stock_data.load_mock_data()
    
    if nasdaq_df is None or nasdaq_df.empty:
        return jsonify([])
    
    # Convert DataFrame to list of dictionaries
    stocks_data = nasdaq_df.to_dict(orient='records')
    
    return jsonify(stocks_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000) 