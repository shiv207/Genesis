import streamlit as st
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
from groq import Groq

# Replace with your actual keys
API_KEY = "AIzaSyDHyK7T14VG8vMwaJhQicBRovAb76dkdxk"
SEARCH_ENGINE_ID = "d6604d6b7dbb9447a"
GROQ_API_KEY = "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"

groq_client = Groq(api_key=GROQ_API_KEY)

def search_images(query, num_images=7):
    service = build("customsearch", "v1", developerKey=API_KEY)
    try:
        res = service.cse().list(
            q=query,
            cx=SEARCH_ENGINE_ID,
            searchType='image',
            num=num_images
        ).execute()
        return [item['link'] for item in res.get('items', [])]
    except Exception as e:
        st.error(f"Error fetching images: {e}")
        return []

def get_brief_description(query):
    prompt = f"Tell me a 10-line description of the object '{query}'. Do not describe the query itself, but describe the object that was asked about in the query."
    
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides brief descriptions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Error fetching description from Groq: {e}")
        return "No description found."

def apply_custom_css():
    custom_css = """
    <style>
        /* Chat message styling */
        .stChatMessage {
            border-radius: 20px;
            padding: 12px 18px;
            margin-bottom: 20px;
            max-width: 75%;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            background-color: rgba(255, 255, 255, 0.05) !important;
        }

        /* Image scrape styling */
        .message.img-scrape {
            background-color: rgba(34, 34, 34, 0.95);
            background-image: url('Backend/texture/grainy-texture.png');
            border: 2px solid #555;
            color: #eaeaea;
            font-weight: 400;
            font-size: 14px;
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        /* Image display columns */
        .stImage img {
            border-radius: 15px;
            filter: brightness(0.8) contrast(1.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            max-width: 100%;
            height: auto;
        }

        .stImage img:hover {
            transform: scale(1.03);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }

        /* Scrollable chat UI */
        .stChatBox {
            max-height: 60vh;
            overflow-y: auto;
        }

        /* Input text box */
        .stTextInput input {
            width: 100%;
            padding: 10px 15px;
            background: rgba(50, 50, 50, 0.8);
            border: none;
            color: white;
            border-radius: 20px;
            outline: none;
            font-size: 16px;
        }

        .stTextInput input:focus {
            box-shadow: 0 0 0 2px rgba(30, 136, 229, 0.2);
        }

        /* Light theme */
        @media (prefers-color-scheme: light) {
            body {
                background-color: #ffffff;
                color: #000000;
            }

            .stChatMessage {
                background-color: #f0f0f0 !important;
                color: #000000;
            }

            .message.img-scrape {
                background-color: rgba(240, 240, 240, 0.95);
                background-image: url('Backend/texture/light-grainy-texture.png');
                border: 2px solid #cccccc;
                color: #333333;
            }

            .stTextInput input {
                background: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
            }
        }

        /* Responsive design for smaller screens */
        @media (max-width: 768px) {
            .stChatMessage {
                max-width: 90%;
                padding: 10px 15px;
                font-size: 14px;
            }

            .message.img-scrape {
                font-size: 13px;
                padding: 12px;
            }

            .stImage img {
                border-radius: 10px;
            }

            .stTextInput input {
                font-size: 14px;
                padding: 8px 12px;
            }

            .stChatBox {
                max-height: 70vh;
            }
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def handle_image_search_and_description(query: str, num_images=7):
    apply_custom_css()
    
    # Get brief description from Groq
    description = get_brief_description(query)
    
    # Search for images
    image_urls = search_images(query, num_images)
    
    # Prepare output
    output = {
        "description": description,
        "images": image_urls
    }
    
    return output

def process_image_query(query: str):
    result = handle_image_search_and_description(query)
    
    # Apply grainy background to the chat response
    response = f'''
    <div class="stChatMessage message img-scrape">
        <strong>Brief description:</strong> {result["description"]}
    </div>
    '''
    
    st.markdown(response, unsafe_allow_html=True)
    
    if result['images']:
        cols = st.columns(3)
        for i, img_url in enumerate(result['images'][:3]):  # Limit to 3 images
            with cols[i % 3]:
                st.image(img_url, use_column_width=True)
    else:
        st.markdown('<div class="stChatMessage message img-scrape">No images found for the given query.</div>', unsafe_allow_html=True)
    
    return response

# This function would be called by the main chatbot logic
def handle_image_search(query: str):
    return process_image_query(query)