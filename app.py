from flask import Flask, request, jsonify, send_from_directory, send_file
from pathlib import Path
from PyPDF2 import PdfReader
from openai import OpenAI
import os

client = OpenAI(api_key="ADD YOUR KEY HERE")
app = Flask(__name__, static_folder='static')

# Serve the homepage (index.html)
@app.route('/')
def serve_homepage():
    return send_from_directory(app.static_folder, 'index.html')

# Route to serve audio files
@app.route('/audio/<filename>')
def serve_audio(filename):
    audio_directory = Path(__file__).parent
    return send_file(audio_directory / filename, mimetype='audio/mpeg')

# Function to chunk the text
def chunk_text(text, chunk_size=1000):
    chunks = []
    start = 0

    while start < len(text):
        # Find the nearest space or newline character before the chunk limit
        end = start + chunk_size
        if end < len(text):
            while end > start and text[end] not in [' ', '\n']:
                end -= 1
        else:
            end = len(text)  # Last chunk takes the remaining text

        chunks.append(text[start:end].strip())  # Remove any leading/trailing spaces
        start = end

    return chunks

text_chunks = []  # Store chunks globally for current session

# Endpoint to handle TTS requests (only one chunk in advance)
@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    global text_chunks
    data = request.json
    text = data.get('text')
    chunk_index = data.get('chunk_index', 0)

    # Generate chunks if this is the first request or if text has changed
    if not text_chunks:
        text_chunks = chunk_text(text, chunk_size=1000)
        print(f"Total chunks generated: {len(text_chunks)}")

    # Stop if all chunks are done
    if chunk_index >= len(text_chunks):
        return jsonify({'finished': True})

    try:
        chunk = text_chunks[chunk_index]
        print(f"Processing chunk {chunk_index + 1}")

        # Call OpenAI TTS API for this chunk
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=chunk
        )

        audio_file = Path(__file__).parent / f'output_{chunk_index}.mp3'
        with open(audio_file, 'wb') as out_file:
            for data_chunk in response.iter_bytes():
                out_file.write(data_chunk)

        return jsonify({
            'audio_file': f"/audio/output_{chunk_index}.mp3",
            'chunk_text': chunk,  # Send the chunk text to the frontend
            'next_chunk': chunk_index + 1,
            'total_chunks': len(text_chunks)
        })

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint to handle PDF upload and text extraction
@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    try:
        # Extract text from the PDF
        pdf_reader = PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()

        # Return the extracted text
        return jsonify({'text': text})

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
