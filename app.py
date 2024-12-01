import asyncio
import base64
import io
import pytesseract
from PIL import Image
from datetime import datetime, timedelta
import requests
from types import SimpleNamespace
from flask import Flask, request, send_file, jsonify,render_template, redirect, url_for, flash, Response, send_from_directory
import os
from pdfminer.high_level import extract_text as extract_pdf_text
import docx
from dotenv import load_dotenv
from database import add_user,get_all_users, get_subscriptions_by_user_type, init_db, is_user_subscribed, unsubscribe,get_all_conversation_references, delete_conversation_reference, add_document, add_subscription, delete_subscription, get_subscriptions_by_user, delete_document, get_document_by_id, get_all_documents,save_conversation_reference, get_conversation_reference, delete_conversation_reference 
from nlp import get_answer, add_document_to_index, delete_document_from_index
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor
from utils import scrape_website_content
import logging
import markdown2
import json
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from msal import ConfidentialClientApplication
import requests
# Load environment variables from .env file
load_dotenv()

# Initialize Flask app and set upload folder
app = Flask(__name__,static_url_path='/static', static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'supersecretkey'

# Predefined password for authentication
UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD")


# Load environment variables from .env file
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
tenant_id = os.getenv('TENANT_ID')
group_id = os.getenv('GROUP_ID')  # ID of your organization's group
bot_user_id = os.getenv("BOT_USER_ID")

# Initialize and update database
try:
    init_db('teams_database.db')
    print("Database initialized and updated successfully.")
except Exception as e:
    print(f"Error initializing or updating database: {e}")

# Create a ThreadPoolExecutor for parallel execution
executor = ThreadPoolExecutor()

logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    try:
        documents = get_all_documents()  # Get all documents from the database

        return render_template('index.html', documents=documents)  # Render the index.html template with documents
    except Exception as e:
        # Log the error for debugging purposes
        app.logger.error(f"Error occurred while fetching documents: {e}")

        # Optionally, you could return a custom error page
        return render_template('error.html', error_message="Üzgünüz, ziyaret ettiğiniz sayfa şu anda cevap veremiyor. Lütfen daha sonra tekrar deneyiniz."), 500

# Error handlers for specific HTTP errors and general exceptions
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_message="Üzgünüz, aradığınız sayfa bulunamadı."), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Internal server error: {error}")
    return render_template('error.html', error_message="Üzgünüz, sunucumuzda bir hata meydana geldi. Lütfen daha sonra tekrar deneyiniz."), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error(f"Unhandled exception: {e}")
    return render_template('error.html', error_message="Üzgünüz, beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyiniz."), 500



@app.route('/generate', methods=['POST'])
async def ask_question():
    try:
        data = request.json
        question = data.get('question')
        if not question:
            return jsonify({'error': 'Question is missing'}), 400

        def generate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def async_generate():
                documents = await asyncio.to_thread(get_all_documents)
                for chunk in get_answer(question, documents):
                    # Clean chunk and ensure proper punctuation handling
                    chunk = chunk.replace("  ", " ")  # Remove double spaces
                    chunk = chunk.replace("\n", " ")  # Replace newlines with spaces
                    chunk = chunk.replace(" .", ".")  # Fix spaces before punctuation
                    chunk = chunk.replace(" ,", ",")  # Fix spaces before punctuation
                    

                    # Ensure proper word spacing and punctuation spacing
                    chunk = chunk.replace("([.,!?])([A-Za-z])", "$1 $2")  # Space after punctuation
                    chunk = chunk.replace("([a-z])([A-Z])", "$1 $2")  # Space between words

                     # New line before bold or numbered points
                    chunk = chunk.replace(r'(\*\*)', r'\n$1')  # Start new line for bold text (**)
                    chunk = chunk.replace(r'(\d+\.)', r'\n$1')  # Start new line for numbered points (1., 2., etc.)

                    yield f"data: {chunk.strip()}\n\n"  # Ensure each chunk is sent properly

            async_gen = async_generate()

            try:
                while True:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    yield chunk
            except StopAsyncIteration:
                pass
            finally:
                loop.close()

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logging.error(f"An error occurred in ask_question: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/convert_to_markdown', methods=['POST'])
def convert_to_markdown():
    data = request.json
    text = data.get('text', '')
    # Convert the text to markdown
    html = markdown2.markdown(text)
    return jsonify({'markdown': html})

@app.route('/ask', methods=['GET'])
def ask():
    question = request.args.get('question')  # Get the question from the query parameters

    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def async_generate():
            documents = await asyncio.to_thread(get_all_documents)
            for chunk in get_answer(question, documents):
                yield f"data: {chunk}\n\n"

        # Use asyncio.run to execute the async generator and yield results
        async_gen = async_generate()

        try:
            while True:
                # Get the next item from the async generator
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    return Response(generate(), mimetype='text/event-stream')


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    url = request.form.get('url')

    if file and url:
        return jsonify({'success': False, 'error': 'Only one of file or URL should be provided.'})

    extracted_text = ""
    filename = ""

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        extracted_text = extract_text_from_file(filepath)

    elif url:
        filename = url
        extracted_text = scrape_website_content(url)

    if extracted_text:
        return jsonify({'success': True, 'content': extracted_text, 'filename': filename})
    else:
        return jsonify({'success': False, 'error': 'Failed to extract content from the provided file or URL.'})

@app.route('/add_document', methods=['POST'])
def add_document_route():
    content = request.form.get('content')
    filename = request.form.get('filename')
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].split(':')[0]
    password = request.form.get('upload_password')

    if password != UPLOAD_PASSWORD:
        flash('Invalid password.', 'error')
        return redirect(url_for('index'))

    if content and filename:
        doc_id = add_document(filename, content, user_ip)
        document = (doc_id, filename, content, user_ip)  # Only pass 4 elements
        add_document_to_index(document)
        
        flash('Document added successfully!', 'success')
    else:
        flash('Failed to add document. Content or filename is missing.', 'error')

    return redirect(url_for('index'))

@app.route('/delete_document/<int:document_id>', methods=['POST'])
def delete_document_route(document_id):
    document = get_document_by_id(document_id)
    if document:
        filename = document[1]
        delete_document(document_id)
        executor.submit(delete_document_from_index, document_id)  # Update index to remove the document

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        flash('Document deleted successfully!', 'success')
    else:
        flash('Document not found!', 'error')
    return redirect(url_for('index'))

@app.route('/view_document/<int:document_id>', methods=['GET'])
def view_document(document_id):
    document = get_document_by_id(document_id)
    if document:
        return render_template('view_document.html', document=document)
    else:
        flash('Document not found!', 'error')
        return redirect(url_for('index'))

def extract_text_from_file(filepath):
    if filepath.endswith('.pdf'):
        return extract_pdf_text(filepath)
    elif filepath.endswith('.docx'):
        return extract_text_from_docx(filepath)
    elif filepath.endswith('.txt'):
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        return ""

def extract_text_from_docx(filepath):
    doc = docx.Document(filepath)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Dictionary to store the current uploaded menu file for deletion
uploaded_menus = {
    'current_day': None
}


# Scheduler for automatic uploads
scheduler = BackgroundScheduler()

def upload_menu_to_ai(day, file_path):
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Create a filename based on the day
        filename = f"Yemekte_Ne_Var_{day}.txt"
        user_ip = "automated_upload"  # Placeholder for IP address in an automated upload scenario

        # Add the document to the database and get its unique document ID
        doc_id = add_document(filename, content, user_ip)  # This function should return the doc_id

        if doc_id is not None:
            # If a valid doc_id is returned, add the document to the index for search
            add_document_to_index((doc_id, filename, content, user_ip))  # Pass the doc_id
            logging.info(f"Document {filename} with ID {doc_id} successfully uploaded and indexed.")
            return doc_id  # Return the document ID after successful upload
        else:
            logging.error(f"Failed to upload and index document: {filename}. Could not retrieve doc_id.")
            return None
    
    except Exception as e:
        logging.error(f"Error during upload and indexing of the menu for {day}: {e}")
        raise


def delete_previous_day_menu():
    previous_menu_id = uploaded_menus['current_day']
    if previous_menu_id:
        try:
            # Attempt to delete the previous menu from the index and database
            delete_document_from_index(previous_menu_id)
            delete_document(previous_menu_id)
            logging.info(f"Previous menu with ID {previous_menu_id} deleted successfully.")
            uploaded_menus['current_day'] = None  # Clear the record
        except Exception as e:
            logging.error(f"Error deleting previous menu with ID {previous_menu_id}: {e}")
    else:
        logging.info("No previous menu found to delete.")


@app.route('/test_delete_previous_menu', methods=['POST'])
def test_delete_previous_menu():
    try:
        if uploaded_menus['current_day']:
            delete_previous_day_menu()  # Call the function to delete the previous day's menu
            return jsonify({"status": "success", "message": "Previous day's menu deleted successfully."}), 200
        else:
            return jsonify({"status": "success", "message": "No previous menu found to delete."}), 200
    except Exception as e:
        logging.error(f"Error during previous day's menu deletion: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/daily_menu_upload', methods=['GET'])
def trigger_daily_menu_upload():
    try:
        daily_menu_upload()
        return jsonify({"status": "success", "message": "Daily menu upload triggered successfully."}), 200
    except Exception as e:
        logging.error(f"Error during daily menu upload: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def daily_menu_upload():
    # Get today's date
    current_date = datetime.now()
    weekday = current_date.weekday()

    # Days of the week (Monday=0, ..., Friday=4)
    if 0 <= weekday <= 4:
        days_map = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma']
        day_name = days_map[weekday]

        # Path to the corresponding day's menu
        file_name = f"Yemekte_Ne_Var_{current_date.strftime('%d_%m_%y')}.txt"
        file_path = os.path.join(app.static_folder, 'daily_lunch_menus', file_name)

        if os.path.exists(file_path):
            # Delete the previous day's menu from the AI system if it exists
            delete_previous_day_menu()

            # Upload today's menu and get the document ID
            doc_id = upload_menu_to_ai(current_date.strftime('%d_%m_%y'), file_path)

            # Save the document ID for future deletion
            if doc_id:
                uploaded_menus['current_day'] = doc_id
            else:
                logging.error("Failed to upload today's menu, doc_id is None.")


# Define the timezone for Turkey
turkey_tz = pytz.timezone('Europe/Istanbul')

# Schedule for 11:05 AM every weekday (Monday to Friday)
scheduler.add_job(daily_menu_upload, 'cron', day_of_week='mon', hour=11, minute=5, timezone=turkey_tz)

# Schedule for 08:30 AM on Tuesday, Wednesday, Thursday, and Friday
scheduler.add_job(daily_menu_upload, 'cron', day_of_week='tue-fri', hour=8, minute=30, timezone=turkey_tz)


# Route to render yemek_canvas.html
@app.route('/yemek_canvas')
def yemek_canvas():
    app.logger.info("Rendering yemek_canvas.html")
    return render_template('yemek_canvas.html')


@app.route('/get_last_menu', methods=['GET'])
def get_last_menu():
    try:
        folder = os.path.join(app.static_folder, 'daily_lunch_menus')
        current_date = datetime.now()
        monday_date = current_date - timedelta(days=current_date.weekday())  # Get Monday's date

        # List of weekdays and file names
        days_of_week = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma']
        file_names = [f'Yemekte_Ne_Var_{(monday_date + timedelta(days=i)).strftime("%d_%m_%y")}.txt' for i in range(5)]

        menu_data = {}

        # Process each day's file
        for i, file_name in enumerate(file_names):
            file_path = os.path.join(folder, file_name)
            app.logger.info(f"Looking for file: {file_path}")

            # Check if the file exists
            if not os.path.exists(file_path):
                app.logger.error(f"Menu file for {days_of_week[i]} not found: {file_name}")
                menu_data[f'{days_of_week[i].lower()}_hot'] = ''
                menu_data[f'{days_of_week[i].lower()}_salad'] = ''
                continue

            # Initialize empty strings for Sıcak Menü and Salata-Tatlı
            hot_menu = []
            salad_menu = []
            collecting_hot = False
            collecting_salad = False

            # Read and process the file
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    
                    if 'Sıcak Menü' in line:
                        collecting_hot = True
                        collecting_salad = False  # Stop collecting salad if started earlier
                        continue  # Skip the label line

                    elif 'Salata-Tatlı' in line:
                        collecting_salad = True
                        collecting_hot = False  # Stop collecting hot menu if started earlier
                        continue  # Skip the label line

                    # Collect menu items based on the current section
                    if collecting_hot:
                        hot_menu.append(line)
                    elif collecting_salad:
                        salad_menu.append(line)

            # Store the collected data for each day
            menu_data[f'{days_of_week[i].lower()}_hot'] = "\n".join(hot_menu).strip()
            menu_data[f'{days_of_week[i].lower()}_salad'] = "\n".join(salad_menu).strip()

        # Return the combined menu data as a JSON response
        return jsonify(menu_data)

    except Exception as e:
        app.logger.error(f"Unhandled exception: {e}")
        return "Error: Something went wrong", 500



@app.route('/download_menu', methods=['POST'])
def download_menu():
    base64_data = request.form.get('image_data')
    
    # Get the menu data from the form for each day
    monday_menu = request.form.get('monday_menu')
    tuesday_menu = request.form.get('tuesday_menu')
    wednesday_menu = request.form.get('wednesday_menu')
    thursday_menu = request.form.get('thursday_menu')
    friday_menu = request.form.get('friday_menu')

    if base64_data:
        # Remove the "data:image/jpeg;base64," part from the base64 string
        base64_data = base64_data.split(",")[1]
        image_data = base64.b64decode(base64_data)

        # Path to save the image on the server
        save_folder = os.path.join(app.static_folder, 'weekly_lunch_menus')
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)  # Create the folder if it doesn't exist

        # Calculate the Monday date of the current week
        current_date = datetime.now()
        monday_date = current_date - timedelta(days=current_date.weekday())  # Get Monday's date
        monday_date_str = monday_date.strftime("%d_%m_%y")  # Format Monday's date as dd_mm_yy

        # Create text files for each day
        save_text_files(monday_date_str, monday_menu, tuesday_menu, wednesday_menu, thursday_menu, friday_menu)

        # Define the file path with Monday's date appended to the filename
        file_name = f'haftalik_yemek_menusu_{monday_date_str}.jpg'
        file_path = os.path.join(save_folder, file_name)

        # Save the image to the server's static folder
        with open(file_path, 'wb') as f:
            f.write(image_data)

        # Create an in-memory file using BytesIO so the file can be sent as a download
        img_io = io.BytesIO(image_data)
        img_io.seek(0)  # Reset the stream position to the beginning

        # Return the image as a downloadable file to the browser, with Monday's date in the filename
        return send_file(
            img_io,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name=f'haftalik_yemek_menusu_{monday_date_str}.jpg'  # Name of the file for the browser download
        )

    return redirect(url_for('yemek_canvas'))

def save_text_files(monday_date_str, monday_menu, tuesday_menu, wednesday_menu, thursday_menu, friday_menu):
    """ Save each day's menu into separate text files with the appropriate date in the filename. """
    
    # Get the current date (assumed as Monday)
    monday_date = datetime.strptime(monday_date_str, "%d_%m_%y")
    
    # Calculate the other weekdays
    tuesday_date = monday_date + timedelta(days=1)
    wednesday_date = monday_date + timedelta(days=2)
    thursday_date = monday_date + timedelta(days=3)
    friday_date = monday_date + timedelta(days=4)

    # Create the folder for storing text files if it doesn't exist
    text_folder = os.path.join(app.static_folder, 'daily_lunch_menus')
    if not os.path.exists(text_folder):
        os.makedirs(text_folder)

    # Save each day's menu in a separate text file
    save_menu_to_file(monday_date, monday_menu, text_folder)
    save_menu_to_file(tuesday_date, tuesday_menu, text_folder)
    save_menu_to_file(wednesday_date, wednesday_menu, text_folder)
    save_menu_to_file(thursday_date, thursday_menu, text_folder)
    save_menu_to_file(friday_date, friday_menu, text_folder)

def save_menu_to_file(date, menu_content, folder):
    """ Helper function to save a menu for a specific date to a text file in Turkish. """
    
    # Format the date as dd_mm_yy
    date_str = date.strftime("%d_%m_%y")
    # Format the full date in Turkish (e.g., 30 Eylül 2024 Pazartesi Öğle Yemeği Menüsü)
    full_date_str = date.strftime('%d %B %Y %A')  # New format: 30 Eylül 2024 Pazartesi
    
    # Map English weekday names to Turkish
    day_translations = {
        'Monday': 'Pazartesi',
        'Tuesday': 'Salı',
        'Wednesday': 'Çarşamba',
        'Thursday': 'Perşembe',
        'Friday': 'Cuma'
    }

    # Replace English day names with Turkish day names
    for eng_day, tr_day in day_translations.items():
        full_date_str = full_date_str.replace(eng_day, tr_day)

    # Replace English month names with Turkish
    month_translations = {
        'January': 'Ocak',
        'February': 'Şubat',
        'March': 'Mart',
        'April': 'Nisan',
        'May': 'Mayıs',
        'June': 'Haziran',
        'July': 'Temmuz',
        'August': 'Ağustos',
        'September': 'Eylül',
        'October': 'Ekim',
        'November': 'Kasım',
        'December': 'Aralık'
    }

    for eng_month, tr_month in month_translations.items():
        full_date_str = full_date_str.replace(eng_month, tr_month)

    # Append "Öğle Yemeği Menüsü" to match the required format
    full_date_str += " Öğle Yemeği Menüsü"

    # Create the filename with the date
    file_name = f'Yemekte_Ne_Var_{date_str}.txt'
    file_path = os.path.join(folder, file_name)
    # Write the content to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        # Write the formatted date and titles in Turkish
        file.write(f"{full_date_str}\n\n")  # 30 Eylül 2024 Pazartesi Öğle Yemeği Menüsü
        file.write("Sıcak Menü:\n")
        file.write(menu_content)

@app.route('/subscribe_water_reminder', methods=['POST'])
def toggle_water_reminder():
    try:
        data = request.json
        user_id = data.get('userId')

        # Log incoming data for debugging
        app.logger.info(f"Received request for water subscription with userId: {user_id}")

        if not user_id:
            return jsonify({'error': 'User ID is missing'}), 400

        if is_user_subscribed(user_id, 'water_reminder'):
            unsubscribe(user_id, 'water_reminder')
            return jsonify({'message': 'Su hatırlatıcı aboneliğiniz iptal edildi'})  # Return unsubscribe message
        else:
            add_subscription(user_id, 'water_reminder')
            return jsonify({'message': 'Su hatırlatıcı aboneliği isteğiniz alındı'})  # Return subscribe message

    except Exception as e:
        app.logger.error(f"Error in toggle_water_reminder: {str(e)}")  # Log the actual error
        return jsonify({'error': str(e)}), 500
    
@app.route('/subscribe_food_reminder', methods=['POST'])
def toggle_food_reminder():
    try:
        data = request.json
        user_id = data.get('userId')

        if not user_id:
            return jsonify({'error': 'User ID is missing'}), 400

        if is_user_subscribed(user_id, 'food_reminder'):
            unsubscribe(user_id, 'food_reminder')
            return jsonify({'message': 'Yemek hatırlatıcı aboneliğiniz iptal edildi'})  # Unsubscribe message
        else:
            add_subscription(user_id, 'food_reminder')
            return jsonify({'message': 'Yemek hatırlatıcı aboneliği isteğiniz alındı'})  # Subscribe message

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/subscribe_movement_reminder', methods=['POST'])
def toggle_movement_reminder():
    try:
        data = request.json
        user_id = data.get('userId')

        if not user_id:
            return jsonify({'error': 'User ID is missing'}), 400

        if is_user_subscribed(user_id, 'movement_reminder'):
            unsubscribe(user_id, 'movement_reminder')
            return jsonify({'message': 'Hareket hatırlatıcı aboneliğiniz iptal edildi'})  # Unsubscribe message
        else:
            add_subscription(user_id, 'movement_reminder')
            return jsonify({'message': 'Hareket hatırlatıcı aboneliği isteğiniz alındı'})  # Subscribe message

    except Exception as e:
        return jsonify({'error': str(e)}), 500


#  https://bot2748dd.azurewebsites.net/api/messages
def format_menu_for_teams(menu_content):
    """
    Format the menu content for proper display in Teams, ensuring bullet points for each item.
    """
    formatted_content = menu_content.replace("Sıcak Menü:", "\n\n**Sıcak Menü**:\n-") \
                                    .replace("Salata-Tatlı:", "\n\n**Salata-Tatlı**:\n-") \
                                    .replace("\n", "\n- ")  # Add bullet points to all items
    return formatted_content

def get_daily_menu():
    """Get the current day's menu from the 'Yemekte_Ne_Var_dd_mm_yy.txt' file."""
    current_date = datetime.now().strftime("%d_%m_%y")
    file_name = f"Yemekte_Ne_Var_{current_date}.txt"
    file_path = os.path.join(app.static_folder, 'daily_lunch_menus', file_name)

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        return None

def notify_subscribed_users():
    """Notify all users subscribed to the food reminder with the daily menu."""
    try:
        # Get the list of users subscribed to food reminders
        subscribed_users = get_subscriptions_by_user_type('food_reminder')

        # Fetch today's menu
        menu_content = get_daily_menu()

        if not menu_content:
            logging.error("Today's menu file not found.")
            return

        # Send the menu to all subscribed users
        for user in subscribed_users:
            user_id = user[0]  # Assuming the first element in user tuple is user_id
            try:
                # Call the bot to send the message
                send_menu_to_bot(user_id, menu_content)
            except Exception as e:
                logging.error(f"Error sending menu to user {user_id}: {str(e)}")

    except Exception as e:
        logging.error(f"Error in notify_subscribed_users: {str(e)}")

@app.route('/notify_subscribed_users', methods=['POST'])
def trigger_notify_subscribed_users():
    try:
        notify_subscribed_users()  # Call the function to notify all subscribed users
        return jsonify({"status": "success", "message": "Notifications sent successfully."}), 200
    except Exception as e:
        logging.error(f"Error triggering notifications: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def send_menu_to_bot(user_id, menu_content):
    """Send the daily menu to the bot for a specific user."""
    try:
        
        # Print userId and menuContent for debugging purposes
        print(f"Sending menu to user ID: {user_id}")
        print(f"Menu content: {menu_content}")
        
        # Call the bot to send the message to the user
        url = "https://bot2748dd.azurewebsites.net/sendMenu"  # Replace with your actual bot service URL
        payload = {
            "userId": user_id,
            "menuContent": menu_content
        }
        
        # Print payload for debugging
        print(f"Payload: {payload}")
        
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for any HTTP errors
        
        # Print success message
        print(f"Menu sent to user {user_id} successfully.")
    except Exception as e:
        # Print error message
        print(f"Error sending menu to bot for user {user_id}: {str(e)}")


# Schedule the job to run at 11:30 AM Turkey time every weekday (Monday to Friday)
scheduler.add_job(notify_subscribed_users, 'cron', day_of_week='mon-fri', hour=11, minute=30, timezone=turkey_tz)


def notify_water_users():
    """Notify all users subscribed to the water reminder."""
    try:
        subscribed_users = get_subscriptions_by_user_type('water_reminder')

        reminder_content = "Su içme zamanı! Sağlığınız için su için."  # Define your reminder message

        for user in subscribed_users:
            user_id = user[0]  # Assuming the first element is user_id
            try:
                send_water_reminder_to_bot(user_id, reminder_content)
            except Exception as e:
                logging.error(f"Error sending water reminder to user {user_id}: {str(e)}")
    except Exception as e:
        logging.error(f"Error in notify_water_users: {str(e)}")


def send_water_reminder_to_bot(user_id, reminder_content):
    """Send the water reminder to the bot for a specific user."""
    try:
        url = "https://bot2748dd.azurewebsites.net/sendWaterReminder"  # Replace with your bot service URL
        payload = {
            "userId": user_id,
            "reminderContent": reminder_content
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        print(f"Water reminder sent to user {user_id} successfully.")
    except Exception as e:
        print(f"Error sending water reminder to bot for user {user_id}: {str(e)}")

@app.route('/notify_subscribed_water_users', methods=['POST'])
def trigger_notify_subscribed_water_users():
    try:
        notify_water_users()
        return jsonify({"status": "success", "message": "Water reminders sent successfully."}), 200
    except Exception as e:
        logging.error(f"Error triggering water reminders: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



# Schedule water reminder: every hour during work hours (9 AM to 5 PM)
scheduler.add_job(notify_water_users, 'cron', day_of_week='mon-fri', hour='9-17', minute=0, timezone=turkey_tz)



def notify_movement_users():
    """Notify all users subscribed to the movement reminder."""
    try:
        subscribed_users = get_subscriptions_by_user_type('movement_reminder')

        reminder_content = "Hareket etme zamanı! Sağlığınız için ayağa kalkın."  # Define your reminder message

        for user in subscribed_users:
            user_id = user[0]  # Assuming the first element is user_id
            try:
                send_movement_reminder_to_bot(user_id, reminder_content)
            except Exception as e:
                logging.error(f"Error sending movement reminder to user {user_id}: {str(e)}")
    except Exception as e:
        logging.error(f"Error in notify_movement_users: {str(e)}")


def send_movement_reminder_to_bot(user_id, reminder_content):
    """Send the movement reminder to the bot for a specific user."""
    try:
        url = "https://bot2748dd.azurewebsites.net/sendMovementReminder"  # Replace with your bot service URL
        payload = {
            "userId": user_id,
            "reminderContent": reminder_content
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        print(f"Movement reminder sent to user {user_id} successfully.")
    except Exception as e:
        print(f"Error sending movement reminder to bot for user {user_id}: {str(e)}")

@app.route('/notify_subscribed_movement_users', methods=['POST'])
def trigger_notify_subscribed_movement_users():
    try:
        notify_movement_users()
        return jsonify({"status": "success", "message": "Movement reminders sent successfully."}), 200
    except Exception as e:
        logging.error(f"Error triggering movement reminders: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



# Schedule movement reminder: every 2 hours, starting from 10 AM to 6 PM
scheduler.add_job(notify_movement_users, 'cron', day_of_week='mon-fri', hour='10,12,14,16,18', minute=0, timezone=turkey_tz)


@app.route('/save_conversation_reference', methods=['POST'])
def save_conversation_reference_route():
    try:
        data = request.json
        user_id = data.get('userId')
        reference = data.get('reference')
        # Log the received data for debugging purposes
        print(f"Received data for userId: {user_id}")
        print(f"Received conversation reference: {reference}")

        if not user_id or not reference:
            return jsonify({'error': 'Missing userId or conversation reference'}), 400

        save_conversation_reference(user_id, reference)
        return jsonify({'message': 'Conversation reference saved successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_conversation_reference/<user_id>', methods=['GET'])
def get_conversation_reference_route(user_id):
    try:
        reference = get_conversation_reference(user_id)
        if reference:
            print(reference)
            return jsonify({'reference': reference}), 200
        else:
            return jsonify({'message': 'No conversation reference found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    






# Start the scheduler
scheduler.start()

@app.route('/announcement')
def announcement_page():
    return render_template('announcement.html')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def get_access_token():
    try:
        app = ConfidentialClientApplication(
            client_id,
            authority=f'https://login.microsoftonline.com/{tenant_id}',
            client_credential=client_secret
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if "access_token" in result:
            token = result["access_token"]
            print("Access Token Retrieved Successfully.")
            return token
        else:
            print("Failed to retrieve token. Error:", result)
            raise Exception("Failed to retrieve access token")
    except Exception as e:
        print("Error in get_access_token:", str(e))
        raise


# Fetch team members from Microsoft Graph API
def fetch_team_roster(team_id, access_token):
    url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/members"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    
    # Log the response details for debugging
    print("Response Status Code:", response.status_code)
    print("Response Body:", response.text)
    
    if response.status_code == 200:
        return response.json()["value"]
    else:
        response.raise_for_status()
        
        
# @app.route('/testFetchRoster', methods=['POST'])
# def test_fetch_roster():
#     try:
#         data = request.json
#         group_id = data.get("groupId")  # Expect groupId (GUID) now

#         if not group_id:
#             return jsonify({"error": "groupId is required"}), 400

#         # Get access token
#         print("Fetching Access Token...")
#         access_token = get_access_token()
#         print("Access Token:", access_token)

#         # Fetch team roster
#         team_members = fetch_team_roster(group_id, access_token)

#         # Process and save conversation references
#         conversation_references = []
#         for member in team_members:
#             conversation_reference = {
#                 "userId": member["id"],
#                 "displayName": member["displayName"],
#                 "email": member.get("mail", "N/A"),
#                 "userPrincipalName": member.get("userPrincipalName", "N/A")
#             }
#             print("Conversation Reference:", conversation_reference)
#             conversation_references.append(conversation_reference)

#         return jsonify({
#             "message": "Team roster fetched and conversation references saved.",
#             "teamMembers": conversation_references
#         }), 200

#     except Exception as e:
#         print("Error in /testFetchRoster:", str(e))
#         return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


# Endpoint to trigger bot fetching team members
@app.route('/trigger-fetch-team-members', methods=['POST'])
def trigger_fetch_team_members():
    access_token = get_access_token()
    print(access_token)
    bot_endpoint = "https://bot2748dd.azurewebsites.net/fetchTeamMembers"  # Bot endpoint URL
    team_id = request.json.get("teamId")
    service_url = request.json.get("serviceUrl")

    if not team_id or not service_url:
        return jsonify({"error": "Missing teamId or serviceUrl in the request"}), 400

    # Request payload for the bot server
    payload = {
        "teamId": team_id,
        "serviceUrl": service_url
    }

    try:
        # Make request to bot server
        response = requests.post(bot_endpoint, json=payload)
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/testFetchRoster', methods=['POST'])
def test_fetch_roster():
    try:
        data = request.json
        team_id = data.get("teamId")  # Expect Teams-specific ID (e.g., 19:...@thread.tacv2)

        if not team_id:
            return jsonify({"error": "teamId is required"}), 400

        # Call Bot Framework service
        bot_framework_url = "http://localhost:3978/getTeamRoster"  # Replace with actual Bot Framework API URL
        response = requests.post(bot_framework_url, json={"teamId": team_id})

        # Handle response
        if response.status_code == 200:
            team_members = response.json()["teamMembers"]
            return jsonify({
                "message": "Team roster fetched successfully.",
                "teamMembers": team_members
            }), 200
        else:
            return jsonify({
                "error": "Failed to fetch team members",
                "details": response.text
            }), response.status_code

    except Exception as e:
        print("Error in /testFetchRoster:", str(e))
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


def get_users_from_group():
    access_token = get_access_token()
    headers = {'Authorization': f'Bearer {access_token}'}
    url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        users = response.json().get('value', [])
        for user in users:
            print(user, "\n")
            # Store each user in the users table
            add_user(user["id"], user["displayName"])
        return [{"id": user["id"], "displayName": user["displayName"]} for user in users]
    else:
        print(f"Failed to retrieve users: {response.status_code}, {response.text}")
        raise Exception(f"Failed to retrieve users: {response.status_code}, {response.text}")


@app.route('/sendAnnouncement', methods=['POST'])
def send_announcement():
    try:
        logging.info("Received request to send announcement")
        is_test = request.args.get('test', default=False, type=bool)
        logging.info(f"Test mode: {is_test}")
        # Get the announcement text
        announcement_text = request.form.get('announcementText')
        logging.info(f"Announcement text: {announcement_text}")
        
        file = request.files.get('announcementMedia')
        media_url = None
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('uploads', filename)
            file.save(filepath)
            media_url = f'http://188.166.70.139:8000/uploads/{filename}'
            logging.info(f"Media uploaded: {media_url}")
        # Prepare the announcement message
        message = {
            "announcementText": announcement_text,
            "mediaUrl": media_url
        }
        
        # For testing, specify two real user IDs directly
        test_users = [
            {"userId": "29:1UVE8qyq0-nr-CGOZE3-IeHezJOLTPwQmNPFeKVUDtenuoor6Vyl1QZSFCGR35S03lgkGf-IdD6gnMglhEH2KKg", "displayName": "Öykü Elis Türegün"},
            {"userId": "c0f28945-2668-454f-8a21-c4069c57b18f", "displayName": "Elvan Başaran"},
            {"userId": "89011c8e-eb3d-4f8a-b2b5-f0ab4168027d", "displayName": "öykü elis türegün"}
        ]
        if is_test:
            logging.info(f"Test mode active. Sending announcement to test users: {test_users[0]['displayName']}, {test_users[1]['displayName']}")
            users = test_users  # Limit to two specific users for the test
        else:
            logging.info("Fetching users from the organization group")
            # users = get_users_from_group
            users = get_all_conversation_references()
            logging.info(f"Total users retrieved: {len(users)}")
        # Send the announcement to all users (or test users)
        send_announcement_to_users(users, message)
        logging.info("Announcement sent successfully")
        return jsonify({"status": "success", "message": "Announcement sent successfully"}), 200
    except Exception as e:
        logging.error(f"Error in send_announcement: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

#  Send announcement to users using the bot
def send_announcement_to_users(users, message):
    for user in users:
        userId = user['userId']
        displayName = user['displayName']
        
        print("user id:", userId)
        print("display name:", displayName)
        payload = {
            "userId": userId,
            "announcementText": message['announcementText'],
            "mediaUrl": message['mediaUrl']
        }

        bot_url = "https://bot2748dd.azurewebsites.net/sendAnnouncement"

        try:
            logging.info(f"Sending announcement to user: {displayName} ({userId})")
            response = requests.post(bot_url, json=payload)
            response.raise_for_status()
            logging.info(f"Announcement sent to {userId} successfully")
        except Exception as e:
            logging.error(f"Failed to send announcement to {displayName} ({userId}): {str(e)}")

@app.route('/delete_conversation', methods=['POST'])
def delete_conversation():
    data = request.get_json()
    if not data or 'user_id' not in data:
        return jsonify({"status": "error", "message": "Missing 'user_id' in request body"}), 400

    user_id = data['user_id']
    result = delete_conversation_reference(user_id)
    return jsonify(result)

# Fetch and store users in the organization group
def update_users_in_db():
    try:
        access_token = get_access_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            users = response.json().get('value', [])
            for user in users:
                add_user(user["id"], user["displayName"])
        else:
            print(f"Failed to retrieve users: {response.status_code}, {response.text}")
            raise Exception(f"Failed to retrieve users: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error updating users in DB: {e}")
 

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=8000)
