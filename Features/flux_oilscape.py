import requests
import io
import PIL
from PIL import Image
import streamlit as st
import os
import json

API_URL = "https://api-inference.huggingface.co/models/bingbangboom/flux_oilscape"
headers = {"Authorization": "Bearer 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"}

def query(payload):
	response = requests.post(API_URL, headers=headers, json=payload)
	return response

def apply_custom_css():
    custom_css = """
    <style>
        div[data-testid="stImage"] > img {
            border-radius: 20px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease-in-out;
            max-width: 100%;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def generate_image_oilscape(prompt):
	apply_custom_css()

	print(f"Generating image with prompt: {prompt}")
	
	payload = {
		"inputs": prompt,
		"options": {
			"wait_for_model": True
		}
	}
	
	try:
		response = query(payload)
		
		print(f"Response status code: {response.status_code}")
		print(f"Response headers: {response.headers}")
		
		if response.status_code != 200:
			error_message = f"API request failed with status code {response.status_code}"
			print(error_message)
			return f"Error: {error_message}"

		# Check if the content type is image
		if 'image' in response.headers.get('Content-Type', ''):
			image_bytes = response.content
		else:
			# If it's not an image, it might be an error message in JSON format
			try:
				json_response = response.json()
				print(f"JSON response: {json.dumps(json_response, indent=2)}")
				return f"Error: {json_response.get('error', 'Unexpected JSON response')}"
			except json.JSONDecodeError:
				return f"Error: Unexpected response format"

		image = Image.open(io.BytesIO(image_bytes))
		output_dir = 'Images/flux_images'
		os.makedirs(output_dir, exist_ok=True)
		
		filename = os.path.join(output_dir, "dev.png")

		image.save(filename)
		print(f"Image saved to {filename}")
		return filename  # Return the path to the saved image
	except PIL.UnidentifiedImageError as e:
		print(f"Failed to identify image: {e}")
		debug_filename = 'debug_image_bytes.bin'
		with open(debug_filename, 'wb') as f:
			f.write(image_bytes)
		return f"Error: Failed to identify image. Debug data saved to {debug_filename}"
	except Exception as e:
		print(f"Unexpected error: {e}")
		return f"Error: Unexpected error occurred: {str(e)}"
