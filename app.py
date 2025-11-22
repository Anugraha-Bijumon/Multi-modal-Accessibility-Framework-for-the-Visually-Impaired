from flask import Flask, request, jsonify, render_template, send_file
from transformers import pipeline
from gtts import gTTS
import os
import docx  # To handle .docx files
import fitz  # PyMuPDF for PDFs

app = Flask(__name__)

# Load the summarization model
summarizer = pipeline("summarization")


# Ensure uploads folder exists
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "static/audio"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Function to extract text from .docx
def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text if text.strip() else "ERROR: Empty .docx file"
    except Exception as e:
        return f"ERROR: Could not read .docx file - {str(e)}"

# Function to extract text from PDF
def extract_text_from_pdf(file_path):
    try:
        text = ""
        with fitz.open(file_path) as pdf_doc:
            for page in pdf_doc:
                text += page.get_text("text") + "\n"
        return text.strip() if text.strip() else "ERROR: No readable text in PDF"
    except Exception as e:
        return f"ERROR: Failed to extract text from PDF - {str(e)}"

# Braille Conversion Function
def text_to_braille(text):
    braille_dict = {
         "a": "⠁", "b": "⠃", "c": "⠉", "d": "⠙", "e": "⠑",
    "f": "⠋", "g": "⠛", "h": "⠓", "i": "⠊", "j": "⠚",
    "k": "⠅", "l": "⠇", "m": "⠍", "n": "⠝", "o": "⠕",
    "p": "⠏", "q": "⠟", "r": "⠗", "s": "⠎", "t": "⠞",
    "u": "⠥", "v": "⠧", "w": "⠺", "x": "⠭", "y": "⠽", "z": "⠵",
    "0": "⠼⠚", "1": "⠼⠁", "2": "⠼⠃", "3": "⠼⠉", "4": "⠼⠙",
    "5": "⠼⠑", "6": "⠼⠋", "7": "⠼⠛", "8": "⠼⠓", "9": "⠼⠊",
    " ": " ", ".": "⠲", ",": "⠂", "?": "⠦", "!": "⠖", "-": "⠤", ":": "⠒",
    "(": "⠷", ")": "⠾", "/": "⠸", "&": "⠡", "$": "⠴", "'": "⠈"
    
    }
    return "".join(braille_dict.get(char, char) for char in text.lower())

# Braille to Text Conversion Function
def braille_to_text(braille_input):
    reverse_dict = {
        "⠁": "a", "⠃": "b", "⠉": "c", "⠙": "d", "⠑": "e",
        "⠋": "f", "⠛": "g", "⠓": "h", "⠊": "i", "⠚": "j",
        "⠅": "k", "⠇": "l", "⠍": "m", "⠝": "n", "⠕": "o",
        "⠏": "p", "⠟": "q", "⠗": "r", "⠎": "s", "⠞": "t",
        "⠥": "u", "⠧": "v", "⠺": "w", "⠭": "x", "⠽": "y", "⠵": "z",
        "⠲": ".", "⠂": ",", "⠦": "?", "⠖": "!", "⠤": "-", "⠒": ":",
        "⠷": "(", "⠾": ")", "⠸": "/", "⠡": "&", "⠴": "$", "⠈": "'",
        " ": " "
    }

    number_map = {
        "⠁": "1", "⠃": "2", "⠉": "3", "⠙": "4", "⠑": "5",
        "⠋": "6", "⠛": "7", "⠓": "8", "⠊": "9", "⠚": "0"
    }

    output = ""
    i = 0
    while i < len(braille_input):
        if braille_input[i] == "⠼" and i + 1 < len(braille_input):
            # Number mode
            i += 1
            if braille_input[i] in number_map:
                output += number_map[braille_input[i]]
            else:
                output += braille_input[i]
        else:
            output += reverse_dict.get(braille_input[i], braille_input[i])
        i += 1

    return output

# Helper function to chunk long text
def chunk_text(text, max_tokens=512, overlap=50):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += max_tokens - overlap  # maintain context overlap
    return chunks

# API route for text summarization
@app.route("/summarize", methods=["POST"]) 
def summarize():
    try:
        print("Received request to /summarize")

        text = ""
        if "file" in request.files and request.files["file"].filename != "":
            file = request.files["file"]
            filename = file.filename
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            if filename.endswith(".txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
            elif filename.endswith(".docx"):
                text = extract_text_from_docx(file_path)
            elif filename.endswith(".pdf"):
                text = extract_text_from_pdf(file_path)
            else:
                return jsonify({"error": "Unsupported file type"}), 400

        elif "text" in request.form and request.form["text"].strip() != "":
            text = request.form["text"]

        if not text.strip():
            return jsonify({"error": "No text content provided"}), 400

        word_count = len(text.split())
        threshold_words = 150

        print(f"Input word count: {word_count}")

        if word_count < threshold_words:
            braille = text_to_braille(text)
            return jsonify({"summary": text, "braille": braille})
        else:
            max_len = min(200, word_count // 2)
            min_len = max(30, word_count // 10)

            # Chunk and summarize
            chunks = chunk_text(text, max_tokens=512, overlap=50)
            summaries = []
            for i, chunk in enumerate(chunks):
                print(f"Summarizing chunk {i+1}/{len(chunks)}")
            chunk_word_count = len(chunk.split())
            max_len = min(200, chunk_word_count // 2)
            min_len = max(30, chunk_word_count // 10)
            print(f"  ⤷ Chunk word count: {chunk_word_count}, min_len: {min_len}, max_len: {max_len}")
            try:
                result = summarizer(chunk, max_length=max_len, min_length=min_len, do_sample=False)
                if result and "summary_text" in result[0]:
                    summaries.append(result[0]["summary_text"])
            except Exception as e:
                print(f"Chunk {i+1} summarization failed:", str(e))

            summary = " ".join(summaries) if summaries else "Summarization failed."
            braille = text_to_braille(summary)
            print("Final summary:", summary[:100])  # Just to verify something is there
            print("Braille output:", braille[:100])

            return jsonify({"summary": summary, "braille": braille})
        


    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500



# API route for text-to-speech conversion
@app.route("/speak", methods=["POST"])
def speak():
    try:
        text = request.json.get("text", "").strip()
        if not text:
            return jsonify({"error": "No text provided"}), 400

        # Generate audio file
        audio_file = os.path.join(AUDIO_FOLDER, "speech.mp3")
        tts = gTTS(text)
        tts.save(audio_file)

        return send_file(audio_file, mimetype="audio/mp3", as_attachment=False)
    

    except Exception as e:
        print("Error in TTS:", str(e))
        return jsonify({"error": str(e)}), 500
    
# Page route
@app.route('/braille-to-text', methods=['GET'])
def braille_to_text_page():
    return render_template("braille-to-text.html")

# JSON endpoint for JS fetch
@app.route('/braille-to-text-json', methods=['POST'])
def braille_to_text_json():
    braille = request.form.get("braille")
    if not braille:
        return jsonify({"error": "No Braille input"}), 400
    try:
        text = braille_to_text(braille)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/text-to-braille", methods=["GET", "POST"])
def text_to_braille_route():
    if request.method == "POST":
        input_text = request.form.get("text", "").strip()
        if not input_text:
            return render_template("text-to-braille.html", output="Please enter text to convert.", input=input_text)

        braille_output = text_to_braille(input_text)
        return render_template("text-to-braille.html", output=braille_output, input=input_text)

    return render_template("text-to-braille.html")

# API route for Braille to Text conversion

if __name__ == '__main__':
    app.run(debug=True)
