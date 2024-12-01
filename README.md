### **InfiChat-Web**

INFIChat is a Python-based web application that provides a custom AI chatbot solution designed to streamline internal communication and enhance document-based responses. The chatbot leverages internal company documents and APIs to deliver relevant and accurate responses to employee queries.

---

Features

- Custom AI Chatbot: Trained with internal documents for company-specific responses.
- Integration with Microsoft Teams: Seamless integration with Teams for enhanced communication.
- Document Management: Backend system for uploading, processing, and searching documents using FAISS and embedding techniques.
- Proactive Notifications: Subscribed users receive reminders for daily menus, water intake, and movement prompts.
- Role-Based Access Control: Secure access to features based on user roles.

---

Tech Stack

- Programming Language: Python
- Web Framework: Flask
- Database: SQLite
- AI Tools: FAISS for similarity search, Embedding Models, OpenAI embedding, and LLM model
- Deployment: Azure Web App and Digital Ocean
- Frontend: HTML/CSS

---

Installation and Setup

Prerequisites

- Python 3.8 or above
- Virtual Environment

Steps

1. Clone the Repository
git clone https://github.com/elisturegun/InfiChat-Web.git 
cd INFIChat

2. Create and Activate a Virtual Environment
- On Linux/MacOS:
  ```
  python -m venv venv
  source venv/bin/activate
  ```
- On Windows:
  ```
  python -m venv venv
  venv\Scripts\activate
  ```

3. Install Dependencies
pip install -r requirements.txt

4. Set Up Environment Variables
- Create a `.env` file in the root directory and add the following environment variables:
  ```
  OPENAI_API_KEY=<your_openai_api_key>
  UPLOAD_PASSWORD=<your_upload_password>
  CLIENT_ID=<your_client_id>
  CLIENT_SECRET=<your_client_secret>
  TENANT_ID=<your_tenant_id>
  GROUP_ID=<your_group_id>
  ```

5. Run the Application
python app.py


6. Access the Application
Open your web browser and navigate to:
http://localhost:5000

---

Usage

User Features
- Chat with the Bot: Users can interact with the AI chatbot for queries related to internal documents.

Admin Features
- Upload Documents: Upload internal documents for the chatbot to use in its responses.
- Manage Subscriptions: Control user access to notifications and other features.

---

Future Enhancements

- Add sentiment analysis for a more personalized response.
- Extend support for multiple languages.
- Enhance the document search feature with advanced AI techniques.

---

License

This project is licensed under the MIT License.

---
