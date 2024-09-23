import streamlit as st
from pathlib import Path
from faster_whisper import WhisperModel
import speech_recognition as sr
import cv2
import time
from Features.voice import say
from vision import vision_prompt, take_screenshot, web_cam_capture
import os
import re
import logging
from requests.exceptions import RequestException, Timeout
import threading
from Features.flux_dev import generate_image_dev
from groq import Groq
from Features.flux_dreamscape import generate_image_dreamscape
from Features.flux_oilscape import generate_image_oilscape
import random
from Features.img_scrape import handle_image_search
import requests
import base64
from PIL import Image
import io

# Initialize API clients
wake_word = ['optimus','jarvis','hal','siri','gemini', 'billie']

groq_client = Groq(api_key='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')

st.set_page_config(page_title="Optimus", layout="wide", page_icon="Images/avatar/neura.png")

# System message and configuration
sys_msg = (
    'You are a multi-modal AI voice assistant. Your user may or may not have attached a photo for context '
    '(either a screenshot or a webcam capture). Any photo has already been processed into a highly detailed '
    'text prompt that will be attached to their transcribed voice prompt. Generate the most useful and '
    'factual response possible, carefully considering all previous generated text in your response before '
    'adding new tokens to the response. Do not expect or request images, just use the context if added. '
    'Use all of the context of this conversation so your response is relevant to the conversation. Make '
    'your responses clear and concise, avoiding any verbosity.'
)

convo = [{'role': 'system', 'content': sys_msg}]

num_cores = os.cpu_count()
whisper_size = 'base'
Whisper_model = WhisperModel(
    whisper_size, 
    device='cpu',
    compute_type='int8',
    cpu_threads=num_cores //2,
    num_workers=num_cores //2
)

r = sr.Recognizer()
source = sr.Microphone()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def groq_prompt(prompt, img_context=None, timeout=30):
    try:
        if img_context:
            prompt = f'USER PROMPT: {prompt}\n\n   IMAGE CONTEXT: {img_context}'
        convo.append({'role': 'user', 'content': prompt})
        
        logger.info(f"Sending request to Groq API with prompt: {prompt}")
        
        chat_completion = groq_client.chat.completions.create(
            messages=convo, 
            model='mixtral-8x7b-32768',
            timeout=timeout
        )
        
        if not chat_completion.choices:
            logger.warning("No choices returned from Groq API")
            return "I'm sorry, I couldn't generate a response. Please try again."
        
        response = chat_completion.choices[0].message.content
        convo.append({'role': 'assistant', 'content': response})

        logger.info(f"Received response from Groq API: {response}")

        return response
    except Timeout:
        logger.error("Timeout occurred while calling Groq API")
        return "I'm sorry, the request timed out. Please try again later."
    except RequestException as e:
        logger.error(f"Request exception occurred: {str(e)}")
        return "I'm sorry, there was an error with the request. Please try again later."
    except Exception as e:
        logger.error(f"Error in groq_prompt: {str(e)}")
        raise

def function_call(prompt):
    function_sys_msg = (
        'You are an AI function calling model. You will determine the most appropriate function to call based on the user\'s prompt. '
        'Available functions are:\n'
        '1. "take screenshot": For requests to take a screenshot.\n'
        '2. "capture webcam": For requests to capture from the webcam. The webcam can be assumed to be a normal laptop webcam facing the user.\n'
        '3. "generate_image": For requests to generate an image, create artwork, or produce visual content.\n'
        '4. "search_images": For requests to search for existing images or pictures.\n'
        '5. "None": For general conversation or tasks not related to the above functions.\n'
        'Respond with only one selection from this list: ["take screenshot", "capture webcam", "generate_image", "search_images", "None"]\n'
        'Do not respond with anything but the most logical selection from that list with no explanations. Format the '
        'function call name exactly as listed.'
    )

    function_convo = [{'role': 'system', 'content': function_sys_msg},
                      {'role': 'user', 'content': prompt}]
    
    chat_completion = groq_client.chat.completions.create(messages=function_convo, model='Llama3-70b-8192')
    response = chat_completion.choices[0].message.content.strip()

    if not response:
        return {"function": "None", "parameters": {}}

    return {"function": response, "parameters": {}}

def wav_to_text(audio_path):
    segments, _ = Whisper_model.transcribe(audio_path)
    text = ''.join(segment.text for segment in segments)
    print("Full Transcription:", text)  # Debugging
    return text

def extract_prompt(transcribed_text, wake_word):
    pattern = rf'\b{re.escape(wake_word)}[\s,.?!]*(.*)'
    match = re.search(pattern, transcribed_text, re.IGNORECASE)

    if match:
        prompt = match.group(1).strip()
        return prompt
    else:
        return None

def update_ui_with_voice_input(prompt, response):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": response})

def callback(recognizer, audio):
    prompt_audio_path = 'Backend/prompt.wav'
    with open(prompt_audio_path, 'wb') as f:
        f.write(audio.get_wav_data())

    prompt_text = wav_to_text(prompt_audio_path)
    clean_prompt = extract_prompt(prompt_text, wake_word)

    if clean_prompt:
        print(f'USER : {clean_prompt}')
        call = function_call(clean_prompt)
        
        if call["function"] == "take screenshot":
            print('Taking screenshot')
            take_screenshot()
            vision_context = vision_prompt(prompt=clean_prompt, photo_path='Images/backend/screenshot.jpg')
        
        elif call["function"] == "capture webcam":
            print('Capturing webcam...')
            web_cam_capture()
            vision_context = vision_prompt(prompt=clean_prompt, photo_path='Images/backend/webcam.jpg')
        
        else:
            vision_context = None
            response = groq_prompt(prompt=clean_prompt, img_context=vision_context)
        
        print(f'optimus : {response}')
        say(response) 
        
        # Update Streamlit UI
        st.session_state.voice_input = (clean_prompt, response)

def start_listening():
    try:
        with source as s:
            r.adjust_for_ambient_noise(s, duration=2)
        print('\nSay ', wake_word, 'followed with your prompt. \n')
        r.listen_in_background(source, callback)
    except Exception as e:
        print(f"Error in start_listening: {str(e)}")

def generate_image(prompt):

    dreamscape_styles = ['dreamscape', 'anime', 'ghibli']
    oilscape_styles = ['van gogh', 'painting', 'oil painting']
    
    prompt_lower = prompt.lower()
    
    try:
        if any(style in prompt_lower for style in dreamscape_styles):
            if not any(style in prompt_lower for style in ['dreamscape style', 'anime style', 'ghibli style']):
                prompt += " in dreamscape style"
            result = generate_image_dreamscape(prompt)
        elif any(style in prompt_lower for style in oilscape_styles):
            if 'oil painting style' not in prompt_lower:
                prompt += " in oil painting style"
            result = generate_image_oilscape(prompt)
        else:
            result = generate_image_dev(prompt)
        
        if result.startswith("Error:"):
            return result 
        else:
            return result  
    except Exception as e:
        return f"Error: Failed to generate image. {str(e)}"

def add_fixed_grid():
    grid_svg = """
    <div class="fixed-grid">
        <svg width="3476" height="300" viewBox="0 0 3476 757" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2156.11 755L1320.78 755L-491 -3.00003L3966 -3.00003L2156.11 755Z" stroke="url(#paint0_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M3375.03 244.918L101.863 244.918" stroke="url(#paint1_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M3031.88 388.513L445.018 388.513" stroke="url(#paint2_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2807.67 482.352L669.217 482.352" stroke="url(#paint3_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2649.74 548.428L827.154 548.428" stroke="url(#paint4_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2532.41 597.508L944.494 597.508" stroke="url(#paint5_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2441.91 635.412L1034.99 635.412" stroke="url(#paint6_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2369.91 665.555L1106.99 665.555" stroke="url(#paint7_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2311.26 690.091L1165.63 690.091" stroke="url(#paint8_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2262.59 710.43L1214.3 710.43" stroke="url(#paint9_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2221.55 727.62L1255.35 727.62" stroke="url(#paint10_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2186.46 742.316L1290.43 742.316" stroke="url(#paint11_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1390.39 755L-117.832 -2.35765" stroke="url(#paint12_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1460 755L253.391 -2.35765" stroke="url(#paint13_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1529.61 755L624.668 -2.35765" stroke="url(#paint14_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1599.22 755L995.945 -2.35765" stroke="url(#paint15_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1668.83 755L1367.17 -2.35765" stroke="url(#paint16_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1738.45 755V-2.35765" stroke="url(#paint17_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1808.05 755L2109.72 -2.35765" stroke="url(#paint18_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1877.67 755L2480.95 -2.35765" stroke="url(#paint19_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M1947.28 755L2852.22 -2.35765" stroke="url(#paint20_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2016.89 755L3223.5 -2.35765" stroke="url(#paint21_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <path d="M2086.5 755L3594.73 -2.35765" stroke="url(#paint22_linear_74_1233)" stroke-width="3" stroke-linejoin="round"/>
        <defs>
        <linearGradient id="paint0_linear_74_1233" x1="3966" y1="376" x2="-491" y2="376" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint1_linear_74_1233" x1="3375.03" y1="244.418" x2="101.863" y2="244.418" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint2_linear_74_1233" x1="3031.88" y1="388.013" x2="445.018" y2="388.013" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint3_linear_74_1233" x1="2807.67" y1="481.852" x2="669.217" y2="481.852" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint4_linear_74_1233" x1="2649.74" y1="547.928" x2="827.154" y2="547.928" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint5_linear_74_1233" x1="2532.41" y1="597.008" x2="944.494" y2="597.008" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint6_linear_74_1233" x1="2441.91" y1="634.912" x2="1034.99" y2="634.912" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint7_linear_74_1233" x1="2369.91" y1="665.055" x2="1106.99" y2="665.055" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint8_linear_74_1233" x1="2311.26" y1="689.591" x2="1165.63" y2="689.591" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint9_linear_74_1233" x1="2262.59" y1="709.93" x2="1214.3" y2="709.93" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint10_linear_74_1233" x1="2221.55" y1="727.12" x2="1255.35" y2="727.12" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint11_linear_74_1233" x1="2186.46" y1="741.816" x2="1290.43" y2="741.816" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint12_linear_74_1233" x1="1390.39" y1="376.321" x2="-117.832" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint13_linear_74_1233" x1="1460" y1="376.321" x2="253.391" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint14_linear_74_1233" x1="1529.61" y1="376.321" x2="624.668" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint15_linear_74_1233" x1="1599.22" y1="376.321" x2="995.945" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint16_linear_74_1233" x1="1668.83" y1="376.321" x2="1367.17" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint17_linear_74_1233" x1="1738.45" y1="376.321" x2="1737.45" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint18_linear_74_1233" x1="2109.72" y1="376.321" x2="1808.05" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint19_linear_74_1233" x1="2480.95" y1="376.321" x2="1877.67" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint20_linear_74_1233" x1="2852.22" y1="376.321" x2="1947.28" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint21_linear_74_1233" x1="3223.5" y1="376.321" x2="2016.89" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        <linearGradient id="paint22_linear_74_1233" x1="3594.73" y1="376.321" x2="2086.5" y2="376.321" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="#999999"/>
        </linearGradient>
        </defs>
        </svg>
    </div>

    <style>
    .fixed-grid {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 30vh;
        overflow: hidden;
        z-index: 0;
        pointer-events: none;
    }
    .fixed-grid svg {
        width: 100%;
        height: 100%;
        opacity: 0.3;
    }
    /* Ensure the chat container has a higher z-index */
    .stChatFloatingInputContainer {
        z-index: 1;
        position: relative;
        background-color: transparent !important;
    }
    </style>
    """
    st.markdown(grid_svg, unsafe_allow_html=True)

def load_css(file_name):
    with open(file_name) as f:
        return f'<style>{f.read()}</style>'

def streamlit_ui():
    # Load CSS from external file
    st.markdown(load_css('style.css'), unsafe_allow_html=True)
    
    # Add the grid
    add_fixed_grid()

    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "How may I help you?"}]
    if 'voice_input' not in st.session_state:
        st.session_state.voice_input = None

    # Header Section
    st.markdown('<div class="header-container">', unsafe_allow_html=True)
    st.markdown('<div class="header-content">', unsafe_allow_html=True)
    st.markdown('<h1>Optimus</h1>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True) 

    # Chat container
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="Images/avatar/avatar.png" if msg["role"] == "assistant" else None):
            if "content" in msg:
                st.write(msg["content"])
            if "image_path" in msg:
                st.image(msg["image_path"], use_column_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Chat input and paperclip button container
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    
    # Chat input
    prompt = st.chat_input("Ask Optimus something", key="chat_input")

    # Handle new user input
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Generate assistant response
        with st.chat_message("assistant", avatar="Images/avatar/avatar.png"):
            with st.spinner("Thinking..."):
                try:
                    function_result = function_call(prompt)
                    
                    if function_result["function"] == "take screenshot":
                        take_screenshot()
                        
                        vision_context = vision_prompt(prompt=prompt, photo_path='Images/backend/screenshot.jpg')
                        if vision_context.startswith("Error: No image file found"):
                            response = "I'm sorry, but I couldn't find the screenshot image. Let me answer your question without visual context."
                            response += groq_prompt(prompt=prompt)
                        elif vision_context.startswith("Error"):
                            st.error(vision_context)
                            response = f"I'm sorry, but I encountered an error while analyzing the image: {vision_context}"
                        else:
                            response = groq_prompt(prompt=prompt, img_context=vision_context)
                    
                    elif function_result["function"] == "capture webcam":
                        st.write("Capturing from webcam...")
                        image_path = web_cam_capture()
                        if image_path.startswith("Error:"):
                            st.error(image_path)
                            response = f"I'm sorry, but I encountered an error while trying to capture from the camera: {image_path}"
                        else:
                            st.success("Photo captured successfully!")
                            vision_context = vision_prompt(prompt=prompt, photo_path=image_path)
                            if vision_context.startswith("Error: No image file found"):
                                response = "I'm sorry, but I couldn't find the captured image. Let me answer your question without visual context."
                                response += groq_prompt(prompt=prompt)
                            elif vision_context.startswith("Error"):
                                st.error(vision_context)
                                response = f"I'm sorry, but I encountered an error while analyzing the image: {vision_context}"
                            else:
                                response = groq_prompt(prompt=prompt, img_context=vision_context)

                    elif function_result["function"] == "generate_image":
                        result = generate_image(prompt)

                        if result.startswith("Error:"):
                            st.error(result)
                            response = f"I'm sorry, but I encountered an error while trying to generate the image: {result}"
                        else:
                            try:
                                st.image(result, caption="Generated Image", use_column_width=True)
                                st.write("Voilà ✨ Your AI-crafted masterpiece is ready!")
                                response = ''

                            except Exception as e:
                                st.error(f"Error displaying the image: {e}")
                                response = f"Error displaying the image: {e}"
                            
                    elif function_result["function"] == "search_images":
                        images = handle_image_search(prompt)
                        
                        if images:
                            for img in images[:3]:  # Limit to 3 images
                                try:
                                    st.image(img, use_column_width=True)
                                except Exception as e:
                                    return None
                            response = "Images found and displayed."
                        else:
                            st.write("No images found.")
                            response = "No images found."
                    else:
                        response = groq_prompt(prompt=prompt)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.write(response)
                    say(response)
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    response = f"I'm sorry, but an error occurred: {str(e)}"
                    st.session_state.messages.append({"role": "assistant", "content": response})

def main():
    threading.Thread(target=start_listening, daemon=True).start()
    
    # Run the Streamlit UI
    streamlit_ui()

if __name__ == "__main__":
    main()









    