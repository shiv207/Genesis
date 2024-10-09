import logging
from deepgram import DeepgramClient, SpeakOptions
import streamlit as st
import os
import tempfile
import base64

def text_to_speech_deepgram(text: str):
    API_KEY = "deepgram_api_key" #put your deepgram api key here

    try:
        client = DeepgramClient(api_key=API_KEY)
        options = SpeakOptions(
            model="aura-stella-en",
            encoding="linear16",
            container="wav",
            sample_rate=48000
        )

        SPEAK_OPTIONS = {"text": text}

        # Use a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_filename = temp_file.name
            response = client.speak.v("1").save(temp_filename, SPEAK_OPTIONS, options)
        
        logging.info(f"Successfully generated speech and saved to temporary file")
        return temp_filename  # Return the temporary file path
        
    except Exception as e:
        logging.error(f"Failed to convert text to speech using Deepgram: {e}")
        return None

def say(text: str):
    audio_file = text_to_speech_deepgram(text)
    
    if audio_file and os.path.exists(audio_file):
        try:
            # Read the audio file as binary data
            with open(audio_file, "rb") as file:
                audio_bytes = file.read()
            
            # Encode the audio bytes to base64
            audio_base64 = base64.b64encode(audio_bytes).decode()
            
            # Create an HTML audio element with autoplay
            audio_html = f'''
                <audio autoplay="true">
                    <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                    Your browser does not support the audio element.
                </audio>
            '''
            
            # Display the audio using HTML
            st.markdown(audio_html, unsafe_allow_html=True)
            
            logging.info(f"Successfully streamed audio from temporary file")
            
            # Clean up the temporary file
            os.unlink(audio_file)
        except Exception as e:
            logging.error(f"Failed to stream audio: {e}")
    else:
        logging.error("No audio file generated to stream")