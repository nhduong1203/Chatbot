import streamlit as st
from PIL import Image

# Set page configuration
st.set_page_config(
    page_title="Welcome to Your Chatbot!",
    page_icon="🤖",
    layout="centered"
)

# cute_icon_url = "https://www.clipartmax.com/png/middle/309-3095255_chatbot-png-vector-icon-chatbot-icon-png.png"  # Example URL
# st.image(cute_icon_url, width=150)

# Title and welcome message
st.title("🌟 Welcome to Your Chatbot! 🌟")
st.subheader("Here to brighten your day and assist you with anything you need!")

# Positive energy quote or message
st.write("""
> "The only limit to our realization of tomorrow is our doubts of today." – Franklin D. Roosevelt

Feel free to ask me anything, and let's make every interaction meaningful!
""")

# Start button
import shutil
import os

page_name = st.text_input("New Conversation Name")
# Button to start a new chat
if st.button("✨ Start New Chatting Now! ✨"):
    if page_name.strip():  # Check if the input is not empty or just whitespace
        # Define file paths
        template_file = "Conversation-Template.py"
        new_file_path = f"pages/{page_name}.py"

        # Ensure the pages directory exists
        os.makedirs("pages", exist_ok=True)

        try:
            # Copy the template to the new file
            shutil.copy(template_file, new_file_path)
            st.success(f"Chat session '{page_name}' created successfully! File saved to {new_file_path}.")
        except Exception as e:
            st.error(f"An error occurred while creating the chat session: {e}")
    else:
        st.error("Please enter a valid conversation name before starting.")

# Footer
st.write("---")
st.markdown(
    """
    **Made with ❤️ by [Levi]**
    """
)
