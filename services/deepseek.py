import requests
import json
import os
from config.settings import BOT_GUIDELINES

def generate_deepseek_response(prompt):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("REFERER", "https://yourdomain.com"),
                "X-Title": os.getenv("SITE_NAME", "AI Assistant Bot"),
            },
            data=json.dumps({
                "model": "deepseek/deepseek-prover-v2:free",
                "messages": [
                    {"role": "system", "content": BOT_GUIDELINES},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 250,
                "top_p": 0.9,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.5
            })
        )

        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print("DeepSeek request failed:", response.status_code)
            print(response.text)
            return None
    except Exception as e:
        print(f"Error in DeepSeek API: {e}")
        return None
