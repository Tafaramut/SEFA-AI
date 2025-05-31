import os
from flask import Flask
from routes.whatsapp import whatsapp_bp

app = Flask(__name__)
app.register_blueprint(whatsapp_bp)

@app.route('/')
def home():
    return "🚀 Flask WhatsApp chatbot is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
