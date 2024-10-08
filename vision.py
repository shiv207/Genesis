import cv2
import os
import google.generativeai as genai
import time
from PIL import Image, ImageGrab
import streamlit as st

# Configure the Generative AI model
genai.configure(api_key='')

generation_config = {
    'temperature': 0.7,
    'top_p': 1,
    'top_k': 1,
    'max_output_tokens': 2048
}

safety_settings = [
  {
    'category': 'HARM_CATEGORY_HARASSMENT',
    'threshold': 'BLOCK_NONE'
  },
  {
    'category': 'HARM_CATEGORY_HATE_SPEECH',
    'threshold': 'BLOCK_NONE'
  },
  {
    'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
    'threshold': 'BLOCK_NONE'
  },
  {
    'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
    'threshold': 'BLOCK_NONE'
  },
]

model = genai.GenerativeModel(model_name='gemini-1.5-flash',
                              generation_config=generation_config,
                              safety_settings=safety_settings)

def take_screenshot():
    path = 'Images/backend/screenshot.jpg'
    screenshot = ImageGrab.grab()
    rgb_screenshot = screenshot.convert('RGB')
    rgb_screenshot.save(path)

def web_cam_capture():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Error: Could not open webcam"

    # Set the resolution to 1280x720 (HD)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    ret, frame = cap.read()
    if not ret:
        return "Error: Could not read frame from webcam"

    image_path = 'Images/backend/webcam.jpg'
    cv2.imwrite(image_path, frame)
    cap.release()
    return image_path

def vision_prompt(prompt, photo_path):
    try:
        if not os.path.exists(photo_path):
            return "Error: No image file found. Unable to process visual context."

        img = Image.open(photo_path)
        
        # Prepare the vision prompt text
        vision_prompt_text = (
            'You are the vision analysis AI that provides semantic meaning from images to provide context '
            'to send to another AI that will create a response to the user. Do not respond as the AI assistant '
            'to the user. Instead, take the user prompt input and try to extract all the meaning from the photo '
            'relevant to the user prompt. Then generate as much objective data about the image for the AI '
            f'assistant who will respond to the user. \nUSER PROMPT: {prompt}'
        )

        # Ensure both the prompt and image are sent as strings
        response = model.generate_content([vision_prompt_text, img])
        return response.text
    except Exception as e:
        return f"Error in vision_prompt: {str(e)}"
