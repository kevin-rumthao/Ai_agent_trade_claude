#!/usr/bin/env python3
"""Test Gemini API connection directly."""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Get API key
api_key = os.getenv("GEMINI_API_KEY")

print("=" * 70)
print("Testing Gemini API Connection")
print("=" * 70)
print(f"\nAPI Key: {api_key[:20]}...{api_key[-10:]}")
print()

try:
    import google.generativeai as genai

    print("Configuring Gemini...")
    genai.configure(api_key=api_key)

    print("✅ Configuration successful!")
    print("\nListing available models...")

    # List available models
    models = genai.list_models()
    print("\nAvailable models:")
    for model in models:
        if 'generateContent' in model.supported_generation_methods:
            print(f"  - {model.name}")

    print("\nTesting with gemini-pro-latest model...")
    model = genai.GenerativeModel('gemini-pro-latest')

    response = model.generate_content("Say 'Hello! I am working correctly.' if you can read this.")

    print("✅ Model response received!")
    print(f"\nResponse: {response.text}")

    print("\n" + "=" * 70)
    print("✅ SUCCESS! Gemini API is working correctly!")
    print("=" * 70)

except ImportError as e:
    print(f"❌ Error: google-generativeai not installed")
    print(f"   Run: poetry install")

except Exception as e:
    print(f"❌ Error connecting to Gemini:")
    print(f"   {type(e).__name__}: {e}")
    print(f"\nTroubleshooting:")
    print(f"  1. Verify API key is correct in .env")
    print(f"  2. Check if API key is active at https://aistudio.google.com/app/apikey")
    print(f"  3. Ensure you have internet connectivity")

