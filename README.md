# OSINT Intelligence System

A production-ready OSINT intelligence system with a Streamlit GUI and a modular backend. It integrates with a primary API and falls back to an intelligent OSINT pipeline when results are empty.

## 🚀 Features

- **Multi-Input Search:** Phone, Name, Email, or Image.
- **Smart Fallback:** Automatically triggers OSINT pipeline (Dorking, Social Discovery, Crawling) if the primary API returns no results.
- **Modular Architecture:** Separate modules for crawling, social media discovery, and data analysis.
- **Connection Engine:** Links found entities into a unified graph.
- **Sentiment & Location:** Analyzes text for sentiment and phone numbers for geographical data.
- **Image Intelligence:** Extracts EXIF metadata and provides reverse image search links.

## 🛠️ Setup Instructions

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download NLTK Corpora (for Sentiment Analysis):**
   ```python
   python -m textblob.download_corpora
   ```

## ▶️ Running the Application

```bash
streamlit run app.py
```

## 📂 Project Structure

- `app.py`: Main Streamlit application and UI logic.
- `crawler.py`: Web crawling and data extraction logic (regex).
- `social.py`: Social media profile link generation.
- `analysis.py`: Sentiment analysis, location detection, and connection engine.
- `requirements.txt`: Project dependencies.

## 🧪 Example Usage

1. **Phone Search:** Enter `+14155552671` to see location detection and social links.
2. **Name Search:** Enter a name like `John Doe` to trigger Google Dorking and social discovery.
3. **Image Upload:** Upload a JPEG with EXIF data to view technical metadata.
