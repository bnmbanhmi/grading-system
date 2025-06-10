# AR Grading System

This is an automated grading system for AR projects using the Gemini API. The system has been separated into course-specific implementations to handle different grading criteria and requirements.

## Course-Specific Grading Systems

### 🎓 3702ICT AR Course
- **Directory**: `3702ICT_AR_grading/`
- **Focus**: Foundational AR concepts and undergraduate-level implementation
- **Script**: `grader_3702ICT.py`
- **Documentation**: See `3702ICT_AR_grading/README.md`

### 🎓 7009ICT Advanced in AR Course  
- **Directory**: `7009ICT_AdvancedInAR_grading/`
- **Focus**: Advanced AR research, innovation, and graduate-level work
- **Script**: `grader_7009ICT.py`
- **Documentation**: See `7009ICT_AdvancedInAR_grading/README.md`

## Key Differences Between Courses

| Aspect | 3702ICT AR | 7009ICT Advanced AR |
|--------|------------|-------------------|
| Level | Undergraduate | Graduate |
| Focus | Implementation & Functionality | Research & Innovation |
| Technical Depth | Fundamental AR concepts | Advanced algorithms & optimization |
| Assessment | Practical skills | Research contributions |
| Grading Emphasis | Clear implementation | Novel approaches & methodology |

## Global Setup

1. **Create Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Key**:
   Create a `.env` file in the main directory with:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

## Usage

### For 3702ICT AR Course:
```bash
cd 3702ICT_AR_grading
python grader_3702ICT.py
```

### For 7009ICT Advanced AR Course:
```bash
cd 7009ICT_AdvancedInAR_grading
python grader_7009ICT.py
```

### Legacy Unified System:
```bash
# Still available for reference
python grader.py        # Original unified grader
python organizer.py     # Submission organizer
```

## Project Structure
```
grading-system/
├── grader.py                     # Original unified grading script
├── organizer.py                  # Organizes submissions
├── requirements.txt              # Python dependencies
├── .env                         # API configuration
├── 3702ICT_AR_grading/          # 3702ICT course-specific grading
│   ├── grader_3702ICT.py
│   ├── README.md
│   ├── .env
│   └── requirements.txt
├── 7009ICT_AdvancedInAR_grading/ # 7009ICT course-specific grading
│   ├── grader_7009ICT.py
│   ├── README.md
│   ├── .env
│   └── requirements.txt
├── organized_assignments/        # Organized submission folders
└── grading_results/             # Generated grading results
```

## Features

- **AI-Powered Grading**: Uses Google's Gemini API for intelligent assessment
- **Multi-Modal Analysis**: Processes video, code, and documentation
- **Course-Specific Criteria**: Tailored rubrics for different course levels
- **Detailed Feedback**: Comprehensive written feedback for each component
- **Comment Refinement**: NEW! Makes AI feedback sound more natural and professorial
- **Flexible Scoring**: Automatic score extraction with fallback estimation
- **Export Options**: CSV results and individual feedback files
- **Rate Limiting**: Built-in API quota management

### 🆕 Comment Refinement Feature
The system now includes intelligent comment refinement that transforms AI-generated feedback into more natural, human-like comments while preserving all technical content. Available through Option 5 in all graders.

- **Undergraduate Tone**: Encouraging, supportive feedback for learning
- **Graduate Tone**: Sophisticated academic language for research work
- **Safety Features**: Automatic backups and content preservation

See `COMMENT_REFINEMENT_GUIDE.md` for detailed usage instructions.

## Output Files

Each grading session generates:
- **CSV Results**: `{COURSE_NAME}_grading_results_{timestamp}.csv`
- **Detailed Feedback**: `{COURSE_NAME}_detailed_feedback_{timestamp}/`

## Technical Requirements

- Python 3.8+
- Google Gemini API access
- OpenCV for video processing
- Required packages listed in `requirements.txt`

## Migration Notes

The system has been split from a unified grader to course-specific implementations to better serve the different assessment needs of each course. The original `grader.py` remains available for reference and backward compatibility.

