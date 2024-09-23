import asyncio
import edge_tts
from pydub import AudioSegment
import tempfile
import os
import simpleaudio as sa

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
        
        # Load the audio file
        audio = AudioSegment.from_mp3(temp_filename)
        
        # Convert to a format suitable for playback
        samples = audio.get_array_of_samples()
        play_obj = sa.play_buffer(samples, num_channels=audio.channels, 
                                  bytes_per_sample=audio.sample_width, 
                                  sample_rate=audio.frame_rate)

        # Wait until playback is finished
        play_obj.wait_done()

        # Remove the temporary file
        os.unlink(temp_filename)
        
    except Exception as e:
        print(f"An error occurred during text-to-speech conversion: {str(e)}")

def say(text, voice="en-US-SteffanNeural"):
    """
    Wrapper function to call the asynchronous say_async function.
    """
    asyncio.run(say_async(text, voice))
