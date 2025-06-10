# 7009ICT Advanced in AR - Grading System

This is the course-specific grading system for **7009ICT Advanced in AR Course**.

## Course-Specific Features

This grading system is tailored for advanced AR coursework with enhanced criteria for:

### Grading Components (Total: 100 points)

1. **Video Presentation** (35 points)
   - **Technical Demonstration & Innovation** (15 points): Advanced AR features, novel interactions, technical complexity
   - **Presentation Quality & Communication** (10 points): Clear explanation of advanced concepts, professional delivery
   - **Problem-Solving & Methodology** (10 points): Advanced problem identification, research methodology, innovation

2. **Coding Quality** (20 points)
   - **Advanced Technical Implementation** (8 points): Sophisticated AR algorithms, performance optimization
   - **Code Architecture & Design Patterns** (6 points): Advanced software architecture, modular design
   - **Code Quality & Best Practices** (6 points): Professional standards, error handling, documentation

3. **Component Assessment** (45 points)
   - **Advanced Project Description & Research Foundation** (15 points): Comprehensive research problem analysis
   - **Advanced Individual Contribution & Innovation** (15 points): Original research contributions, novel algorithms
   - **Advanced Testing & Validation Methodology** (10 points): Rigorous testing protocols, performance evaluation
   - **Advanced Supporting Asset Management** (5 points): Professional organization, documentation

## Key Differences from 3702ICT

- **Higher Research Standards**: Emphasis on original research contributions and literature review
- **Advanced Technical Depth**: Focus on sophisticated AR algorithms and optimization
- **Innovation Requirements**: Greater weight on novel approaches and technical innovation
- **Graduate-Level Expectations**: More rigorous testing and validation methodologies

## Usage

1. **Setup Environment**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Key**:
   - Ensure your `.env` file contains your Gemini API key:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

3. **Run Grading**:
   ```bash
   python grader_7009ICT.py
   ```

4. **Input Requirements**:
   - Submissions directory path
   - Choose grading mode (all students or specific student)

## File Structure Expected

Each student submission should contain:
- Video file (`.mp4`, `.mov`, `.avi`, `.mkv`)
- ZIP file with project code and documentation

## Output

- CSV file with detailed scores: `7009ICT_AdvancedInAR_grading_results_YYYYMMDD_HHMMSS.csv`
- Detailed feedback folder: `7009ICT_AdvancedInAR_detailed_feedback_YYYYMMDD_HHMMSS/`

## Grading Scale

- **Excellent (90-100%)**: Exceptional advanced AR implementation with significant innovation
- **Good (80-89%)**: Strong advanced work with notable technical contributions
- **Satisfactory (70-79%)**: Adequate advanced implementation with reasonable depth
- **Needs Improvement (60-69%)**: Basic advanced features lacking research rigor
- **Unsatisfactory (0-59%)**: Minimal advanced work or poor research methodology

## Technical Notes

- Uses Gemini 2.5 Flash Preview for AI-powered grading
- Extracts up to 8 frames from video for analysis
- Supports multiple programming languages and file formats
- Includes rate limiting to avoid API quota issues
