#!/usr/bin/env python3
"""
Simple Interactive Grading System
Single script for grading 3702ICT and 7009ICT courses
"""

import os
import json
import csv
import time
import base64
import cv2
import zipfile
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

class SimpleGrader:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model_name = "gemini-2.5-flash-preview-05-20"
        self.course_config = {}
        self.results = []
        self.results_folder = None
        self.timestamp = None
        self.api_delay = 5  # Default delay
        self.use_short_prompts = False  # Default to full prompts
        self.api_delay = 5  # Default API delay in seconds
        self.use_short_prompts = False  # Use full prompts by default
        
    def show_menu(self):
        """Display main menu and handle user choices."""
        while True:
            print("\n" + "="*60)
            print("🎓 INTERACTIVE GRADING SYSTEM")
            print("="*60)
            print("1. Grade 3702 (Project Evaluation)")
            print("2. Grade 7009 (Reflective Performance Analysis)")
            print("3. Exit")
            print("="*60)
            
            choice = input("Enter your choice (1-3): ").strip()
            if choice == "1":
                self.setup_3702_config()
            elif choice == "2":
                self.setup_7009_config()
            elif choice == "3":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
                continue
            
            # Ask if user wants to continue or exit after grading
            continue_choice = input("\n🔄 Return to main menu? (y/n): ").strip().lower()
            if continue_choice != 'y':
                print("👋 Goodbye!")
                break
    
    def setup_3702_config(self):
        """Configure 3702ICT grading parameters."""
        print("\n🔧 CONFIGURING 3702ICT GRADING")
        print("-" * 40)
        
        # Set score range
        print("📊 Score Range Configuration:")
        print("The system will grade on a 0-100 scale, but you can set the expected range.")
        
        while True:
            try:
                min_score = float(input("Enter minimum expected score (e.g., 65): "))
                max_score = float(input("Enter maximum expected score (e.g., 90): "))
                if 0 <= min_score < max_score <= 100:
                    break
                else:
                    print("❌ Invalid range. Min must be < Max, and both between 0-100.")
            except ValueError:
                print("❌ Please enter valid numbers.")
        
        # Get assignments folder
        while True:
            folder = input("\n📁 Enter path to assignments folder (or press Enter for default): ").strip()
            if not folder:
                folder = "3702"  # Default to local 3702 folder
            
            if os.path.exists(folder):
                break
            else:
                print(f"❌ Folder not found: {folder}")
                print("Available folders:")
                self.show_available_folders()
        
        self.course_config = {
            'course': '3702ICT',
            'folder': folder,
            'min_score': min_score,
            'max_score': max_score,
            'components': {
                'Design': 20,
                'XR/Game Development': 20,
                'Demonstration and Video': 10,
                'Workshops': 10,
                'Project Overview': 15,
                'Testing Feedback': 10,
                'Teamwork Review': 10,
                'Quality of Document and Academic Literacy': 5
            },
            'prompt': self.get_3702_prompt()
        }
        
        self.run_grading()
    
    def setup_7009_config(self):
        """Configure 7009ICT grading parameters."""
        print("\n🔧 CONFIGURING 7009ICT GRADING")
        print("-" * 40)
        
        # Set score range
        print("📊 Score Range Configuration:")
        print("The system will grade on a 0-100 scale, but you can set the expected range.")
        
        while True:
            try:
                min_score = float(input("Enter minimum expected score (e.g., 65): "))
                max_score = float(input("Enter maximum expected score (e.g., 90): "))
                if 0 <= min_score < max_score <= 100:
                    break
                else:
                    print("❌ Invalid range. Min must be < Max, and both between 0-100.")
            except ValueError:
                print("❌ Please enter valid numbers.")
        
        # Get assignments folder
        while True:
            folder = input("\n📁 Enter path to assignments folder (or press Enter for default): ").strip()
            if not folder:
                folder = "7009"  # Default to local 7009 folder
            
            if os.path.exists(folder):
                break
            else:
                print(f"❌ Folder not found: {folder}")
                print("Available folders:")
                self.show_available_folders()
        
        self.course_config = {
            'course': '7009ICT',
            'folder': folder,
            'min_score': min_score,
            'max_score': max_score,
            'components': {
                'Introduction & Reflection on Final Product': 20,
                'Methodology & Test Setup': 15,
                'Performance Metrics Analysis': 25,
                'Comparative Analysis': 20,
                'Discussion, Optimization & Conclusion': 15,
                'Report Structure & Clarity': 5
            },
            'prompt': self.get_7009_prompt()
        }
        
        self.run_grading()
    
    def show_available_folders(self):
        """Show available folders in current directory."""
        for item in os.listdir("."):
            if os.path.isdir(item) and not item.startswith('.'):
                print(f"  📂 {item}")
    
    def get_3702_prompt(self):
        """Return the 3702ICT grading prompt."""
        return """To produce the desired marking output, here's a detailed prompt you can use, along with the specified marking steps and output format.

---

## Marking Prompt for Project Evaluation

Please mark the submitted project based on the following criteria. For each criterion, provide a numerical score and a corresponding comment justifying the score. Finally, calculate and present the total score.

---

### Marking Steps

1.  **Review the Submission:** Thoroughly examine all submitted project components, including:
    * **Reflection Document:** Individual journal entries and reflection on your project and the process you undertook. You will provide constructive feedback on the testing of peers' projects. Each student is to produce their own journal through the course and provide a self-reflective review - this component is an individual assessment, not a group document.

2.  **Evaluate Against Each Criterion:** For each of the following criteria, assign a score based on the provided rating scale. The score should fall within the specified range for the chosen rating.

    * **Design:**
        * Excellent (17.1 to 20 pts)
        * Good (13.1 to 17 pts)
        * Average (9.1 to 13 pts)
        * Below average (4.1 to 9 pts)
        * Absent or poor (4 pts)

    * **XR/Game Development:**
        * Excellent (17.1 to 20 pts)
        * Good (13.1 to 17 pts)
        * Average (9.1 to 13 pts)
        * Below average (4.1 to 9 pts)
        * Absent or poor (4 pts)

    * **Demonstration and Video:**
        * Excellent (8.1 to 10 pts)
        * Good (6.1 to 8 pts)
        * Average (4.1 to 6 pts)
        * Below average (2.1 to 4 pts)
        * Absent or poor (2 pts)

    * **Workshops:**
        * Excellent (8.1 to 10 pts)
        * Good (6.1 to 8 pts)
        * Average (4.1 to 6 pts)
        * Below average (2.1 to 4 pts)
        * Absent or poor (2 pts)

    * **Project Overview:**
        * Excellent (13.1 to 15 pts)
        * Good (11.1 to 13 pts)
        * Average (7.1 to 11 pts)
        * Below average (3.1 to 7 pts)
        * Absent or poor (3 pts)

    * **Testing Feedback:**
        * Excellent (8.1 to 10 pts)
        * Good (6.1 to 8 pts)
        * Average (4.1 to 6 pts)
        * Below average (2.1 to 4 pts)
        * Absent or poor (2 pts)

    * **Teamwork Review:**
        * Excellent (8.1 to 10 pts)
        * Good (6.1 to 8 pts)
        * Average (4.1 to 6 pts)
        * Below average (2.1 to 4 pts)
        * Absent or poor (2 pts)

    * **Quality of Document and Academic Literacy:**
        * Excellent (4.1 to 5 pts)
        * Good (3.1 to 4 pts)
        * Average (2.1 to 3 pts)
        * Below average (1.1 to 2 pts)
        * Absent or poor (1 pts)

3.  **Provide Comments:** For each criterion, write a concise and specific comment that justifies the assigned score. The comment should highlight strengths, areas for improvement, and direct references to the submitted work where applicable.

4.  **Calculate Total Score:** Sum up the scores from all criteria to get the final total score for the project.

---

### Output Format

IMPORTANT: You must respond with ONLY a valid JSON object in this exact format. Do not include any other text, markdown, or explanations outside the JSON:

{
  "student_name": "Extract student name from document content",
  "components": {
    "Design": {
      "score": 0.0,
      "max_score": 20,
      "comment": "Detailed comment justifying the score for Design"
    },
    "XR/Game Development": {
      "score": 0.0,
      "max_score": 20,
      "comment": "Detailed comment justifying the score for XR/Game Development"
    },
    "Demonstration and Video": {
      "score": 0.0,
      "max_score": 10,
      "comment": "Detailed comment justifying the score for Demonstration and Video"
    },
    "Workshops": {
      "score": 0.0,
      "max_score": 10,
      "comment": "Detailed comment justifying the score for Workshops"
    },
    "Project Overview": {
      "score": 0.0,
      "max_score": 15,
      "comment": "Detailed comment justifying the score for Project Overview"
    },
    "Testing Feedback": {
      "score": 0.0,
      "max_score": 10,
      "comment": "Detailed comment justifying the score for Testing Feedback"
    },
    "Teamwork Review": {
      "score": 0.0,
      "max_score": 10,
      "comment": "Detailed comment justifying the score for Teamwork Review"
    },
    "Quality of Document and Academic Literacy": {
      "score": 0.0,
      "max_score": 5,
      "comment": "Detailed comment justifying the score for Quality of Document and Academic Literacy"
    }
  },
  "total_score": 0.0,
  "max_total_score": 100
}"""
    
    def get_7009_prompt(self):
        """Return the 7009ICT grading prompt."""
        return """Here's a detailed prompt you can use to mark the student reports, including the marking steps and the desired output format.

---

## Marking Prompt for Reflective Performance Analysis Report

Please assess the student's **Reflective Performance Analysis Report** based on the provided criteria. For each component, assign a score and provide a corresponding comment justifying the score. Finally, calculate and present the total score.

---

### Marking Steps

1.  **Understand the Report's Purpose:** Remember that this report requires students to reflect on their final AR application, analyze its performance metrics using Unity's Profiler, and discuss optimization skills.

2.  **Review the Report Components:** Carefully read through each section of the submitted report:
    * **Introduction:** Check for a brief overview and the purpose of the evaluation.
    * **Reflection on Final Product:** Look for discussions on overall performance, development challenges, design decisions impacting performance, and identified areas for improvement with trade-offs.
    * **Methodology:** Verify the explanation of the test setup, devices used, and Unity tools.
    * **Performance Metrics Evaluation:** Assess the detailed analysis of metrics (e.g., FPS, memory, tracking stability), including any graphs, screenshots, or data tables.
    * **Comparative Analysis:** Evaluate the comparison between devices/platforms based on key performance indicators.
    * **Discussion & Recommendations:** Look for interpretations of findings, suggested optimizations, and discussion of trade-offs.
    * **Conclusion:** Check for a summary of key takeaways and reflections.
    * **References (if any):** Note if references are included and properly cited.

3.  **Evaluate Against Each Criterion:** For each of the following criteria, assign a numerical score within the specified range for the corresponding rating. The score should reflect the quality and depth of the content presented in the report.

    * **Introduction & Reflection on Final Product:**
        * Excellent (15.1 to 20 pts)
        * Good (11.1 to 15 pts)
        * Satisfactory (7.1 to 11 pts)
        * Needs Improvement (0.1 to 7 pts)
        * No Evidence (0 pts)

    * **Methodology & Test Setup:**
        * Excellent (11.1 to 15 pts)
        * Good (8.1 to 11 pts)
        * Satisfactory (5.1 to 8 pts)
        * Needs Improvement (0.1 to 5 pts)
        * No Evidence (0 pts)

    * **Performance Metrics Analysis:**
        * Excellent (19.1 to 25 pts)
        * Good (14.1 to 19 pts)
        * Satisfactory (9.1 to 14 pts)
        * Needs Improvement (0.1 to 9 pts)
        * No Evidence (0 pts)

    * **Comparative Analysis:**
        * Excellent (15.1 to 20 pts)
        * Good (11.1 to 15 pts)
        * Satisfactory (7.1 to 11 pts)
        * Needs Improvement (0.1 to 7 pts)
        * No Evidence (0 pts)

    * **Discussion, Optimization & Conclusion:**
        * Excellent (11.1 to 15 pts)
        * Good (8.1 to 11 pts)
        * Satisfactory (5.1 to 8 pts)
        * Needs Improvement (0.1 to 5 pts)
        * No Evidence (0 pts)

    * **Report Structure & Clarity:**
        * Excellent (3.1 to 5 pts)
        * Good (2.1 to 3 pts)
        * Satisfactory (1.1 to 2 pts)
        * Needs Improvement (0.1 to 1 pts)
        * No Evidence (0 pts)

4.  **Provide Feedback:** For each criterion, write a **short, constructive comment** that explains the assigned score. Highlight specific strengths, point out areas for improvement, and suggest how the student could enhance their work in future reports.

5.  **Calculate Total Score:** Sum up the scores from all criteria to arrive at the final total score out of 100 points.

---

### Output Format

IMPORTANT: You must respond with ONLY a valid JSON object in this exact format. Do not include any other text, markdown, or explanations outside the JSON:

{
  "student_name": "Extract student name from document content",
  "components": {
    "Introduction & Reflection on Final Product": {
      "score": 0.0,
      "max_score": 20,
      "comment": "Short feedback for this component"
    },
    "Methodology & Test Setup": {
      "score": 0.0,
      "max_score": 15,
      "comment": "Short feedback for this component"
    },
    "Performance Metrics Analysis": {
      "score": 0.0,
      "max_score": 25,
      "comment": "Short feedback for this component"
    },
    "Comparative Analysis": {
      "score": 0.0,
      "max_score": 20,
      "comment": "Short feedback for this component"
    },
    "Discussion, Optimization & Conclusion": {
      "score": 0.0,
      "max_score": 15,
      "comment": "Short feedback for this component"
    },
    "Report Structure & Clarity": {
      "score": 0.0,
      "max_score": 5,
      "comment": "Short feedback for this component"
    }
  },
  "total_score": 0.0,
  "max_total_score": 100
}"""
    
    def extract_video_frames(self, video_path, max_frames=3):
        """Extract frames from video file."""
        try:
            cap = cv2.VideoCapture(video_path)
            frames = []
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                cap.release()
                return []
            
            # Extract frames at even intervals
            for i in range(max_frames):
                frame_num = int((i + 1) * total_frames / (max_frames + 1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if ret:
                    # Save frame temporarily
                    temp_path = f"temp_frame_{i}.jpg"
                    cv2.imwrite(temp_path, frame)
                    frames.append(temp_path)
            
            cap.release()
            return frames
        except Exception as e:
            print(f"Error extracting frames from {video_path}: {e}")
            return []
    
    def encode_image_to_base64(self, image_path):
        """Encode image to base64."""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            return None
    
    def extract_zip_content(self, zip_path):
        """Extract text content from ZIP files."""
        content = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if not file_info.is_dir():
                        file_ext = os.path.splitext(file_info.filename)[1].lower()
                        if file_ext in ['.txt', '.cs', '.py', '.js', '.cpp', '.h']:
                            try:
                                with zip_ref.open(file_info) as f:
                                    text = f.read().decode('utf-8', errors='ignore')
                                    content.append(f"=== {file_info.filename} ===\n{text}\n")
                            except:
                                pass
        except Exception as e:
            print(f"Error extracting ZIP {zip_path}: {e}")
        
        return "\n".join(content) if content else "No readable content in ZIP file"
    
    def call_gemini_api(self, prompt, files):
        """Call Gemini API with files."""
        max_retries = 3
        retry_delay = 5  # Start with 5 seconds
        
        for attempt in range(max_retries):
            try:
                content = [prompt]
                
                # Process files
                for file_path in files:
                    if not os.path.exists(file_path):
                        continue
                    
                    file_ext = os.path.splitext(file_path)[1].lower()
                    
                    if file_ext in ['.jpg', '.jpeg', '.png']:
                        # Image file
                        encoded = self.encode_image_to_base64(file_path)
                        if encoded:
                            content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": encoded
                                }
                            })
                    elif file_ext == '.zip':
                        # ZIP file
                        zip_content = self.extract_zip_content(file_path)
                        content.append(f"\n=== ZIP Content: {os.path.basename(file_path)} ===\n{zip_content}")
                    elif file_ext in ['.mp4', '.avi', '.mov']:
                        # Video file - extract frames
                        frames = self.extract_video_frames(file_path)
                        for frame in frames:
                            encoded = self.encode_image_to_base64(frame)
                            if encoded:
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": encoded
                                    }
                                })
                            # Clean up temp frame
                            try:
                                os.remove(frame)
                            except:
                                pass
                    else:
                        # Text file - limit size to avoid quota issues
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                text = f.read()
                                # Limit text size to 50KB to avoid quota issues
                                if len(text) > 50000:
                                    text = text[:50000] + "\n... [Content truncated to avoid quota limits] ..."
                                content.append(f"\n=== File: {os.path.basename(file_path)} ===\n{text}")
                        except Exception as e:
                            print(f"Error reading {file_path}: {e}")
                
                # Add rate limiting before API call
                time.sleep(3)  # 3 second delay between calls
                
                # Call API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=content,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        top_p=0.8,
                        max_output_tokens=4096  # Reduced to save quota
                    )
                )
                
                return response.text
                
            except Exception as e:
                error_msg = str(e)
                print(f"API call attempt {attempt + 1} failed: {error_msg}")
                
                # Check if it's a quota error
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    if attempt < max_retries - 1:
                        print(f"⏳ Rate limit hit. Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print("❌ API quota exhausted. Please wait or upgrade your plan.")
                        return f"Error: API quota exhausted - {error_msg}"
                else:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        return f"Error: Failed to grade submission - {error_msg}"
        
        return "Error: Maximum retries exceeded"
    
    def parse_grading_response(self, response_text, assignment_name):
        """Parse the grading response."""
        result = {
            'assignment': assignment_name,
            'student_name': 'Unknown',
            'components': {},
            'total_score': 0,
            'raw_response': response_text
        }
        
        # First try to parse as JSON
        try:
            # Clean the response - sometimes there's extra text
            cleaned_response = response_text.strip()
            
            # Find JSON object boundaries
            start_idx = cleaned_response.find('{')
            end_idx = cleaned_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = cleaned_response[start_idx:end_idx]
                parsed_data = json.loads(json_str)
                
                # Extract data from JSON structure
                result['student_name'] = parsed_data.get('student_name', 'Unknown')
                result['total_score'] = float(parsed_data.get('total_score', 0))
                
                # Extract components
                components = parsed_data.get('components', {})
                for component_name, component_data in components.items():
                    if isinstance(component_data, dict):
                        result['components'][component_name] = {
                            'score': float(component_data.get('score', 0)),
                            'max_score': float(component_data.get('max_score', 0)),
                            'comment': component_data.get('comment', '')
                        }
                
                # Calculate total if not provided
                if result['total_score'] == 0 and result['components']:
                    result['total_score'] = sum(comp.get('score', 0) for comp in result['components'].values())
                
                return result
                
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print("Falling back to text parsing...")
        except Exception as e:
            print(f"Error in JSON parsing: {e}")
            print("Falling back to text parsing...")
        
        # Fallback: Parse as markdown (legacy format)
        lines = response_text.split('\n')
        current_component = None
        
        for line in lines:
            line = line.strip()
            
            # Extract student name - handle both formats
            if ('### Student name' in line or '#### Student name' in line or 
                'Student Name:' in line or '### Reflective Performance Analysis Report Marking' in line):
                if 'Student Name:' in line:
                    result['student_name'] = line.split('Student Name:')[1].strip()
                elif not 'Marking' in line and not 'Student name' == line.replace('###', '').replace('####', '').strip():
                    # Extract actual name if it's not just the header
                    name_part = line.replace('###', '').replace('####', '').replace('Student name', '').strip()
                    if name_part and name_part != 'Student name':
                        result['student_name'] = name_part
            
            # Detect component headers - handle both ### and #### formats
            elif (line.startswith('####') or line.startswith('### ')) and not any(x in line.lower() for x in ['student', 'marking', 'total', 'overall']):
                current_component = line.replace('####', '').replace('###', '').strip()
                if current_component and current_component not in result['components']:
                    result['components'][current_component] = {}
            
            # Extract scores
            elif line.startswith('**Score:**') and current_component:
                try:
                    score_part = line.replace('**Score:**', '').strip()
                    # Handle format like "15.5 / 20" or "[15.5] / 20" or "[Assigned Score] / 20"
                    score_part = score_part.replace('[', '').replace(']', '')
                    
                    # Skip if it contains template text
                    if 'Assigned Score' in score_part or 'Score' in score_part:
                        continue
                        
                    if '/' in score_part:
                        score_str = score_part.split('/')[0].strip()
                        max_score_str = score_part.split('/')[1].strip()
                        
                        # Try to convert to float
                        score = float(score_str)
                        max_score = float(max_score_str)
                        result['components'][current_component]['score'] = score
                        result['components'][current_component]['max_score'] = max_score
                except Exception as e:
                    print(f"Error parsing score for {current_component}: {e}")
                    # Continue without failing
            
            # Extract comments
            elif line.startswith('**Comment:**') and current_component:
                comment = line.replace('**Comment:**', '').strip()
                result['components'][current_component]['comment'] = comment
            
            # Extract total score - handle multiple formats
            elif any(x in line for x in ['**Overall Score:**', '**Total Score:**', 'Overall Score:', 'Total Score:']):
                try:
                    # Remove markdown and extract score
                    total_part = line
                    for marker in ['**Overall Score:**', '**Total Score:**', 'Overall Score:', 'Total Score:']:
                        if marker in total_part:
                            total_part = total_part.split(marker)[1].strip()
                            break
                    
                    total_part = total_part.replace('[', '').replace(']', '')
                    
                    # Skip if it contains template text
                    if 'Sum of all assigned scores' in total_part or 'Assigned Score' in total_part:
                        continue
                        
                    if '/' in total_part:
                        total_score_str = total_part.split('/')[0].strip()
                        result['total_score'] = float(total_score_str)
                    else:
                        result['total_score'] = float(total_part.strip())
                except Exception as e:
                    print(f"Error parsing total score: {e}")
                    # Continue without failing
        
        # If total score not found, calculate from components
        if result['total_score'] == 0 and result['components']:
            result['total_score'] = sum(comp.get('score', 0) for comp in result['components'].values())
        
        return result
    
    def grade_single_file(self, file_path, assignment_name):
        """Grade a single assignment file."""
        print(f"\n📝 Grading {os.path.basename(file_path)}...")
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
        
        # Process the single file
        files_to_process = [file_path]
        
        print(f"   📄 Processing file: {os.path.basename(file_path)}")
        
        # Grade with API
        response = self.call_gemini_api(self.course_config['prompt'], files_to_process)
        
        # Parse response
        result = self.parse_grading_response(response, assignment_name)
        
        # Adjust scores to expected range if needed
        self.adjust_scores_to_range(result)
        
        return result

    def grade_assignment(self, assignment_folder, assignment_name):
        """Grade a single assignment."""
        print(f"\n📝 Grading {assignment_name}...")
        
        # Collect files with priority for different types
        files_to_process = []
        video_files = []
        code_files = []
        document_files = []
        
        for root, dirs, files in os.walk(assignment_folder):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                # Categorize files
                if file_ext in ['.pdf', '.docx', '.doc', '.txt', '.md']:
                    document_files.append(file_path)
                elif file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']:
                    video_files.append(file_path)
                elif file_ext in ['.cs', '.py', '.js', '.cpp', '.h', '.java', '.kt', '.swift']:
                    code_files.append(file_path)
                elif file_ext == '.zip':
                    files_to_process.append(file_path)
        
        # Prioritize: documents first, then videos (extract frames), then code samples
        files_to_process.extend(document_files)
        
        # Process videos (extract frames)
        for video_file in video_files[:2]:  # Limit to 2 videos
            frames = self.extract_video_frames(video_file)
            files_to_process.extend(frames)
        
        # Add some code files (not too many to avoid token limits)
        files_to_process.extend(code_files[:5])
        
        if not files_to_process:
            print(f"❌ No files found in {assignment_folder}")
            return None
        
        print(f"   📄 Processing {len(files_to_process)} files")
        
        # Grade with API
        response = self.call_gemini_api(self.course_config['prompt'], files_to_process)
        
        # Clean up temporary frame files
        for file_path in files_to_process:
            if file_path.startswith('temp_frame_'):
                try:
                    os.remove(file_path)
                except:
                    pass
        
        # Parse response
        result = self.parse_grading_response(response, assignment_name)
        
        # Validate and adjust scores if needed
        self.adjust_scores_to_range(result)
        
        return result
    
    def adjust_scores_to_range(self, result):
        """Adjust scores to the expected range if they're outside it."""
        min_score = self.course_config['min_score']
        max_score = self.course_config['max_score']
        total_max = sum(self.course_config['components'].values())
        
        # Calculate expected total range
        expected_min_total = (min_score / 100) * total_max
        expected_max_total = (max_score / 100) * total_max
        
        current_total = result['total_score']
        
        # If total is way outside expected range, adjust proportionally
        if current_total < expected_min_total * 0.7 or current_total > expected_max_total * 1.3:
            adjustment_factor = ((expected_min_total + expected_max_total) / 2) / max(current_total, 1)
            
            for component, details in result['components'].items():
                if 'score' in details:
                    old_score = details['score']
                    new_score = min(old_score * adjustment_factor, details.get('max_score', 100))
                    details['score'] = round(new_score, 1)
            
            # Recalculate total
            result['total_score'] = sum(details.get('score', 0) for details in result['components'].values())
    
    def run_grading(self):
        """Run the grading process."""
        folder = self.course_config['folder']
        course = self.course_config['course']
        
        print(f"\n🚀 Starting {course} grading...")
        print(f"📂 Folder: {folder}")
        print(f"📊 Expected score range: {self.course_config['min_score']}-{self.course_config['max_score']}")
        
        # Check for existing results and ask for rerun options
        rerun_mode = self.check_existing_results_and_ask()
        
        # Initialize real-time results tracking
        self.setup_realtime_results()
        
        # Get assignment files (PDF and DOCX files)
        assignment_files = []
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.lower().endswith(('.pdf', '.docx', '.doc')) and not file.startswith('.'):
                    assignment_files.append(file)
        
        if not assignment_files:
            print("❌ No assignment files found!")
            return
        
        # Filter files based on rerun mode
        files_to_process = self.filter_files_for_rerun(assignment_files, rerun_mode)
        
        print(f"📋 Found {len(assignment_files)} total assignments")
        print(f"🎯 Will process {len(files_to_process)} assignments based on your selection")
        
        if len(files_to_process) <= 10:
            for i, file in enumerate(files_to_process, 1):
                print(f"   {i}. {file}")
        else:
            for i, file in enumerate(files_to_process[:5], 1):
                print(f"   {i}. {file}")
            print(f"   ... and {len(files_to_process) - 5} more")
        
        print(f"\n📄 Results will be saved in real-time to:")
        print(f"   • JSON: {self.results_folder}/grading_results_{self.timestamp}.json")
        print(f"   • CSV: {self.results_folder}/grading_report_{self.timestamp}.csv")
        print(f"💡 Open these files in another window to monitor progress!")
        
        # Start grading loop with user control
        self.run_grading_loop(files_to_process, folder)
    
    def check_existing_results_and_ask(self):
        """Check for existing results and ask user what to do."""
        course = self.course_config['course']
        results_folder_name = f"{course}_grading_results"
        
        if os.path.exists(results_folder_name):
            print(f"\n🔍 Found existing results folder: {results_folder_name}")
            
            # List existing files
            existing_files = [f for f in os.listdir(results_folder_name) if f.endswith(('.json', '.csv', '.txt'))]
            if existing_files:
                print("📄 Existing files:")
                for file in sorted(existing_files)[-5:]:  # Show last 5 files
                    print(f"   • {file}")
                if len(existing_files) > 5:
                    print(f"   ... and {len(existing_files) - 5} more")
        
        print(f"\n🔧 GRADING OPTIONS:")
        print("1. Fresh start - Grade all assignments (new timestamp)")
        print("2. Continue previous - Only grade failed/missing assignments")
        print("3. Rerun outliers - Only grade assignments outside expected range")
        print("4. Rerun all - Regrade all assignments (overwrite existing)")
        print("5. Cancel")
        
        while True:
            choice = input("\nSelect grading mode (1-5): ").strip()
            if choice == "1":
                return "fresh"
            elif choice == "2":
                return "continue"
            elif choice == "3":
                return "outliers"
            elif choice == "4":
                return "rerun_all"
            elif choice == "5":
                print("❌ Grading cancelled.")
                return "cancel"
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, 4, or 5.")
    
    def filter_files_for_rerun(self, assignment_files, rerun_mode):
        """Filter assignment files based on rerun mode."""
        if rerun_mode == "cancel":
            return []
        
        if rerun_mode == "fresh" or rerun_mode == "rerun_all":
            return assignment_files
        
        # For continue and outliers mode, check existing results
        processed_files = set()
        failed_files = set()
        outlier_files = set()
        
        course = self.course_config['course']
        results_folder_name = f"{course}_grading_results"
        
        if os.path.exists(results_folder_name):
            # Find the most recent results file
            json_files = [f for f in os.listdir(results_folder_name) if f.startswith('grading_results_') and f.endswith('.json')]
            if json_files:
                latest_json = sorted(json_files)[-1]
                json_path = os.path.join(results_folder_name, latest_json)
                
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        existing_results = json.load(f)
                    
                    for result in existing_results:
                        assignment_name = result.get('assignment', '')
                        # Find corresponding file
                        matching_file = None
                        for file in assignment_files:
                            if os.path.splitext(file)[0] == assignment_name:
                                matching_file = file
                                break
                        
                        if matching_file:
                            processed_files.add(matching_file)
                            
                            # Check if it was failed or outlier
                            total_score = result.get('total_score', 0)
                            is_error = total_score == 0 or 'Error:' in result.get('raw_response', '')
                            is_outlier = (total_score < self.course_config['min_score'] or 
                                        total_score > self.course_config['max_score']) and total_score > 0
                            
                            if is_error:
                                failed_files.add(matching_file)
                            elif is_outlier:
                                outlier_files.add(matching_file)
                    
                except Exception as e:
                    print(f"⚠️ Warning: Could not read existing results: {e}")
        
        if rerun_mode == "continue":
            # Only process files that haven't been processed or failed
            unprocessed = set(assignment_files) - processed_files
            to_process = list(unprocessed | failed_files)
            print(f"📊 Continue mode: {len(unprocessed)} new + {len(failed_files)} failed = {len(to_process)} to process")
            return to_process
        
        elif rerun_mode == "outliers":
            to_process = list(outlier_files)
            print(f"📊 Outliers mode: {len(to_process)} outlier assignments to reprocess")
            return to_process
        
        return assignment_files
    
    def run_grading_loop(self, files_to_process, folder):
        """Run the main grading loop with user control."""
        if not files_to_process:
            print("❌ No files to process based on your selection.")
            return
        
        while True:
            print(f"\n🎮 GRADING CONTROL:")
            print(f"📋 Ready to process {len(files_to_process)} assignments")
            print("1. Run all automatically (batch mode)")
            print("2. Run one by one (interactive mode)")
            print("3. Select specific assignments to run")
            print("4. Change delay settings")
            print("5. Use shorter prompts (save tokens)")
            print("6. Cancel and return to main menu")
            
            control_choice = input("\nSelect action (1-6): ").strip()
            
            if control_choice == "1":
                self.execute_grading_batch(files_to_process, folder, mode="automatic")
                break
            elif control_choice == "2":
                self.execute_grading_batch(files_to_process, folder, mode="interactive")
                break
            elif control_choice == "3":
                selected_files = self.select_specific_assignments(files_to_process)
                if selected_files:
                    self.execute_grading_batch(selected_files, folder, mode="automatic")
                break
            elif control_choice == "4":
                self.configure_delay_settings()
            elif control_choice == "5":
                self.configure_prompt_settings()
            elif control_choice == "6":
                print("❌ Grading cancelled.")
                return
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, 4, 5, or 6.")
    
    def select_specific_assignments(self, files_to_process):
        """Let user select specific assignments to run."""
        print(f"\n📋 SELECT ASSIGNMENTS TO GRADE:")
        print("Available assignments:")
        
        for i, file in enumerate(files_to_process, 1):
            print(f"   {i:2d}. {file}")
        
        print(f"\n💡 Enter assignment numbers separated by commas (e.g., 1,3,5)")
        print(f"💡 Or enter ranges (e.g., 1-5,8,10-12)")
        print(f"💡 Or enter 'all' to select all assignments")
        
        while True:
            selection = input("\nYour selection: ").strip()
            
            if not selection:
                print("❌ Please enter a selection")
                continue
            
            if selection.lower() == 'all':
                return files_to_process
            
            try:
                selected_indices = set()
                parts = selection.split(',')
                
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        # Range
                        start, end = part.split('-')
                        start_idx = int(start.strip()) - 1
                        end_idx = int(end.strip()) - 1
                        if 0 <= start_idx < len(files_to_process) and 0 <= end_idx < len(files_to_process):
                            selected_indices.update(range(start_idx, end_idx + 1))
                        else:
                            raise ValueError(f"Range {part} is out of bounds")
                    else:
                        # Single number
                        idx = int(part.strip()) - 1
                        if 0 <= idx < len(files_to_process):
                            selected_indices.add(idx)
                        else:
                            raise ValueError(f"Number {part} is out of bounds")
                
                selected_files = [files_to_process[i] for i in sorted(selected_indices)]
                
                if selected_files:
                    print(f"✅ Selected {len(selected_files)} assignments:")
                    for file in selected_files:
                        print(f"   • {file}")
                    
                    confirm = input(f"\nProceed with these {len(selected_files)} assignments? (y/n): ").strip().lower()
                    if confirm == 'y':
                        return selected_files
                    else:
                        continue
                else:
                    print("❌ No valid assignments selected")
                    continue
                    
            except ValueError as e:
                print(f"❌ Invalid selection: {e}")
                print("Please use format like: 1,3,5 or 1-5,8,10-12")
                continue
    
    def configure_delay_settings(self):
        """Configure API delay settings."""
        print(f"\n⏱️ DELAY SETTINGS:")
        print("Current delay between API calls: 5 seconds")
        print("1. Keep current (5 seconds)")
        print("2. Longer delay (10 seconds) - safer for quota")
        print("3. Shorter delay (3 seconds) - faster but riskier")
        print("4. Custom delay")
        
        while True:
            choice = input("Select delay option (1-4): ").strip()
            if choice == "1":
                self.api_delay = 5
                break
            elif choice == "2":
                self.api_delay = 10
                break
            elif choice == "3":
                self.api_delay = 3
                break
            elif choice == "4":
                try:
                    custom_delay = float(input("Enter delay in seconds (1-60): "))
                    if 1 <= custom_delay <= 60:
                        self.api_delay = custom_delay
                        break
                    else:
                        print("❌ Delay must be between 1 and 60 seconds.")
                except ValueError:
                    print("❌ Invalid number.")
            else:
                print("❌ Invalid choice.")
        
        print(f"✅ Delay set to {self.api_delay} seconds")
    
    def configure_prompt_settings(self):
        """Configure prompt settings."""
        print(f"\n📝 PROMPT SETTINGS:")
        print("1. Use full detailed prompts (better quality)")
        print("2. Use shorter prompts (save tokens)")
        
        while True:
            choice = input("Select prompt option (1-2): ").strip()
            if choice == "1":
                self.use_short_prompts = False
                print("✅ Using full detailed prompts")
                break
            elif choice == "2":
                self.use_short_prompts = True
                print("✅ Using shorter prompts")
                break
            else:
                print("❌ Invalid choice.")
    
    def execute_grading_batch(self, files_to_process, folder, mode="automatic"):
        """Execute the actual grading batch with user control."""
        print(f"\n🚀 Starting grading in {mode} mode...")
        
        # Grade each assignment file
        self.results = []
        failed_assignments = []
        problematic_assignments = []
        
        # Use configured settings
        current_prompt = self.get_shorter_prompt() if self.use_short_prompts else self.course_config['prompt']
        original_prompt = self.course_config['prompt']
        if self.use_short_prompts:
            self.course_config['prompt'] = current_prompt
        
        for i, assignment_file in enumerate(sorted(files_to_process), 1):
            file_path = os.path.join(folder, assignment_file)
            # Use filename without extension as assignment name
            assignment_name = os.path.splitext(assignment_file)[0]
            
            print(f"\n[{i}/{len(files_to_process)}] Processing: {assignment_name[:60]}{'...' if len(assignment_name) > 60 else ''}")
            
            # Interactive mode controls
            if mode == "interactive":
                print(f"⏸️  Controls: [Enter] Continue | [s] Skip | [q] Quit | [p] Pause for settings")
                user_input = input("   Action: ").strip().lower()
                
                if user_input == 's':
                    print("   ⏭️ Skipping this assignment")
                    continue
                elif user_input == 'q':
                    print("   🛑 Stopping grading loop")
                    break
                elif user_input == 'p':
                    self.pause_for_settings()
                    # Re-apply prompt setting if changed
                    if self.use_short_prompts:
                        self.course_config['prompt'] = self.get_shorter_prompt()
                    else:
                        self.course_config['prompt'] = original_prompt
            
            # Grade the assignment
            result = self.grade_single_assignment_with_immediate_rerun(file_path, assignment_name, mode)
            
            if result:
                # Check for errors or problematic scores
                is_error = 'Error:' in result.get('raw_response', '')
                has_zero_score = result['total_score'] == 0
                is_below_limit = result['total_score'] < self.course_config['min_score']
                is_above_limit = result['total_score'] > self.course_config['max_score']
                
                # Determine status and update real-time results
                if is_error or has_zero_score:
                    status = "error"
                    failed_assignments.append({
                        'file_path': file_path,
                        'assignment_name': assignment_name,
                        'reason': 'API error or zero score'
                    })
                    print(f"   ❌ Failed: {result['total_score']:.1f}/100 (API error or parsing issue)")
                elif is_below_limit or is_above_limit:
                    status = "outlier"
                    problematic_assignments.append({
                        'file_path': file_path,
                        'assignment_name': assignment_name,
                        'score': result['total_score'],
                        'reason': f"Score {result['total_score']:.1f} outside expected range ({self.course_config['min_score']}-{self.course_config['max_score']})"
                    })
                    print(f"   ⚠️  Outlier: {result['total_score']:.1f}/100 (outside expected range)")
                else:
                    status = "completed"
                    print(f"   ✅ Score: {result['total_score']:.1f}/100")
                
                # Save immediately to real-time files
                self.update_realtime_results(result, status)
                self.results.append(result)
                
            else:
                failed_assignments.append({
                    'file_path': file_path,
                    'assignment_name': assignment_name,
                    'reason': 'Failed to process'
                })
                print(f"   ❌ Failed to process")
                
                # Create a dummy result for tracking
                dummy_result = {
                    'assignment': assignment_name,
                    'student_name': 'Unknown',
                    'components': {},
                    'total_score': 0,
                    'raw_response': 'Failed to process file'
                }
                self.update_realtime_results(dummy_result, "error")
            
            # Use configured delay (only in automatic mode or if not last item)
            if mode == "automatic" and i < len(files_to_process):
                print(f"   ⏳ Waiting {self.api_delay} seconds to avoid rate limits...")
                time.sleep(self.api_delay)
        
        # Restore original prompt
        self.course_config['prompt'] = original_prompt
        
        # Handle problematic assignments
        self.handle_problematic_assignments(failed_assignments, problematic_assignments)
        
        # Save final results
        self.save_results()
        print(f"\n🎉 Grading completed! Results saved in the assignments folder.")
    
    def grade_single_assignment_with_immediate_rerun(self, file_path, assignment_name, mode):
        """Grade a single assignment with immediate rerun option for outliers/errors."""
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            if attempt > 1:
                print(f"   🔄 Attempt {attempt}/{max_attempts}")
            
            result = self.grade_single_file(file_path, assignment_name)
            
            if not result:
                print(f"   ❌ Attempt {attempt} failed - no result returned")
                if mode == "interactive" and attempt < max_attempts:
                    retry = input(f"   🔄 Retry this assignment? (y/n): ").strip().lower()
                    if retry != 'y':
                        break
                attempt += 1
                continue
            
            # Check if result is problematic
            is_error = 'Error:' in result.get('raw_response', '')
            has_zero_score = result['total_score'] == 0
            is_below_limit = result['total_score'] < self.course_config['min_score']
            is_above_limit = result['total_score'] > self.course_config['max_score']
            
            is_problematic = is_error or has_zero_score or is_below_limit or is_above_limit
            
            if is_problematic and attempt < max_attempts:
                if is_error or has_zero_score:
                    print(f"   ❌ Attempt {attempt} failed: API error or zero score")
                else:
                    print(f"   ⚠️  Attempt {attempt} outlier: Score {result['total_score']:.1f} outside range ({self.course_config['min_score']}-{self.course_config['max_score']})")
                
                # Ask user if they want to retry immediately
                if mode == "interactive":
                    retry = input(f"   🔄 Retry immediately with different settings? (y/n): ").strip().lower()
                    if retry == 'y':
                        # Offer to change settings for retry
                        print("   ⚙️ Retry options:")
                        print("   1. Retry with longer delay")
                        print("   2. Retry with different prompt")
                        print("   3. Retry with current settings")
                        
                        retry_choice = input("   Select option (1-3): ").strip()
                        
                        if retry_choice == "1":
                            old_delay = self.api_delay
                            self.api_delay = min(self.api_delay * 2, 30)  # Max 30 seconds
                            print(f"   ⏱️ Increased delay to {self.api_delay} seconds for retry")
                            time.sleep(self.api_delay)
                            attempt += 1
                            continue
                        elif retry_choice == "2":
                            old_prompt = self.course_config['prompt']
                            self.use_short_prompts = not self.use_short_prompts
                            self.course_config['prompt'] = self.get_shorter_prompt() if self.use_short_prompts else old_prompt
                            prompt_type = "shorter" if self.use_short_prompts else "full"
                            print(f"   📝 Switched to {prompt_type} prompt for retry")
                            attempt += 1
                            continue
                        elif retry_choice == "3":
                            attempt += 1
                            continue
                        else:
                            break
                    else:
                        break
                else:
                    # In automatic mode, retry once with longer delay
                    if attempt == 1:
                        print(f"   🔄 Auto-retry with longer delay...")
                        time.sleep(10)  # Longer delay for retry
                        attempt += 1
                        continue
                    else:
                        break
            else:
                # Success or max attempts reached
                break
        
        return result
    
    def pause_for_settings(self):
        """Allow user to change settings during grading."""
        print(f"\n⚙️ PAUSE MENU:")
        print("1. Change delay settings")
        print("2. Toggle prompt length")
        print("3. Continue grading")
        
        while True:
            choice = input("Select option (1-3): ").strip()
            if choice == "1":
                self.configure_delay_settings()
            elif choice == "2":
                self.use_short_prompts = not self.use_short_prompts
                prompt_type = "shorter" if self.use_short_prompts else "full"
                print(f"✅ Switched to {prompt_type} prompts")
            elif choice == "3":
                print("▶️ Continuing grading...")
                break
            else:
                print("❌ Invalid choice.")
    
    def handle_problematic_assignments(self, failed_assignments, problematic_assignments):
        """Handle assignments that failed or have problematic scores."""
        total_issues = len(failed_assignments) + len(problematic_assignments)
        
        if total_issues == 0:
            print(f"\n🎉 All assignments processed successfully!")
            return
        
        print(f"\n📊 GRADING SUMMARY")
        print("=" * 50)
        print(f"✅ Successful: {len(self.results) - total_issues}")
        print(f"❌ Failed: {len(failed_assignments)}")
        print(f"⚠️  Outliers: {len(problematic_assignments)}")
        print("=" * 50)
        
        if failed_assignments:
            print(f"\n❌ FAILED ASSIGNMENTS ({len(failed_assignments)}):")
            for i, assignment in enumerate(failed_assignments, 1):
                print(f"   {i}. {assignment['assignment_name'][:60]}...")
                print(f"      Reason: {assignment['reason']}")
        
        if problematic_assignments:
            print(f"\n⚠️  SCORE OUTLIERS ({len(problematic_assignments)}):")
            for i, assignment in enumerate(problematic_assignments, 1):
                print(f"   {i}. {assignment['assignment_name'][:60]}...")
                print(f"      Score: {assignment['score']:.1f}/100")
                print(f"      Reason: {assignment['reason']}")
        
        # Ask user what to do
        print(f"\n🔧 RERUN OPTIONS:")
        print("1. Rerun failed assignments only")
        print("2. Rerun score outliers only") 
        print("3. Rerun both failed and outliers")
        print("4. Continue without rerunning")
        
        while True:
            choice = input("\nSelect option (1-4): ").strip()
            if choice == "1":
                self.rerun_assignments(failed_assignments)
                break
            elif choice == "2":
                self.rerun_assignments(problematic_assignments)
                break
            elif choice == "3":
                self.rerun_assignments(failed_assignments + problematic_assignments)
                break
            elif choice == "4":
                print("📝 Continuing without rerunning...")
                break
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
    
    def rerun_assignments(self, assignments_to_rerun):
        """Rerun specific assignments."""
        if not assignments_to_rerun:
            return
        
        print(f"\n🔄 RERUNNING {len(assignments_to_rerun)} ASSIGNMENTS")
        print("=" * 50)
        
        # Ask for modified settings
        print("🔧 Rerun settings:")
        use_different_delay = input("Use longer delay between API calls? (y/n): ").strip().lower() == 'y'
        use_shorter_prompt = input("Use shorter prompt to save tokens? (y/n): ").strip().lower() == 'y'
        
        original_prompt = self.course_config['prompt']
        if use_shorter_prompt:
            self.course_config['prompt'] = self.get_shorter_prompt()
            print("📝 Using shorter prompt to reduce token usage...")
        
        delay = 10 if use_different_delay else 5
        
        for i, assignment in enumerate(assignments_to_rerun, 1):
            print(f"\n🔄 [{i}/{len(assignments_to_rerun)}] Rerunning: {assignment['assignment_name'][:60]}...")
            
            # Remove the old result from self.results
            self.results = [r for r in self.results if r['assignment'] != assignment['assignment_name']]
            
            # Rerun the grading
            result = self.grade_single_file(assignment['file_path'], assignment['assignment_name'])
            if result:
                self.results.append(result)
                # Update real-time results with rerun status
                self.update_realtime_results(result, "rerun_completed")
                print(f"   ✅ New score: {result['total_score']:.1f}/100")
            else:
                # Update with failed rerun
                dummy_result = {
                    'assignment': assignment['assignment_name'],
                    'student_name': 'Unknown',
                    'components': {},
                    'total_score': 0,
                    'raw_response': 'Rerun failed'
                }
                self.update_realtime_results(dummy_result, "rerun_failed")
                print(f"   ❌ Still failed")
            
            if i < len(assignments_to_rerun):
                print(f"   ⏳ Waiting {delay} seconds...")
                time.sleep(delay)
        
        # Restore original prompt
        if use_shorter_prompt:
            self.course_config['prompt'] = original_prompt
        
        print(f"\n✅ Rerun completed!")

    def get_shorter_prompt(self):
        """Get a shorter version of the prompt to save tokens."""
        if self.course_config['course'] == '3702':
            return """Evaluate this 3702 student project based on these criteria. Assign scores and brief comments.

**Criteria:**
- Design (20 pts): Quality, creativity, AR appropriateness
- XR/Game Development (20 pts): Technical implementation, Unity skills  
- Demonstration and Video (10 pts): Demo quality
- Workshops (10 pts): Participation evidence
- Project Overview (15 pts): Documentation clarity
- Testing Feedback (10 pts): Testing approach
- Teamwork Review (10 pts): Collaboration reflection
- Quality of Document (5 pts): Writing quality

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:

{
  "student_name": "Extract from content",
  "components": {
    "Design": {"score": 0.0, "max_score": 20, "comment": "Brief feedback"},
    "XR/Game Development": {"score": 0.0, "max_score": 20, "comment": "Brief feedback"},
    "Demonstration and Video": {"score": 0.0, "max_score": 10, "comment": "Brief feedback"},
    "Workshops": {"score": 0.0, "max_score": 10, "comment": "Brief feedback"},
    "Project Overview": {"score": 0.0, "max_score": 15, "comment": "Brief feedback"},
    "Testing Feedback": {"score": 0.0, "max_score": 10, "comment": "Brief feedback"},
    "Teamwork Review": {"score": 0.0, "max_score": 10, "comment": "Brief feedback"},
    "Quality of Document and Academic Literacy": {"score": 0.0, "max_score": 5, "comment": "Brief feedback"}
  },
  "total_score": 0.0,
  "max_total_score": 100
}"""
        else:  # 7009
            return """Evaluate this 7009 performance analysis report. Assign scores and brief comments.

**Criteria:**
- Introduction & Reflection (20 pts): Quality of intro and AR app reflection
- Methodology & Test Setup (15 pts): Test setup explanation
- Performance Metrics Analysis (25 pts): FPS, memory, tracking analysis
- Comparative Analysis (20 pts): Device/platform comparison
- Discussion & Conclusion (15 pts): Findings interpretation
- Report Structure & Clarity (5 pts): Organization

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:

{
  "student_name": "Extract from content",
  "components": {
    "Introduction & Reflection on Final Product": {"score": 0.0, "max_score": 20, "comment": "Brief feedback"},
    "Methodology & Test Setup": {"score": 0.0, "max_score": 15, "comment": "Brief feedback"},
    "Performance Metrics Analysis": {"score": 0.0, "max_score": 25, "comment": "Brief feedback"},
    "Comparative Analysis": {"score": 0.0, "max_score": 20, "comment": "Brief feedback"},
    "Discussion, Optimization & Conclusion": {"score": 0.0, "max_score": 15, "comment": "Brief feedback"},
    "Report Structure & Clarity": {"score": 0.0, "max_score": 5, "comment": "Brief feedback"}
  },
  "total_score": 0.0,
  "max_total_score": 100
}"""

    def setup_realtime_results(self):
        """Setup simple real-time results tracking."""
        # Create results folder and files immediately
        self.results_folder = f"{self.course_config['course']}_grading_results"
        os.makedirs(self.results_folder, exist_ok=True)
        
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create initial files
        self.json_file = os.path.join(self.results_folder, f"grading_results_{self.timestamp}.json")
        self.csv_file = os.path.join(self.results_folder, f"grading_report_{self.timestamp}.csv")
        
        # Initialize JSON file
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        
        # Initialize CSV file with headers
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Student Name', 'Assignment', 'Component', 'Score', 'Max Score', 'Comment'])
        
        print(f"📄 Real-time JSON: {self.json_file}")
        print(f"📊 Real-time CSV: {self.csv_file}")
        print(f"💡 You can open these files in another window to monitor progress!")
    
    def update_realtime_results(self, result, status="completed"):
        """Update JSON and CSV files immediately after each assignment."""
        try:
            # Update JSON file
            with open(self.json_file, 'r', encoding='utf-8') as f:
                current_results = json.load(f)
            
            current_results.append(result)
            
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(current_results, f, indent=2, ensure_ascii=False)
            
            # Update CSV file
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                student_name = result['student_name']
                assignment = result['assignment']
                
                # Write component scores
                for component, details in result['components'].items():
                    writer.writerow([
                        student_name,
                        assignment,
                        component,
                        details.get('score', 0),
                        details.get('max_score', 0),
                        details.get('comment', '')
                    ])
                
                # Write total score
                writer.writerow([
                    student_name,
                    assignment,
                    'TOTAL',
                    result['total_score'],
                    100,
                    'Total score for all components'
                ])
                
        except Exception as e:
            print(f"Warning: Failed to update real-time results: {e}")

    def save_results(self):
        """Save final summary."""
        if not self.results:
            return
        
        if not self.results_folder or not self.timestamp:
            print("Warning: Results folder or timestamp not set")
            return
        
        print(f"📄 Final results saved in: {self.results_folder}")
        print(f"   • JSON: grading_results_{self.timestamp}.json")
        print(f"   • CSV: grading_report_{self.timestamp}.csv")

def main():
    """Main function."""
    print("🔑 Checking API key...")
    
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not found in environment variables!")
        print("Please create a .env file with: GEMINI_API_KEY=your_key_here")
        return
    
    print("✅ API key found!")
    
    grader = SimpleGrader()
    grader.show_menu()

if __name__ == "__main__":
    main()
