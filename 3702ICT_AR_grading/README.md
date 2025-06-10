# 3702ICT AR - Grading System

This is the course-specific grading system for **3702ICT AR Course**.

## Course-Specific Features

This grading system is tailored for foundational AR coursework with criteria appropriate for undergraduate-level work:

### Grading Components (Total: 100 points)

1. **Video Presentation** (35 points)
   - **Technical Demonstration** (15 points): AR features implementation, functionality demonstration
   - **Presentation Quality** (10 points): Clear communication, professional delivery
   - **Problem-Solving Approach** (10 points): Problem identification and solution methodology

2. **Coding Quality** (20 points)
   - **Technical Implementation** (8 points): AR functionality, code structure
   - **Code Organization** (6 points): Clean architecture, modularity
   - **Best Practices** (6 points): Coding standards, documentation, error handling

3. **Component Assessment** (45 points)
   - **Project Description** (15 points): Clear problem statement and approach
   - **Individual Contribution** (15 points): Personal contribution to the project
   - **Testing & Validation** (10 points): Testing methodologies and validation
   - **Supporting Asset Management** (5 points): File organization and documentation

## Key Differences from 7009ICT

- **Foundational Focus**: Emphasis on fundamental AR concepts and implementation
- **Undergraduate Expectations**: Appropriate complexity level for undergraduate coursework
- **Practical Implementation**: Focus on working AR applications rather than research innovation
- **Clear Learning Objectives**: Structured around core AR development skills

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
   python grader_3702ICT.py
   ```

4. **Input Requirements**:
   - Submissions directory path
   - Choose grading mode (all students or specific student)

## File Structure Expected

Each student submission should contain:
- Video file (`.mp4`, `.mov`, `.avi`, `.mkv`)
- ZIP file with project code and documentation

## Output

- CSV file with detailed scores: `3702ICT_AR_grading_results_YYYYMMDD_HHMMSS.csv`
- Detailed feedback folder: `3702ICT_AR_detailed_feedback_YYYYMMDD_HHMMSS/`

## Grading Scale

- **Excellent (90-100%)**: Exceptional AR implementation with clear understanding
- **Good (80-89%)**: Strong AR concepts with good technical execution
- **Satisfactory (70-79%)**: Adequate AR implementation meeting requirements
- **Needs Improvement (60-69%)**: Basic implementation with areas for improvement
- **Unsatisfactory (0-59%)**: Minimal implementation or significant issues

## Technical Notes

- Uses Gemini 2.5 Flash Preview for AI-powered grading
- Extracts frames from video for visual analysis
- Supports multiple programming languages and file formats
- Includes rate limiting to avoid API quota issues
- Designed for educational assessment with constructive feedback
