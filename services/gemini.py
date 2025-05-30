from google.generativeai import GenerativeModel

model = GenerativeModel(model_name="gemini-2.0-flash")

def generate_gemini_response(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Sorry, I encountered an error while processing your request."
