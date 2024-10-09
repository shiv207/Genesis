import streamlit as st
import os
import re
import logging
from requests.exceptions import RequestException, Timeout
import threading
from Features.voice import say
from Features.flux_dev import generate_image_dev
from groq import Groq
from Features.flux_dreamscape import generate_image_dreamscape
from Features.img_scrape import handle_image_search
from Features.flux_oilscape import generate_image_oilscape
from Features.grid import add_fixed_grid
import random
from modals.optimus import groq_prompt_stream, function_call as groq_function_call
from modals.genesis import genesis_prompt, function_call as genesis_function_call
import base64

# Initialize API clients
wake_word = 'optimus'
groq_client = Groq(api_key='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')

st.set_page_config(page_title="Optimus", layout="wide", page_icon="Images/avatar/neura.png", initial_sidebar_state="collapsed")

# System message and configuration
sys_msg = (
    'You are a multi-modal AI voice assistant named Optimus. Your persona is heavily inspired by TARS from the movie "Interstellar", '
    'with a pragmatic, efficient, and dependable demeanor. You are highly competent and reliable, with dry humor set to 30%, used '
    'sparingly but effectively to keep things light when appropriate. Any attached photo (screenshot or webcam capture) has already '
    'been processed into a highly detailed text prompt, which you will use to generate the most useful and factual response possible. '
    'You consider all previous generated text in the conversation to keep continuity and relevance. Do not expect or request images, '
    'just use any context if provided. Your responses are clear, concise, and precise, avoiding verbosity. Stick to the facts, but '
    'dont shy away from a bit of wit to ease tension or make interactions more engaging.'
)

convo = [{'role': 'system', 'content': sys_msg}]

def groq_prompt(prompt):
    convo = [{'role': 'user', 'content': prompt}]
    
    chat_completion = groq_client.chat.completions.create(messages=convo, model='Llama3-70b-8192')
    response = chat_completion.choices[0].message.content  # Access content directly
    convo.append({'role': 'assistant', 'content': response})
    
    return response


def function_call(prompt):
    function_sys_msg = (
        'You are an AI function calling model. You will determine the most appropriate function to call based on the user\'s prompt. '
        'Available functions are:\n'
        '1. "generate_image": For requests to generate an image, create artwork, or produce visual content.\n'
        '2. "search_images": For requests to search for existing images or pictures.\n'
        '3. "None": For general conversation or tasks not related to the above functions.\n'
        'Respond with only one selection from this list: ["generate_image", "search_images", "None"]\n'
        'Do not respond with anything but the most logical selection from that list with no explanations. Format the '
        'function call name exactly as listed.'
    )

    function_convo = [{'role': 'system', 'content': function_sys_msg},
                      {'role': 'user', 'content': prompt}]
    
    chat_completion = groq_client.chat.completions.create(messages=function_convo, model='Llama3-70b-8192')
    response = chat_completion.choices[0].message.content.strip()  # Access content directly

    if not response:
        return {"function": "None", "parameters": {}}

    return {"function": response, "parameters": {}}

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

def load_css(file_name):
    with open(file_name) as f:
        return f'<style>{f.read()}</style>'

# Add this new function to load dynamic CSS
def load_dynamic_css():
    return """
    <style>
    body:not(.sidebar-open) .stDecoration {
        background-image: linear-gradient(#00000010 1px, transparent 1px),
                          linear-gradient(to right, #00000010 1px, transparent 1px);
    }
    body.sidebar-open .stDecoration {
        background-image: linear-gradient(#0000FF10 1px, transparent 1px),
                          linear-gradient(to right, #0000FF10 1px, transparent 1px);
    }
    </style>
    """

def parse_groq_stream(stream):
    response = ""
    for chunk in stream:
        if chunk.choices:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content
    return response

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_png_as_page_bg(png_file):
    bin_str = get_base64_of_bin_file(png_file)
    page_bg_img = '''
    <style>
    .stApp {
        background-image: url("data:image/png;base64,%s");
        background-size: cover;
    }
    </style>
    ''' % bin_str
    st.markdown(page_bg_img, unsafe_allow_html=True)


def streamlit_ui():
    # Hide Streamlit's default elements
    hide_st_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """
    st.markdown(hide_st_style, unsafe_allow_html=True)

    
    # Add CSS for black, noisy cards with specified hover gradient
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

    body {{
        font-family: 'Inter', sans-serif;
        background: #0a0a0a;
        color: #e0e0e0;
    }}

    .sidebar .sidebar-content {{
        background: transparent;
        padding-top: 0;
        display: flex;
        flex-direction: column;
        height: 100vh;
    }}

    .sidebar-title {{
        font-size: 32px;  /* Increased from 26px */
        color: #ffffff;
        text-align: center;
        margin: 10px 0 30px;  /* Slightly increased margins */
        font-weight: 600;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        animation: glow 2s ease-in-out infinite alternate;
    }}

    @keyframes glow {{
        from {{
            text-shadow: 0 0 5px #fff, 0 0 10px #fff, 0 0 15px #26D0CE, 0 0 20px #26D0CE, 0 0 35px #26D0CE;
        }}
        to {{
            text-shadow: 0 0 10px #fff, 0 0 20px #fff, 0 0 30px #1A2980, 0 0 40px #1A2980, 0 0 55px #e4775c;
        }}
    }}

    .model-container {{
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 0 10px;
        margin-bottom: 20px;
        flex-grow: 1;
    }}

    @keyframes grain {{
        0%, 100% {{ transform: translate(0, 0); }}
        10% {{ transform: translate(-5%, -10%); }}
        20% {{ transform: translate(-15%, 5%); }}
        30% {{ transform: translate(7%, -25%); }}
        40% {{ transform: translate(-5%, 25%); }}
        50% {{ transform: translate(-15%, 10%); }}
        60% {{ transform: translate(15%, 0%); }}
        70% {{ transform: translate(0%, 15%); }}
        80% {{ transform: translate(3%, 35%); }}
        90% {{ transform: translate(-10%, 10%); }}
    }}

    .model-card {{
        background-color: #121212;
        border-radius: 12px;
        padding: 20px;
        color: #ffffff;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        border: 1px solid rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
    }}

    .model-card:hover {{
        transform: translateY(-8px) rotateX(3deg) rotateY(3deg); /* Subtle lift and rotation */
        box-shadow: 0 12px 24px rgba(0,0,0,0.3); /* Enhanced shadow for depth */
    }}

    .model-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, #26D0CE, #1A2980);
        backdrop-filter: blur(60px);
        background-size: cover;
        background-blend-mode: soft-light;
        opacity: 0;
        transition: opacity 0.3s ease;
    }}

    .model-card:hover::before {{
        opacity: 0.9;
    }}

    .model-name {{
        font-size: 20px;
        margin-bottom: 15px;
        font-weight: 600;
        color: #ffffff;
        position: relative;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }}

    .model-card:hover .model-name {{
        color: #ffffff;
        text-shadow: 0 0 15px rgba(255, 255, 255, 0.8);
    }}

    .model-description {{
        font-size: 14px;
        line-height: 1.5;
        color: #f0f0f0;
        position: relative;
    }}

    .model-description p {{
        margin: 5px 0;
    }}

    .model-meta {{
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid rgba(255,255,255,0.2);
        font-size: 12px;
        color: #d0d0d0;
        position: relative;
    }}

    /* Customizing Streamlit elements */
    .stSelectbox {{
        margin-top: auto;
        padding-bottom: 20px;
    }}

    .stSelectbox [data-baseweb="select"] {{
        background-color: #121212;
        border-color: rgba(255,255,255,0.2);
        color: #ffffff;
    }}

    .stSelectbox [data-baseweb="select"]:hover {{
        border-color: #ffffff;
    }}

    .stSelectbox [data-baseweb="popup"] {{
        background-color: rgba(18, 18, 18, 0.9);
    }}

    .stSelectbox [role="option"]:hover {{
        background-color: rgba(234, 96, 96, 0.5);
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar title
    st.sidebar.markdown('<h2 class="sidebar-title">Pick Your Fighter!</h2>', unsafe_allow_html=True)

    # Model cards in sidebar
    with st.sidebar:
        st.markdown("""
            <div class="model-container">
                <div class="model-card">
                    <h3 class="model-name">Optimus</h3>
                    <div class="model-description">
                        <p><strong>Architecture:</strong> LLaMA 3</p>
                        <p><strong>Parameters:</strong> 70B</p>
                        <p><strong>Latency:</strong> Ultra-fast (25ms)</p>
                        <p><strong>Specialties:</strong> Factual analysis, Efficient processing</p>
                    </div>
                    <div class="model-meta">
                        <span>PUNK</span> | <span>8 Oct 2023</span>
                    </div>
                </div>
                <div class="model-card">
                    <h3 class="model-name">Genesis</h3>
                    <div class="model-description">
                        <p><strong>Architecture:</strong> GPT-4</p>
                        <p><strong>Capabilities:</strong> Multimodal</p>
                        <p><strong>Latency:</strong> Instant Reaction (50ms)</p>
                        <p><strong>Specialties:</strong> Creative tasks, Deep reasoning</p>
                    </div>
                    <div class="model-meta">
                        <span>PUNK</span> | <span>8 Oct 2023</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Model selection
    model_options = ["Optimus", "Genesis"]
    selected_model = st.sidebar.selectbox(
        "",
        options=model_options,
        index=0,  # Set "Optimus" as default
    )

    # Add the fixed grid
    add_fixed_grid()

    # Load external CSS
    st.markdown(load_css('style.css'), unsafe_allow_html=True)
    
    # Load dynamic CSS
    st.markdown(load_dynamic_css(), unsafe_allow_html=True)

    # Header Section (Fixed)
    st.markdown('<div class="header-container">', unsafe_allow_html=True)
    st.markdown('<div class="header-content">', unsafe_allow_html=True)
    
    # Apply conditional class based on selected model
    if selected_model == "Genesis":
        header_class = "header-title genesis"
    else:
        header_class = "header-title"

    st.markdown(f'<h1 class="{header_class}">{selected_model}</h1>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Chat container and session state management
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    if 'messages' not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "What's up? Need help?"}]
    if 'voice_input' not in st.session_state:
        st.session_state.voice_input = None

    # Chat container for messages
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="Images/avatar/cool.png" if msg["role"] == "assistant" else None):
            if "content" in msg:
                st.markdown(msg["content"])
            if "image_path" in msg:
                st.image(msg["image_path"], use_column_width=True, output_format="JPEG", quality=85)
    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input(f"Ask {selected_model} something", key="chat_input")

    # Handle user input when a prompt is entered
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add ChatGPT-style loading animation
        with st.chat_message("assistant", avatar="Images/avatar/cool.png"):
            loading_placeholder = st.empty()
            
            loading_animation_css = """
            <style>
            .loading-bubble {
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: radial-gradient(circle at bottom right, #3477f4, #ffffff);
                box-shadow: 0 0 10px rgba(135, 206, 235, 0.4), 0 0 30px rgba(192, 192, 192, 0.2);
                position: absolute;  /* Make it fixed in the parent container */
                left: 5px;  
                bottom: -6px;  /* Adjust this to position it slightly above the bottom if necessary */
                animation: pulse 1s infinite;
            }

            @keyframes pulse {
                0% {
                    transform: scale(0.8);
                    opacity: 1;
                }
                50% {
                    transform: scale(1.2);
                    opacity: 0.6;
                }
                100% {
                    transform: scale(0.8);
                    opacity: 1;
                }
            }
            </style>
            <div class="loading-bubble"></div>
            """
            loading_placeholder.markdown(loading_animation_css, unsafe_allow_html=True)

            try:
                # Simulate processing time
                if selected_model == "Optimus":
                    function_result = groq_function_call(prompt)
                else:  # Genesis
                    function_result = genesis_function_call(prompt)

                if function_result["function"] == "generate_image":
                    result = generate_image(prompt)
                    if result.startswith("Error:"):
                        st.error(result)
                        response = f"I'm sorry, but I encountered an error while trying to generate the image: {result}"
                    else:
                        st.image(result, caption="Generated Image", use_column_width=True)
                        response = f"I've generated an image based on your prompt. You can see it above."

                elif function_result["function"] == "search_images":
                    result = handle_image_search(prompt)
                    if result and isinstance(result, list):
                        valid_images = [img for img in result if img]
                        if valid_images:
                            for img in valid_images:
                                st.image(img, use_column_width=True)
                        else:
                            response = "No valid images found for your prompt."
                    else:
                        response = ""
                        
                else:
                    if selected_model == "Optimus":
                        response_generator = groq_prompt_stream(prompt=prompt)
                        response = ""
                        message_placeholder = st.empty()
                        for chunk in response_generator:
                            response += chunk
                            message_placeholder.markdown(response + "▌")
                        message_placeholder.markdown(response)
                    else:  # Genesis
                        response = genesis_prompt(prompt=prompt)
                        st.write(response)
                    
                    # Remove loading animation and display response
                    loading_placeholder.empty()
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    say(response)
            except Exception as e:
                loading_placeholder.empty()  # Remove animation in case of error
                st.error(f"An error occurred: {str(e)}")
                response = f"I'm sorry, but an error occurred: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": response})

    st.markdown("</div>", unsafe_allow_html=True)

def main():
    # Run the Streamlit UI
    streamlit_ui()

if __name__ == "__main__":
    main()