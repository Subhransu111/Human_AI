import nltk
import os

# Define the directory to save the data
download_dir = os.path.join(os.path.dirname(__file__), 'nltk_data')

# Create the directory if it doesn't exist
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

# Tell NLTK to use this path
nltk.data.path.append(download_dir)

# Download the vader_lexicon to that specific directory
nltk.download('vader_lexicon', download_dir=download_dir)

print(f"Downloaded 'vader_lexicon' to {download_dir}")