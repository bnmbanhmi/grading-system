# Grading System

This is an automated grading system for AR projects using the Gemini API.

## Setup
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Set up your .env file with GEMINI_API_KEY

## Usage
- Run `python organizer.py` to organize submissions
- Run `python grader.py` to grade organized assignments

## Project Structure
- `grader.py` - Main grading script
- `organizer.py` - Organizes submissions
- `organized_assignments/` - Organized submission folders
- `grading_results/` - Generated grading results

