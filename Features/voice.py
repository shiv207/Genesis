import asyncio
import edge_tts
from pydub import AudioSegment
import tempfile
import os
import pygame

async def say_async(text, voice="en-US-GuyNeural"):
    """
    Convert text to speech asynchronously and play it.
    
    Args:
    text (str): The text to be converted to speech.
    voice (str): The voice to use (default is a male US English voice).
    """
    try:
        # Create a communicate object
        communicate = edge_tts.Communicate(text, voice)
        
        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            temp_filename = temp_audio.name
        
        # Save audio to the temporary file
        await communicate.save(temp_filename)
        
        # Initialize pygame mixer
        pygame.mixer.init()
        
        # Load the audio file
        pygame.mixer.music.load(temp_filename)
        
        # Play the audio
        pygame.mixer.music.play()

        # Wait until playback is finished
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

        # Remove the temporary file
        os.unlink(temp_filename)
        
    except Exception as e:
        print(f"An error occurred during text-to-speech conversion: {str(e)}")

def say(text, voice="en-US-SteffanNeural"):
    """
    Wrapper function to call the asynchronous say_async function.
    """
    asyncio.run(say_async(text, voice))
