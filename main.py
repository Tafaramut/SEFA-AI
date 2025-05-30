from flask import Flask
from routes.whatsapp import whatsapp_bp

app = Flask(__name__)
app.register_blueprint(whatsapp_bp)

# ✅ Root route for Render health checks
@app.route('/')
def home():
    return "🚀 Flask WhatsApp chatbot is running!", 200

if __name__ == '__main__':
    app.run(debug=True)
