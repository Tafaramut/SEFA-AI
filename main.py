from flask import Flask
from routes.whatsapp import whatsapp_webhook, whatsapp_bp

app = Flask(__name__)
app.register_blueprint(whatsapp_bp)

if __name__ == '__main__':
    app.run(debug=True)

