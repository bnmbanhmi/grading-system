import base64
import os
import cv2
import numpy as np
import google.genai as genai
from google.genai import types
import json
import os
import shutil # For cleaning up dummy data
from dotenv import load_dotenv
import time  # For rate limiting
import zipfile
import csv
from datetime import datetime
from comment_refiner import refine_all_assessment_comments, batch_refine_existing_results

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# IMPORTANT: Securely manage your API key. Do not hardcode it in the script.
# Use environment variables or a secret management tool.
# For example: genai.configure(api_key=os.environ["GEMINI_API_KEY"])
# Note: When using genai.Client directly, genai.configure() is not strictly needed
# unless you're also using the higher-level genai.GenerativeModel directly without a client.

# Define the model to be used for API calls
MODEL_NAME = "gemini-2.5-flash-preview-05-20"

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "7009ICT_grading_results")

# --- Helper Functions ---

def extract_code_from_zip(zip_path):
    """
    Extracts code files from a ZIP archive and returns their contents.
    
    Args:
        zip_path (str): Path to the ZIP file
        
    Returns:
        str: Combined content of all code files in the ZIP
    """
    code_content = []
    code_extensions = ['.cs', '.py', '.js', '.ts', '.cpp', '.c', '.h', '.java', '.kt', '.swift', '.css', '.html']
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if not file_info.is_dir():
                    file_ext = os.path.splitext(file_info.filename)[1].lower()
                    if file_ext in code_extensions:
                        try:
                            with zip_ref.open(file_info) as f:
                                content = f.read().decode('utf-8', errors='ignore')
                                code_content.append(f"// File: {file_info.filename}\n{content}\n\n")
                        except Exception as e:
                            print(f"Error reading {file_info.filename} from ZIP: {e}")
        
        if code_content:
            return "".join(code_content)
        else:
            return f"ZIP file contains no readable code files. Archive: {os.path.basename(zip_path)}"
            
    except Exception as e:
        print(f"Error extracting ZIP file {zip_path}: {e}")
        return f"Error reading ZIP file: {os.path.basename(zip_path)}"

# --- Helper Functions ---

def check_existing_video_frames(video_frames_dir):
    """
    Checks if video frames already exist in the specified directory.
    
    Args:
        video_frames_dir (str): Directory where video frames should be stored
        
    Returns:
        list: List of existing frame files if found, empty list otherwise
    """
    if not os.path.exists(video_frames_dir):
        return []
    
    # Look for image files (frames)
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
    existing_frames = []
    
    for file in os.listdir(video_frames_dir):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            full_path = os.path.join(video_frames_dir, file)
            if os.path.isfile(full_path):
                existing_frames.append(full_path)
    
    if existing_frames:
        print(f"Found {len(existing_frames)} existing video frames in {video_frames_dir}")
        return sorted(existing_frames)  # Sort to ensure consistent order
    
    return []

def extract_frames_from_video(video_path, output_dir, frame_interval_seconds=20):
    """
    Extracts frames from a video at a specified interval.

    Args:
        video_path (str): The path to the video file.
        output_dir (str): The directory to save the extracted frames.
        frame_interval_seconds (int): The interval in seconds between frame captures.

    Returns:
        list: A list of file paths for the saved images.
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return []

    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    if fps == 0:
        print(f"Error: Could not read video properties for {video_path}. Is it a valid video file?")
        return []
        
    frame_interval = int(fps * frame_interval_seconds)
    frame_count = 0
    image_count = 0
    saved_images = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % frame_interval == 0:
            image_filename = os.path.join(output_dir, f"frame_{image_count}.jpg")
            cv2.imwrite(image_filename, frame)
            saved_images.append(image_filename)
            image_count += 1
        
        frame_count += 1

    cap.release()
    print(f"Extracted {image_count} frames from {video_path} to {output_dir}")
    return saved_images

def extract_or_use_existing_frames(video_file, video_frames_dir, force_extract=False, frame_interval_seconds=20):
    """
    Extracts video frames or uses existing ones if available.
    
    Args:
        video_file (str): Path to the video file
        video_frames_dir (str): Directory where frames should be stored
        force_extract (bool): If True, extract frames even if they already exist
        frame_interval_seconds (int): Interval between frame captures
    
    Returns:
        list: List of frame file paths, empty list if extraction fails
    """
    if not force_extract:
        existing_frames = check_existing_video_frames(video_frames_dir)
        if existing_frames:
            print(f"Found {len(existing_frames)} existing video frames, skipping extraction")
            return existing_frames
    
    print("Extracting video frames...")
    return extract_frames_from_video(video_file, video_frames_dir, frame_interval_seconds)

def call_gemini_api(client: genai.Client, prompt: str, files=None):
    """
    Calls the Gemini API with the given prompt and files.

    Args:
        client (genai.Client): The Gemini API client instance.
        prompt (str): The text prompt for the model.
        files (list): A list of file paths (str) to be sent along with the prompt.

    Returns:
        dict: The parsed JSON response from the Gemini API.
              Returns a dictionary with 'score': 0 and 'comment': 'API Error...' on failure.
    """
    print("\n--- Making a Call to the Gemini API ---")
    print(f"Prompt (first 100 chars): {prompt[:100]}...")
    
    parts = [types.Part(text=prompt)]

    if files:
        print(f"Sending Files: {files}")
        for file_path in files:
            if not os.path.exists(file_path):
                print(f"Warning: File not found for API call, skipping: {file_path}")
                continue

            file_extension = os.path.splitext(file_path)[1].lower()
            
            # Simple mime type mapping for common files handled by Gemini multimodal models
            mime_type = None
            if file_extension in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            elif file_extension == '.png':
                mime_type = 'image/png'
            elif file_extension == '.gif':
                mime_type = 'image/gif'
            elif file_extension == '.py':
                mime_type = 'text/x-python'
            elif file_extension == '.cs':
                mime_type = 'text/x-csharp'
            elif file_extension == '.txt':
                mime_type = 'text/plain'
            elif file_extension == '.md': # Markdown files
                mime_type = 'text/markdown'
            # Add more specific text types as needed
            # For general documents (PDF, DOCX), extracting text content is often needed
            # rather than sending the raw binary file as a 'Part' unless the model
            # explicitly supports those binary types for direct ingestion.
            
            try:
                if mime_type and 'image' in mime_type:
                    with open(file_path, 'rb') as f:
                        parts.append(types.Part(inline_data=types.Blob(data=f.read(), mime_type=mime_type)))
                elif mime_type and 'text' in mime_type:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        parts.append(types.Part(text=f.read()))
                elif file_extension == '.zip':
                    # For zip files, extract and include code content
                    code_content = extract_code_from_zip(file_path)
                    parts.append(types.Part(text=code_content))
                    print(f"Extracted code from ZIP: {os.path.basename(file_path)}")
                elif file_extension in ['.pdf', '.docx', '.xlsx', '.pptx']:
                    # For document files, include file info for the API to understand
                    file_info = f"Document file: {os.path.basename(file_path)} (Type: {file_extension})"
                    parts.append(types.Part(text=file_info))
                    print(f"Including document info: {file_info}")
                else:
                    # Skip other binary files that can't be processed
                    print(f"Skipping unsupported file: {file_path} (file type: {file_extension})")
                    continue

            except Exception as e:
                print(f"Error processing file {file_path} for API: {e}")
                continue
    
    # Check if we have any content to send
    if len(parts) == 1:  # Only the prompt, no files were processed
        print("Warning: No files were successfully processed for API call")
        if files:
            # Add a fallback message about the files
            file_list = ", ".join([os.path.basename(f) for f in files])
            fallback_text = f"Note: The following files were submitted but could not be processed directly: {file_list}"
            parts.append(types.Part(text=fallback_text))
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[types.Content(role="user", parts=parts)]
        )
        # Add a small delay to avoid hitting rate limits
        time.sleep(1)
        
        # Assuming the model returns JSON directly as text if response_mime_type is set
        response_text = response.text
        if response_text:
            print(f"Gemini API Raw Response (first 200 chars): {response_text[:200]}...")
            
            # Extract JSON from response (handle text before/after JSON)
            try:
                # Look for JSON block markers
                if "```json" in response_text:
                    # Extract content between ```json and ```
                    start_idx = response_text.find("```json") + 7
                    end_idx = response_text.find("```", start_idx)
                    if end_idx != -1:
                        response_text = response_text[start_idx:end_idx].strip()
                    else:
                        response_text = response_text[start_idx:].strip()
                elif "{" in response_text and "}" in response_text:
                    # Try to extract JSON object from text
                    start_idx = response_text.find("{")
                    end_idx = response_text.rfind("}") + 1
                    response_text = response_text[start_idx:end_idx].strip()
                
                return json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to find a JSON array
                try:
                    if "[" in response_text and "]" in response_text:
                        start_idx = response_text.find("[")
                        end_idx = response_text.rfind("]") + 1
                        response_text = response_text[start_idx:end_idx].strip()
                        return json.loads(response_text)
                except json.JSONDecodeError:
                    pass
                
                # If all parsing fails, return error
                print(f"Error decoding JSON from Gemini API response")
                print(f"Response text: {response_text}")
                return {"score": 0, "comment": f"API returned non-JSON or invalid JSON format"}
        else:
            print("Empty response from Gemini API")
            return {"score": 0, "comment": "Empty response from API"}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Gemini API response: {e}")
        print(f"Response text: {response_text}")
        return {"score": 0, "comment": f"API returned non-JSON or invalid JSON: {e}"}
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print("⚠️  API quota exceeded. Waiting before retrying...")
            time.sleep(30)  # Wait 30 seconds for quota to reset
            return {"score": 0, "comment": "API quota exceeded - partial grading completed"}
        return {"score": 0, "comment": f"Gemini API call failed: {e}"}


# --- Main Grading Functions ---

def grade_coding_quality(client: genai.Client, code_files: list):
    """
    Grades the coding quality based on the provided files.
    """
    prompt = """
    Give me a score based on the following criteria:

    Coding Quality (/20 pts)
    - Excellent (15.1 to 20 pts): Code is well-structured, readable, and follows best practices (e.g., comments, modularity). .zip file is organised and functional. No major bugs. 
    - Good (11.1 to 15 pts): Code is functional and mostly readable but has minor issues (e.g., inconsistent comments, less modularity). .zip file is organised. 
    - Satisfactory (7.1 to 11 pts): Code works but lacks structure, readability, or has moderate issues. .zip file is somewhat disorganised. 
    - Needs Improvement (0.1 to 7 pts) : Code is poorly written, unreadable, or non-functional. .zip file is missing or unusable. 
    - No Evidence (0 pts): No Evidence
    
    The output should be a JSON object with 'score' (integer or float) and 'comment' (string).
    """
    response_json = call_gemini_api(client, prompt, files=code_files)
    return response_json # call_gemini_api now returns parsed JSON

def grade_video_presentation(client: genai.Client, image_files: list):
    """
    Grades the video presentation based on extracted frames.
    """
    prompt = """
    Provide short feedback on the video, of which multiple images are provided as frames.
    Assume that transitions between scenes may not be smooth due to the sampling of frames and give the maximum score for the smoothness of transitions.
    Assume the video includes a voice-over and sound.
    
    - Video Presentation (/35 pts)
    + Excellent (27.1 to 35 pts): Video is clear, engaging, and within 3 minutes. Effectively showcases prototype’s key features and functionality with smooth execution. High production quality (audio, visuals). 
    + Good (20.1 to 27 pts): Video is clear and within time limit. Shows most key features but may lack polish or minor clarity issues. Good production quality. 
    + Satisfactory (13.1 to 20 pts): Video is somewhat clear but exceeds time limit or misses some features. Functionality is partially demonstrated. Average production quality. 
    + Needs Improvement (0.1 to 13 pts): Video is unclear, significantly over/under time, or fails to demonstrate prototype functionality. Poor production quality. 
    + No Evidence (0 pts): No submission

    The output should be a JSON object with 'score' (integer or float) and 'comment' (string).
    """
    response_json = call_gemini_api(client, prompt, files=image_files)
    return response_json # call_gemini_api now returns parsed JSON

def grade_individual_contribution(client: genai.Client, project_files: list, group_name: str):
    """
    Performs dedicated assessment of Individual Contribution component with enhanced focus and criteria.
    """
    prompt = f"""
    You are an expert academic assessor specializing in team project evaluation. Your task is to assess the INDIVIDUAL CONTRIBUTION component for group {group_name} based on the provided project documents.

    # ASSESSMENT FOCUS: Individual Contribution (/10 pts)

    ## SPECIFIC INSTRUCTIONS:
    1. **SEARCH THOROUGHLY** - Look for any document sections, slides, or references that mention:
       - Individual roles and responsibilities
       - Team member contributions 
       - Division of work/tasks
       - Personal accountability statements
       - Individual effort descriptions
       - Team collaboration details
       - Workload distribution
       
    2. **LOOK FOR MULTIPLE EVIDENCE SOURCES**:
       - Presentation slides about team roles
       - Project documentation with individual sections
       - Asset registers with creator/contributor information
       - README files with contribution details
       - Individual reflection statements
       - Team collaboration descriptions

    3. **EVALUATION CRITERIA** (Be generous if evidence exists):
       + **Excellent (7.1 to 10 pts)**: Each team member's role and contributions are clearly defined and significant, with evidence of balanced workload. Specific examples of individual contributions are provided.
       + **Good (5.1 to 7 pts)**: Contributions are defined but may be uneven or lack some detail. Most members show clear involvement with identifiable roles.
       + **Satisfactory (3.1 to 5 pts)**: Contributions are described but with limited detail. Some roles unclear but basic workload distribution is evident.
       + **Needs Improvement (0.1 to 3 pts)**: Contributions are minimally described or significantly unbalanced. Very limited evidence of individual involvement.
       + **No Evidence (0 pts)**: No mention of individual contributions found anywhere in the documents.

    ## ASSESSMENT APPROACH:
    - **Assume teams have addressed this requirement** unless clearly absent
    - **Give credit for any evidence** of individual contribution documentation
    - **Look beyond just presentation slides** - check all document types
    - **Consider implicit evidence** such as different writing styles, specialized sections, role-specific content
    - **Value clear role definition** even if detailed contribution lists are not provided

    ## OUTPUT FORMAT:
    Provide your assessment as a JSON object with:
    - 'score' (integer or float between 0-10)
    - 'comment' (detailed string explaining your assessment and what evidence you found)
    - 'evidence_found' (list of specific documents/sections where contribution information was located)

    ## IMPORTANT NOTES:
    - This is a critical component that most successful teams address well
    - If you find ANY evidence of individual contribution planning or documentation, score accordingly
    - Be specific about WHERE you found the evidence in your comment
    - Consider that contribution evidence might be embedded within broader project documentation
    """
    
    response_json = call_gemini_api(client, prompt, files=project_files)
    
    # Validate response format
    if isinstance(response_json, dict) and 'score' in response_json:
        return response_json
    else:
        print(f"Warning: Individual contribution assessment returned unexpected format: {response_json}")
        return {
            "score": 5, 
            "comment": "Assessment completed but response format was unclear. Please review documents manually for individual contribution details.",
            "evidence_found": ["Response format error - manual review needed"]
        }

def grade_all_components(client: genai.Client, project_files: list, video_score_comment: dict, coding_score_comment: dict, group_name: str):
    """
    Performs grading of the remaining project components (excluding video and coding which are graded separately).
    Individual Contribution is assessed using a dedicated function for enhanced accuracy.
    """
    # Grade Individual Contribution using the dedicated function
    individual_contribution_result = grade_individual_contribution(client, project_files, group_name)
    
    prompt = f"""
    Assess the student's submission for a Unity AR project based on the provided files and the following assessments that have already been completed separately.

    Previous Assessments:
    - Video Presentation Score: {video_score_comment.get('score', 'N/A')}/35
    - Video Comment: {video_score_comment.get('comment', 'N/A')}
    - Coding Quality Score: {coding_score_comment.get('score', 'N/A')}/20  
    - Coding Comment: {coding_score_comment.get('comment', 'N/A')}

    # Project Objective
    Design and develop an Augmented Reality (AR) application that enhances business and consumer engagement. The application can be tailored for various industries, such as retail, tourism, education, or real estate, providing interactive and immersive experiences.

    # Project Scope:
    - Implement AR features such as product visualisation, interactive advertisements, virtual guides, or promotional experiences.
    - Utilise marker-based or markerless tracking to display AR content in real-world environments.
    - Ensure the application is user-friendly and provides valuable engagement for customers or businesses.
    - Optimise performance and conduct an in-depth analysis of rendering efficiency, tracking stability, and system resource usage.

    # Assessment Criteria for REMAINING Components (Total: 35 points)
    Provide a score (integer or float) and detailed feedback (string) for each of the following criteria:

    ## 1. Project Description, Design & Development Process (/20 pts)
    + Excellent (15.1 to 20 pts): In-class presentation clearly articulates project purpose, design rationale, and development process with strong technical detail. Delivery is engaging, well-paced, and professional within 10 minutes. Visual aids (e.g., PowerPoint) are effective. Q&A responses are confident, accurate, and relevant. 
    + Good (11.1 to 15 pts): Presentation covers purpose, design, and process but lacks some depth or clarity. Delivery is clear but less engaging. Visual aids are used but may be less effective. Q&A responses are mostly accurate but may lack depth. 
    + Satisfactory (7.1 to 11 pts) : Presentation addresses purpose, design, and process minimally, with limited detail. Delivery is rushed, slightly over/under time, or lacks engagement. Visual aids are basic or poorly organised. Q&A responses are vague or partially relevant. 
    + Needs Improvement (0.1 to 7 pts): Presentation is vague, lacks technical detail, or fails to explain design/development. Delivery is disorganised, significantly off-time, or unprofessional. Visual aids are minimal or absent. Q&A responses are inaccurate or absent. 
    + No Presentation (0 pts):  

    ## 2. Testing & Validation (/10 pts)
    - Excellent (7.1 to 10 pt): Testing methodology is thorough, well-documented, and clearly presented. Validation confirms prototype functionality with evidence (e.g., test results). 
    - Good (5.1 to 7 pts): Testing is adequate with some documentation. Validation is shown but may lack depth or clarity. 
    - Satisfactory (1.1 to 5 pts) : Testing is minimal or poorly documented. Validation is incomplete or unclear. 
    - Needs Improvement (0.1 to 1 pts): Testing and validation are absent or insufficiently addressed. 
    - No Evidence (0 pts): No Evidence

    ## 3. Supporting Asset Management (/5 pts)
    - Excellent (3.1 to 5 pts): Asset register is complete, well-organised, and clearly documents all project assets (e.g., images, libraries). 
    - Good (2.1 to 3 pts): Asset register is mostly complete but may have minor gaps or organisation issues 
    - Satisfactory (1.1 to 2 pts): Asset register is incomplete or poorly organised, with missing assets. 
    - Needs Improvement (0.1 to 1 pts): Asset register is missing or severely lacking in detail. 
    - No Evidence (0 pts): No Evidence 

    The output should be a JSON object containing a list of dictionaries, where each dictionary has 'component' (string), 'score' (integer or float), and 'comment' (string). Ensure you assess these 3 remaining components only.
    """
    
    response_json = call_gemini_api(client, prompt, files=project_files)
    
    # Ensure the response is a list as expected by the prompt
    if isinstance(response_json, list):
        # Add the Individual Contribution result to the list
        individual_contribution_component = {
            "component": "Individual Contribution", 
            "score": individual_contribution_result.get('score', 0), 
            "comment": individual_contribution_result.get('comment', 'No specific feedback available.')
        }
        
        # Insert Individual Contribution as the second component (after Project Description)
        combined_results = []
        for i, component in enumerate(response_json):
            combined_results.append(component)
            # Insert Individual Contribution after the first component (Project Description)
            if i == 0:
                combined_results.append(individual_contribution_component)
        
        return combined_results
    else:
        print(f"Warning: Expected a list of grades for 'grade_all_components' but got: {response_json}")
        # Return a mock structure with Individual Contribution included if the API doesn't return a list
        return [
            {"component": "Project Description, Design & Development Process", "score": 0, "comment": response_json.get('comment', 'API response format error.')},
            {"component": "Individual Contribution", "score": individual_contribution_result.get('score', 0), "comment": individual_contribution_result.get('comment', 'Enhanced assessment completed separately.')},
            {"component": "Testing & Validation", "score": 0, "comment": "No specific feedback due to API response format."},
            {"component": "Supporting Asset Management", "score": 0, "comment": "No specific feedback due to API response format."}
        ]


def grade_single_group(client: genai.Client, group_folder: str, group_name: str):
    """
    Grades a single group and returns the assessment results.
    
    Args:
        client: The Gemini API client
        group_folder: Path to the group's organized folder
        group_name: Name of the group (e.g., 'GC1', 'GC2')
    
    Returns:
        dict: Complete grading results for the group
    """
    print(f"\n{'='*60}")
    print(f"GRADING GROUP: {group_name}")
    print(f"Folder: {group_folder}")
    print(f"{'='*60}")
    
    # Ensure video_frames directory exists
    video_frames_dir = os.path.join(group_folder, "video_frames")
    os.makedirs(video_frames_dir, exist_ok=True)

    # 1. Process Video
    video_folder = os.path.join(group_folder, "videos")
    video_file = None
    if os.path.exists(video_folder):
        video_files = [f for f in os.listdir(video_folder) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv'))]
        if video_files:
            video_file = os.path.join(video_folder, video_files[0])
            print(f"Found video: {video_files[0]}")

    if video_file and os.path.exists(video_file) and os.path.getsize(video_file) > 0:
        print(f"Processing video: {video_file}")
        
        # Extract frames or use existing ones
        video_frames = extract_or_use_existing_frames(video_file, video_frames_dir)
        
        if video_frames:
            print(f"Using {len(video_frames)} frames for grading")
            video_assessment = grade_video_presentation(client, video_frames)
        else:
            print("Failed to extract or find frames from video")
            video_assessment = {"score": 0, "comment": "Failed to extract or find frames from video file."}
    else:
        print("No valid video file found")
        video_assessment = {"score": 0, "comment": "No video submitted or video file is empty/invalid."}

    # 2. Grade Code
    code_folder = os.path.join(group_folder, "source_code")
    code_files = []
    if os.path.exists(code_folder):
        all_items = os.listdir(code_folder)
        print(f"Found items in source_code: {all_items}")
        
        # Recursively find all code files in source_code directory and subdirectories
        code_extensions = ['.cs', '.py', '.js', '.ts', '.cpp', '.c', '.h', '.java', '.kt', '.swift']
        
        def find_code_files_recursively(directory):
            """Recursively find all code files in directory and subdirectories."""
            found_files = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    # Include code files and zip files
                    if file_ext in code_extensions or file.endswith('.zip'):
                        found_files.append(file_path)
            return found_files
        
        code_files = find_code_files_recursively(code_folder)
        print(f"Code files to analyze: {[os.path.relpath(f, code_folder) for f in code_files]}")
    
    if code_files:
        coding_assessment = grade_coding_quality(client, code_files)
    else:
        print("No code files found")
        coding_assessment = {"score": 0, "comment": "No code submitted."}

    # 3. Grade All Other Components
    document_folder = os.path.join(group_folder, "documents")
    
    other_files = []
    if os.path.exists(document_folder):
        doc_files = [os.path.join(document_folder, f) for f in os.listdir(document_folder) 
                    if os.path.isfile(os.path.join(document_folder, f))]
        other_files.extend(doc_files)
        print(f"Document files found (including converted presentations): {[os.path.basename(f) for f in doc_files]}")

    # Call the comprehensive grading function
    if other_files:
        final_grades = grade_all_components(client, other_files, video_assessment, coding_assessment, group_name)
    else:
        print("No documents found")
        final_grades = [
            {"component": "Project Description, Design & Development Process", "score": 0, "comment": "No documents submitted."},
            {"component": "Individual Contribution", "score": 0, "comment": "No documents submitted."},
            {"component": "Testing & Validation", "score": 0, "comment": "No documents submitted."},
            {"component": "Supporting Asset Management", "score": 0, "comment": "No documents submitted."}
        ]

    # Compile results
    total_score = 0
    
    # Add scores from separately graded components
    total_score += video_assessment.get('score', 0)  # /35 points
    total_score += coding_assessment.get('score', 0)  # /20 points
    
    # Handle remaining components from grade_all_components (45 points total)
    display_components = []
    if isinstance(final_grades, list):
        for item in final_grades:
            component_name = item.get('component', 'Unknown')[:46]
            score = str(item.get('score', 'N/A'))[:5]
            comment = item.get('comment', '')[:75]
            print(f"| {component_name:<46} | {score:<5} | {comment:<75} |")
            # Store full untruncated data in JSON
            display_components.append({"component": component_name, "score": score, "comment": comment})
            total_score += score
    else:
        print(f"Warning: 'grade_all_components' did not return a list or was invalid. Got: {final_grades}")
        display_components = [
            {"component": "Project Description, Design & Development Process", "score": 0, "comment": final_grades.get('comment', 'API response format error.')},
            {"component": "Individual Contribution", "score": 0, "comment": "No specific feedback due to API response format."},
            {"component": "Testing & Validation", "score": 0, "comment": "No specific feedback due to API response format."},
            {"component": "Supporting Asset Management", "score": 0, "comment": "No specific feedback due to API response format."}
        ]

    # Keep video frames for future use (no cleanup)
    print(f"Video frames preserved in: {video_frames_dir}")

    return {
        "group_name": group_name,
        "total_score": total_score,
        "video_assessment": video_assessment,
        "coding_assessment": coding_assessment,
        "component_assessments": display_components,
        "timestamp": json.dumps({"graded_at": str(os.path.getctime(group_folder))})
    }


def save_grading_results(group_name: str, results: dict):
    """
    Saves grading results to a JSON file.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    results_file = os.path.join(RESULTS_DIR, f"{group_name}_grading_results.json")
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to: {results_file}")
    return results_file


def display_grading_results(results: dict):
    """
    Displays grading results in a formatted table.
    """
    group_name = results["group_name"]
    total_score = results["total_score"]
    video_assessment = results["video_assessment"]
    coding_assessment = results["coding_assessment"]
    display_components = results["component_assessments"]
    
    print(f"\n--- FINAL GRADING REPORT FOR {group_name} ---")
    print(f"Video Score: {video_assessment.get('score', 'N/A')}/35")
    print(f"Comment: {video_assessment.get('comment', 'N/A')}\n")

    print(f"Coding Score: {coding_assessment.get('score', 'N/A')}/20")
    print(f"Comment: {coding_assessment.get('comment', 'N/A')}\n")
    
    print("| Component                                      | Score | Comment                                                                                             |")
    print("|------------------------------------------------|-------|-----------------------------------------------------------------------------------------------------|")

    for item in display_components:
        component = item.get('component', 'Unknown')[:46]
        score = str(item.get('score', 'N/A'))[:5]
        comment = item.get('comment', '')[:75]
        print(f"| {component:<46} | {score:<5} | {comment:<75} |")

    print(f"\nTotal Score: {total_score}/100")


def generate_csv_report():
    """
    Generates a CSV file containing all grading results from JSON files.
    """
    if not os.path.exists(RESULTS_DIR):
        print(f"Error: Results directory '{RESULTS_DIR}' not found.")
        return None
    
    # Get all JSON files in the results directory
    json_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('_grading_results.json')]
    
    if not json_files:
        print(f"No grading result files found in '{RESULTS_DIR}'.")
        return None
    
    print(f"Found {len(json_files)} grading result files.")
    
    # Prepare CSV data
    csv_data = []
    
    for json_file in json_files:
        json_path = os.path.join(RESULTS_DIR, json_file)
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            group_name = data.get('group_name', 'Unknown')
            total_score = data.get('total_score', 0)
            
            # Video assessment
            video_assessment = data.get('video_assessment', {})
            video_score = video_assessment.get('score', 0)
            video_comment = video_assessment.get('comment', '').replace('\n', ' ').replace('\r', ' ')
            
            # Coding assessment
            coding_assessment = data.get('coding_assessment', {})
            coding_score = coding_assessment.get('score', 0)
            coding_comment = coding_assessment.get('comment', '').replace('\n', ' ').replace('\r', ' ')
            
            # Component assessments
            component_assessments = data.get('component_assessments', [])
            
            # Initialize component scores and comments
            project_desc_score = 0
            project_desc_comment = ""
            individual_contrib_score = 0
            individual_contrib_comment = ""
            testing_score = 0
            testing_comment = ""
            asset_mgmt_score = 0
            asset_mgmt_comment = ""
            
            # Extract component data
            for component in component_assessments:
                comp_name = component.get('component', '')
                comp_score = component.get('score', 0)
                comp_comment = component.get('comment', '').replace('\n', ' ').replace('\r', ' ')
                
                if 'Project Description' in comp_name or 'Design & Development' in comp_name:
                    project_desc_score = comp_score
                    project_desc_comment = comp_comment
                elif 'Individual Contribution' in comp_name:
                    individual_contrib_score = comp_score
                    individual_contrib_comment = comp_comment
                elif 'Testing' in comp_name or 'Validation' in comp_name:
                    testing_score = comp_score
                    testing_comment = comp_comment
                elif 'Asset Management' in comp_name or 'Supporting Asset' in comp_name:
                    asset_mgmt_score = comp_score
                    asset_mgmt_comment = comp_comment
            
            # Create row for CSV
            row = {
                'Group Name': group_name,
                'Total Score': total_score,
                'Video Score (/35)': video_score,
                'Video Comment': video_comment,
                'Coding Score (/20)': coding_score,
                'Coding Comment': coding_comment,
                'Project Description Score (/20)': project_desc_score,
                'Project Description Comment': project_desc_comment,
                'Individual Contribution Score (/10)': individual_contrib_score,
                'Individual Contribution Comment': individual_contrib_comment,
                'Testing & Validation Score (/10)': testing_score,
                'Testing & Validation Comment': testing_comment,
                'Asset Management Score (/5)': asset_mgmt_score,
                'Asset Management Comment': asset_mgmt_comment
            }
            
            csv_data.append(row)
            print(f"✓ Processed {group_name}: Total Score {total_score}/100")
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    if not csv_data:
        print("No valid data found to export.")
        return None
    
    # Sort by group name
    csv_data.sort(key=lambda x: x['Group Name'])
    
    # Generate CSV filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"grading_results_summary_{timestamp}.csv"
    csv_path = os.path.join(os.getcwd(), csv_filename)
    
    # Write CSV file
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Group Name', 'Total Score',
                'Video Score (/35)', 'Video Comment',
                'Coding Score (/20)', 'Coding Comment',
                'Project Description Score (/20)', 'Project Description Comment',
                'Individual Contribution Score (/10)', 'Individual Contribution Comment',
                'Testing & Validation Score (/10)', 'Testing & Validation Comment',
                'Asset Management Score (/5)', 'Asset Management Comment'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
        
        print(f"\n✅ CSV report generated successfully!")
        print(f"📄 File: {csv_filename}")
        print(f"📁 Location: {csv_path}")
        print(f"📊 Contains {len(csv_data)} group results")
        
        # Print summary statistics
        if csv_data:
            total_scores = [row['Total Score'] for row in csv_data]
            avg_score = sum(total_scores) / len(total_scores)
            max_score = max(total_scores)
            min_score = min(total_scores)
            
            print(f"\n📈 Summary Statistics:")
            print(f"   Average Score: {avg_score:.1f}/100")
            print(f"   Highest Score: {max_score}/100")
            print(f"   Lowest Score: {min_score}/100")
        
        return csv_path
        
    except Exception as e:
        print(f"Error writing CSV file: {e}")
        return None


def get_available_groups():
    """
    Gets list of available organized group folders.
    """
    current_dir = os.getcwd()
    
    # Look for organized_assignments directory in multiple possible locations
    possible_paths = [
        os.path.join(current_dir, "organized_assignments"),  # Root directory
        os.path.join(current_dir, "7009ICT_AdvancedInAR", "7009ICT_AdvancedInAR", "organized_assignments"),  # Course subdirectory
    ]
    
    organized_assignments_dir = None
    for path in possible_paths:
        if os.path.exists(path):
            organized_assignments_dir = path
            break
    
    groups = []
    if not organized_assignments_dir:
        return groups
    
    for item in os.listdir(organized_assignments_dir):
        item_path = os.path.join(organized_assignments_dir, item)
        if item.endswith('_organized' ) and os.path.isdir(item_path):
            group_name = item.replace('_organized', '')
            groups.append((group_name, item_path))  # Return full path instead of just item name
    
    return sorted(groups)


def check_existing_results(group_name: str):
    """
    Checks if grading results already exist for a group.
    """
    results_file = os.path.join(RESULTS_DIR, f"{group_name}_grading_results.json")
    return os.path.exists(results_file)


def choose_grading_mode():
    """
    Allows user to choose between batch grading mode, interactive mode, CSV export, score normalization, or comment refinement.
    
    Returns:
        str: 'batch' for batch mode, 'interactive' for interactive mode, 'csv' for CSV export, 'normalize' for score normalization, 'refine' for comment refinement, 'quit' to exit
    """
    print("\n=== GRADING SYSTEM MENU ===")
    print("1. Interactive Mode: Grade groups with confirmation after each (recommended)")
    print("2. Batch Mode: Grade all groups without interruption")
    print("3. Export CSV Report: Generate CSV file from existing grading results")
    print("4. Normalize Scores: Adjust scores to meet distribution requirements (mean=65, range=55-90)")
    print("5. Refine Comments: Make existing feedback sound more natural and human-like")
    print("6. Quit")
    
    while True:
        choice = input("\nSelect option (1/2/3/4/5/6): ").strip()
        
        if choice == '1':
            print("✓ Interactive mode selected - you'll be prompted after each group")
            return 'interactive'
        elif choice == '2':
            print("✓ Batch mode selected - all groups will be processed automatically")
            return 'batch'
        elif choice == '3':
            print("✓ CSV export selected - generating report from existing results")
            return 'csv'
        elif choice == '4':
            print("✓ Score normalization selected - adjusting grades to meet distribution requirements")
            return 'normalize'
        elif choice == '5':
            print("✓ Comment refinement selected - improving feedback tone and naturalness")
            return 'refine'
        elif choice == '6':
            print("Exiting grading system.")
            return 'quit'
        else:
            print("Invalid choice. Please enter 1, 2, 3, 4, 5, or 6.")


def main():
    """
    Main function to orchestrate the grading process for all groups.
    """
    print("=== AR PROJECT GRADING SYSTEM ===")
    print("Initializing...")
    
    # Initialize the Gemini API client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set!")
        print("Please set your API key in the .env file")
        return
    
    client = genai.Client(api_key=api_key)
    print("✓ Gemini API client initialized")
    
    # Get available groups
    available_groups = get_available_groups()
    if not available_groups:
        print("No organized group folders found!")
        print("Expected folders like: organized_assignments/GC1_organized, organized_assignments/GC2_organized, etc.")
        print("Make sure you have run the assignment organizer first to create the organized_assignments/ directory.")
        return
    
    print(f"Found {len(available_groups)} groups: {[g[0] for g in available_groups]}")
    
    # Choose grading mode
    grading_mode = choose_grading_mode()
    if grading_mode == 'quit':
        return
    elif grading_mode == 'csv':
        # Generate CSV report and exit
        csv_path = generate_csv_report()
        if csv_path:
            print(f"\n✅ CSV report successfully generated!")
            print(f"You can now open: {os.path.basename(csv_path)}")
        else:
            print("❌ Failed to generate CSV report.")
        return
    elif grading_mode == 'normalize':
        # Normalize scores and exit
        print(f"\n🔄 Starting score normalization process...")
        success = normalize_scores(client)
        if success:
            print(f"\n✅ Score normalization completed successfully!")
            print(f"All scores have been adjusted to meet distribution requirements.")
            print(f"Backups of original scores saved in {os.path.join(RESULTS_DIR, 'pre_normalization_backup')}/")
        else:
            print("❌ Failed to normalize scores.")
        return
    elif grading_mode == 'refine':
        # Refine comments and exit
        print(f"\n✨ Starting comment refinement process...")
        print("This will make all feedback sound more natural and human-like...")
        print("Note: This is for graduate-level (7009ICT) course feedback")
        
        try:
            batch_refine_existing_results(client, RESULTS_DIR, "graduate")
            print(f"\n✅ Comment refinement completed successfully!")
            print(f"All feedback has been refined to sound more natural and professorial.")
            print(f"📁 Refined results saved to: {os.path.join(RESULTS_DIR, 'refined_comments')}/")
            print(f"📋 Original files preserved in: {RESULTS_DIR}/")
        except Exception as e:
            print(f"❌ Failed to refine comments: {e}")
        return
    
    # Process each group
    for group_name, group_folder in available_groups:
        print(f"\n{'='*80}")
        print(f"Processing Group: {group_name}")
        
        # Check if results already exist
        if check_existing_results(group_name):
            print(f"⚠️  Results file already exists for {group_name}")
            if grading_mode == 'batch':
                print(f"Batch mode: Skipping {group_name} (results exist)")
                continue
            else:  # interactive mode
                choice = input(f"Do you want to re-grade {group_name}? (y/n/skip): ").lower().strip()
                if choice == 'skip' or choice == 's':
                    print(f"Skipping {group_name}")
                    continue
                elif choice != 'y' and choice != 'yes':
                    print(f"Skipping {group_name}")
                    continue
        
        try:
            # Grade the group
            results = grade_single_group(client, group_folder, group_name)
            
            # Display results
            display_grading_results(results)
            
            # Save results
            results_file = save_grading_results(group_name, results)
            
            print(f"\n✓ Successfully graded {group_name}")
            
            # Handle continuation based on mode
            if grading_mode == 'interactive' and group_name != available_groups[-1][0]:  # Not the last group
                choice = input(f"\nContinue to next group? (y/n/quit): ").lower().strip()
                if choice == 'n' or choice == 'no' or choice == 'quit' or choice == 'q':
                    print("Grading session ended by user.")
                    break
            elif grading_mode == 'batch':
                print(f"Batch mode: Continuing to next group automatically...")
        
        except KeyboardInterrupt:
            print(f"\n\nGrading interrupted by user")
            break
        except Exception as e:
            print(f"Error grading {group_name}: {e}")
            if grading_mode == 'interactive':
                choice = input(f"Continue to next group? (y/n): ").lower().strip()
                if choice == 'n' or choice == 'no':
                    break
            else:  # batch mode
                print(f"Batch mode: Continuing despite error...")
    
    print(f"\n{'='*80}")
    print("GRADING SESSION COMPLETE")
    print(f"Results saved in: {RESULTS_DIR}/")
    print(f"{'='*80}")


def normalize_scores(client: genai.Client):
    """
    Normalizes all grading results to meet specific distribution requirements using AI refinement.
    Target distribution: mean=70, highest≤85, lowest≥55
    Prioritizes files from pre_normalization_backup folder if available.
    """
    if not os.path.exists(RESULTS_DIR):
        print(f"Error: Results directory '{RESULTS_DIR}' not found.")
        return False
    
    # Check if backup folder exists and has files - prioritize these for normalization
    backup_dir = os.path.join(RESULTS_DIR, "pre_normalization_backup")
    source_dir = RESULTS_DIR
    
    if os.path.exists(backup_dir):
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith('_grading_results.json')]
        if backup_files:
            source_dir = backup_dir
            print(f"🔄 Using files from backup folder for normalization: {backup_dir}")
        else:
            print(f"📁 Backup folder exists but is empty, using main results folder")
    else:
        print(f"📁 No backup folder found, using main results folder")
    
    # Get all JSON files from the chosen source directory
    json_files = [f for f in os.listdir(source_dir) if f.endswith('_grading_results.json')]
    
    if not json_files:
        print(f"No grading result files found in '{source_dir}'.")
        return False
    
    print(f"Found {len(json_files)} grading result files for normalization from '{source_dir}'.")
    
    # Load all grading results from source directory
    all_results = []
    for json_file in json_files:
        source_path = os.path.join(source_dir, json_file)
        # Always prepare to save back to main results directory
        target_path = os.path.join(RESULTS_DIR, json_file)
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_results.append((json_file, target_path, data))
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            continue
    
    if not all_results:
        print("No valid grading results found to normalize.")
        return False
    
    # Calculate current distribution
    current_scores = [data.get('total_score', 0) for _, _, data in all_results]
    current_mean = sum(current_scores) / len(current_scores)
    current_min = min(current_scores)
    current_max = max(current_scores)
    
    print(f"\n📊 Current Score Distribution:")
    print(f"   Mean: {current_mean:.1f}/100")
    print(f"   Range: {current_min} - {current_max}")
    
    # Target distribution - favor outstanding groups with higher scores
    target_mean = 70
    target_min = 55
    target_max = 85
    
    print(f"\n🎯 Target Score Distribution:")
    print(f"   Mean: {target_mean}/100")
    print(f"   Range: {target_min} - {target_max}")
    print(f"   📈 Outstanding groups should score 80-85 to reward excellence")
    
    # Check if normalization is needed
    needs_normalization = (
        abs(current_mean - target_mean) > 2 or 
        current_min < target_min or 
        current_max > target_max
    )
    
    if not needs_normalization:
        print("\n✅ Scores already meet the target distribution requirements.")
        return True
    
    print(f"\n⚙️ Normalization required. Processing {len(all_results)} groups...")
    
    # Create backup directory and backups only if we're reading from main results (not from backup)
    backup_dir = os.path.join(RESULTS_DIR, "pre_normalization_backup")
    
    if source_dir == RESULTS_DIR:  # Only create backups if reading from main directory
        os.makedirs(backup_dir, exist_ok=True)
        print(f"📋 Creating backups of original scores in: {backup_dir}")
        
        # Create backups for all files first
        for json_file, json_path, data in all_results:
            backup_path = os.path.join(backup_dir, json_file)
            source_path = os.path.join(RESULTS_DIR, json_file)
            shutil.copy2(source_path, backup_path)
    else:
        print(f"📋 Reading from backup folder - no new backups needed")
    
    # Prepare all assessments for collective AI normalization
    all_assessments = []
    for json_file, json_path, data in all_results:
        assessment = {
            "group_name": data.get('group_name', 'Unknown'),
            "current_total": data.get('total_score', 0),
            "video_assessment": data.get('video_assessment', {}),
            "coding_assessment": data.get('coding_assessment', {}),
            "component_assessments": data.get('component_assessments', [])
        }
        all_assessments.append(assessment)
    
    print(f"\n📊 Processing all {len(all_assessments)} groups with statistical normalization...")
    
    # Use statistical linear transformation to preserve relative rankings
    normalized_scores = statistical_normalize_scores(current_scores, target_mean, target_min, target_max)
    
    # Prepare normalized results
    normalized_results = []
    
    if normalized_scores and len(normalized_scores) == len(all_results):
        # Update all data with normalized scores using fair statistical adjustment
        for i, (json_file, json_path, original_data) in enumerate(all_results):
            # Create a deep copy of the original data to preserve all content
            import copy
            normalized_data = copy.deepcopy(original_data)
            
            # Calculate adjustment factor based on statistical normalization
            original_total = current_scores[i]
            target_total = normalized_scores[i]
            
            if original_total > 0:
                adjustment_factor = target_total / original_total
                # No artificial bounds - let statistical method determine fair adjustments
            else:
                adjustment_factor = 1.0
            
            # Apply proportional adjustment to all score components
            
            # Update video assessment score proportionally
            if 'video_assessment' in original_data and 'score' in original_data['video_assessment']:
                original_video_score = original_data['video_assessment']['score']
                new_video_score = round(original_video_score * adjustment_factor, 1)
                # Cap video score at reasonable bounds (0-50)
                new_video_score = max(0, min(50, new_video_score))
                normalized_data['video_assessment']['score'] = new_video_score
            
            # Update coding assessment score proportionally  
            if 'coding_assessment' in original_data and 'score' in original_data['coding_assessment']:
                original_coding_score = original_data['coding_assessment']['score']
                new_coding_score = round(original_coding_score * adjustment_factor, 1)
                # Cap coding score at reasonable bounds (0-50)
                new_coding_score = max(0, min(50, new_coding_score))
                normalized_data['coding_assessment']['score'] = new_coding_score
            
            # Update component assessment scores proportionally
            if 'component_assessments' in original_data and isinstance(original_data['component_assessments'], list):
                for component in normalized_data['component_assessments']:
                    if 'score' in component:
                        original_component_score = component['score']
                        new_component_score = round(original_component_score * adjustment_factor, 1)
                        # Cap component scores at reasonable bounds (0-20 for most components)
                        max_component_score = 20
                        new_component_score = max(0, min(max_component_score, new_component_score))
                        component['score'] = new_component_score
            
            # Calculate actual total from adjusted components
            video_score = normalized_data.get('video_assessment', {}).get('score', 0)
            coding_score = normalized_data.get('coding_assessment', {}).get('score', 0)
            component_total = sum(comp.get('score', 0) for comp in normalized_data.get('component_assessments', []) if isinstance(comp, dict))
            
            calculated_total = video_score + coding_score + component_total
            normalized_data['total_score'] = round(calculated_total, 1)
            
            # Add normalization metadata
            backup_path = os.path.join(backup_dir, json_file)
            normalized_data['normalization_info'] = {
                "normalized_at": datetime.now().isoformat(),
                "original_score": original_total,
                "target_distribution": {"mean": target_mean, "min": target_min, "max": target_max},
                "pre_normalization_backup": backup_path,
                "normalization_method": "tiered_statistical_normalization",
                "adjustment_factor": round(adjustment_factor, 3)
            }
            
            normalized_results.append((json_path, normalized_data))
            print(f"   ✓ {normalized_data['group_name']}: {original_total:.1f} → {normalized_data['total_score']:.1f} (factor: {adjustment_factor:.3f})")
    else:
        print(f"   ⚠️ Statistical normalization failed")
        print(f"   📄 Keeping original scores for all groups")
        # Keep original data if normalization fails
        for json_file, json_path, data in all_results:
            normalized_results.append((json_path, data))
    
    # Save normalized results directly to the main grading results folder 
    # (backups are already created in pre_normalization_backup/)
    print(f"\n💾 Saving normalized results to {RESULTS_DIR}...")
    for json_path, normalized_data in normalized_results:
        try:
            # Save directly to the original file path
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(normalized_data, f, indent=2, ensure_ascii=False)
            print(f"   ✓ Updated {os.path.basename(json_path)}")
        except Exception as e:
            print(f"Error saving {os.path.basename(json_path)}: {e}")
    
    # Verify final distribution
    final_scores = [data.get('total_score', 0) for _, data in normalized_results]
    final_mean = sum(final_scores) / len(final_scores)
    final_min = min(final_scores)
    final_max = max(final_scores)
    
    print(f"\n✅ Normalization Complete!")
    print(f"📊 Final Score Distribution:")
    print(f"   Mean: {final_mean:.1f}/100 (target: {target_mean})")
    print(f"   Range: {final_min} - {final_max} (target: {target_min}-{target_max})")
    print(f"📁 Backups saved to: {backup_dir}")
    
    return True


def statistical_normalize_scores(original_scores, target_mean, target_min, target_max):
    """
    Performs tiered statistical normalization that rewards top performers with smaller adjustments.
    Top performers (90th percentile+) get minimal adjustments to preserve their excellence.
    
    Args:
        original_scores: List of original scores
        target_mean: Target mean score
        target_min: Target minimum score
        target_max: Target maximum score
    
    Returns:
        List of normalized scores with preserved relative rankings and top performer protection
    """
    import numpy as np
    
    original_scores = np.array(original_scores)
    current_mean = np.mean(original_scores)
    current_min = np.min(original_scores)
    current_max = np.max(original_scores)
    
    print(f"📊 Tiered Statistical Normalization (Top Performer Protection):")
    print(f"   Original: mean={current_mean:.1f}, range={current_min}-{current_max}")
    print(f"   Target: mean={target_mean:.1f}, range={target_min}-{target_max}")
    
    if current_max == current_min:
        # All scores are the same - set all to target mean
        return [target_mean] * len(original_scores)
    
    # Define performance tiers based on percentiles
    percentile_90 = np.percentile(original_scores, 90)
    percentile_75 = np.percentile(original_scores, 75)
    percentile_25 = np.percentile(original_scores, 25)
    
    print(f"   Performance Tiers:")
    print(f"     🏆 Exceptional (90th+): {percentile_90:.1f}+ (minimal adjustment)")
    print(f"     🥈 Good (75-90th): {percentile_75:.1f}-{percentile_90:.1f} (light adjustment)")
    print(f"     📊 Average (25-75th): {percentile_25:.1f}-{percentile_75:.1f} (standard adjustment)")
    print(f"     📈 Needs Help (<25th): <{percentile_25:.1f} (stronger adjustment)")
    
    # Calculate what the linear normalization would produce
    normalized_01 = (original_scores - current_min) / (current_max - current_min)
    target_range = target_max - target_min
    linear_scaled = normalized_01 * target_range + target_min
    current_scaled_mean = np.mean(linear_scaled)
    mean_adjustment = target_mean - current_scaled_mean
    linear_final = np.clip(linear_scaled + mean_adjustment, target_min, target_max)
    
    # Apply tiered adjustments
    tiered_scores = np.zeros_like(original_scores, dtype=float)
    
    for i, original_score in enumerate(original_scores):
        linear_score = linear_final[i]
        adjustment_needed = linear_score - original_score
        
        # Determine tier and adjustment factor
        if original_score >= percentile_90:
            # Exceptional: Only 20% of the adjustment (protect excellence)
            tier_factor = 0.2
            tier = "🏆 Exceptional"
        elif original_score >= percentile_75:
            # Good: 50% of the adjustment
            tier_factor = 0.5
            tier = "🥈 Good"
        elif original_score >= percentile_25:
            # Average: 100% of the adjustment
            tier_factor = 1.0
            tier = "📊 Average"
        else:
            # Needs Help: 130% of the adjustment (extra boost)
            tier_factor = 1.3
            tier = "📈 Needs Help"
        
        # Apply tiered adjustment
        tiered_adjustment = adjustment_needed * tier_factor
        tiered_scores[i] = original_score + tiered_adjustment
        
        # Ensure bounds
        tiered_scores[i] = max(target_min, min(target_max, tiered_scores[i]))
        
        print(f"     {tier}: {original_score:.1f} → {tiered_scores[i]:.1f} (factor: {tier_factor:.1f})")
    
    # Fine-tune to achieve exact target mean
    current_tiered_mean = np.mean(tiered_scores)
    final_adjustment = target_mean - current_tiered_mean
    
    # Apply final adjustment proportionally, but protect top performers more
    for i in range(len(tiered_scores)):
        if original_scores[i] >= percentile_90:
            # Top performers get minimal final adjustment
            tiered_scores[i] += final_adjustment * 0.1
        elif original_scores[i] >= percentile_75:
            # Good performers get moderate final adjustment
            tiered_scores[i] += final_adjustment * 0.5
        else:
            # Others get full final adjustment
            tiered_scores[i] += final_adjustment
    
    # Final bounds check
    tiered_scores = np.clip(tiered_scores, target_min, target_max)
    
    # Verify and report
    final_mean = np.mean(tiered_scores)
    final_min = np.min(tiered_scores)
    final_max = np.max(tiered_scores)
    
    print(f"   Result: mean={final_mean:.1f}, range={final_min:.1f}-{final_max:.1f}")
    print(f"   🏆 Top performers protected from excessive normalization")
    print(f"   📈 Relative rankings preserved with performance-based adjustments")
    
    return tiered_scores.tolist()


def normalize_all_scores_with_ai(client: genai.Client, all_assessments: list, target_mean: float, target_min: float, target_max: float,
                                current_mean: float, current_min: float, current_max: float):
    """
    Uses AI to normalize all group scores collectively in a single prompt for optimal distribution adjustment.
    
    Args:
        client: Gemini API client
        all_assessments: List of assessment dictionaries with group data
        target_mean, target_min, target_max: Target distribution parameters
        current_mean, current_min, current_max: Current distribution stats
        
    Returns:
        List of normalized assessment dictionaries, or None if failed
    """
    try:
        # Build comprehensive prompt with all group data
        groups_summary = "\n".join([
            f"Group {i+1}: {assessment['group_name']} - Current Score: {assessment['current_total']}/100"
            for i, assessment in enumerate(all_assessments)
        ])
        
        detailed_assessments = []
        for i, assessment in enumerate(all_assessments):
            video_score = assessment['video_assessment'].get('score', 0) if assessment['video_assessment'] else 0
            coding_score = assessment['coding_assessment'].get('score', 0) if assessment['coding_assessment'] else 0
            
            detailed_assessments.append(f"""
GROUP {i+1}: {assessment['group_name']}
- Current Total Score: {assessment['current_total']}/100
- Video Assessment Score: {video_score}/50
- Coding Assessment Score: {coding_score}/50
- Component Assessments: {len(assessment.get('component_assessments', []))} items""")
        
        detailed_data = "\n".join(detailed_assessments)
        
        prompt = f"""
You are an academic grading specialist tasked with determining target total scores for normalization to meet institutional distribution requirements while maintaining relative performance differences.

CURRENT CLASS DISTRIBUTION:
- Mean: {current_mean:.1f}/100
- Range: {current_min} - {current_max}
- Total Groups: {len(all_assessments)}

TARGET DISTRIBUTION REQUIREMENTS:
- Mean: EXACTLY {target_mean}/100 (CRITICAL - this must be achieved)
- Range: {target_min} - {target_max}
- Maximum allowed score: {target_max} (only for exceptional performers)
- STRICT MEAN CONTROL: The average of ALL scores must equal {target_mean}

CURRENT GROUP SCORES (ranked by performance):
{groups_summary}

DETAILED GROUP DATA:
{detailed_data}

MATHEMATICAL REQUIREMENTS FOR MEAN = {target_mean}:
With {len(all_assessments)} groups, total points needed = {len(all_assessments)} × {target_mean} = {len(all_assessments) * target_mean}

MANDATORY DISTRIBUTION STRATEGY (to achieve mean of {target_mean}):
1. TOP 1-2 groups ONLY: 82-85 points (exceptional performers)
2. GOOD performers (next 2-3 groups): 72-76 points
3. MAJORITY of groups (middle performers): 65-71 points  
4. LOWER performers (2-3 groups): 58-64 points
5. LOWEST performers (1-2 groups): 55-57 points

CRITICAL CONSTRAINTS:
- MOST groups must score in 65-71 range to maintain mean of {target_mean}
- VERY FEW groups can score above 75 (this pushes mean too high)
- ONLY 1-2 exceptional groups should get 80+ scores
- VERIFY: Sum of all scores ÷ {len(all_assessments)} = {target_mean}

SCORING ALLOCATION (strict adherence required):
- 82-85 points: Maximum 2 groups (top performers only)
- 72-76 points: Maximum 3 groups (good performers)
- 65-71 points: Majority of groups ({len(all_assessments)-7} or more groups)
- 58-64 points: 2-3 groups (lower performers)
- 55-57 points: 1-2 groups (lowest performers)

Please provide target total scores for ALL groups in the following JSON format:
```json
[
  {{
    "group_name": "Group1Name", 
    "total_score": target_total_score
  }},
  ... (continue for all {len(all_assessments)} groups)
]
```

FINAL VALIDATION CHECKLIST:
- Return exactly {len(all_assessments)} group results
- Sum of all total_scores = {len(all_assessments) * target_mean}
- Average of all total_scores = {target_mean}
- Only 1-2 groups above 80 points
- Most groups in 65-71 range
- Maintain relative ranking of current performance"""

        print(f"   🤖 Sending collective normalization request to AI...")
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4000,
            )
        )
        
        if not response or not response.text:
            print(f"   ⚠️ Empty response from AI")
            return None
            
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Find JSON array in the response
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        
        if json_start == -1 or json_end == 0:
            print(f"   ⚠️ No JSON array found in AI response")
            return None
            
        json_str = response_text[json_start:json_end]
        
        try:
            normalized_assessments = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ Failed to parse AI response as JSON: {e}")
            return None
        
        # Validate the response
        if not isinstance(normalized_assessments, list) or len(normalized_assessments) != len(all_assessments):
            print(f"   ⚠️ AI returned {len(normalized_assessments) if isinstance(normalized_assessments, list) else 'invalid'} results, expected {len(all_assessments)}")
            return None
        
        # Validate each assessment
        for i, assessment in enumerate(normalized_assessments):
            if not isinstance(assessment, dict):
                print(f"   ⚠️ Assessment {i+1} is not a dictionary")
                return None
                
            total_score = assessment.get('total_score', 0)
            if not isinstance(total_score, (int, float)) or total_score < target_min or total_score > target_max:
                print(f"   ⚠️ Assessment {i+1} has invalid total_score: {total_score}")
                return None
        
        # Calculate final statistics
        final_scores = [assessment['total_score'] for assessment in normalized_assessments]
        final_mean = sum(final_scores) / len(final_scores)
        final_min = min(final_scores)
        final_max = max(final_scores)
        
        print(f"   ✅ AI normalization successful!")
        print(f"   📊 Collective adjustment result:")
        print(f"      Mean: {current_mean:.1f} → {final_mean:.1f} (target: {target_mean})")
        print(f"      Range: {current_min}-{current_max} → {final_min}-{final_max} (target: {target_min}-{target_max})")
        
        return normalized_assessments
        
    except Exception as e:
        print(f"   ❌ Error in AI normalization: {e}")
        return None


def refine_scores_with_ai(client: genai.Client, assessment: dict, target_mean: float, target_min: float, target_max: float, 
                         current_mean: float, current_min: float, current_max: float, current_index: int, total_count: int):
    """
    Uses AI to refine individual scores while maintaining evaluation integrity and moving toward target distribution.
    NOTE: This function is kept for backward compatibility but collective normalization is preferred.
    """
    try:
        # Calculate suggested adjustment direction
        current_score = assessment['current_total']
        adjustment_direction = "maintain"
        
        if current_mean > target_mean and current_score > target_mean:
            adjustment_direction = "slightly decrease"
        elif current_mean < target_mean and current_score < target_mean:
            adjustment_direction = "slightly increase"
        elif current_score > target_max:
            adjustment_direction = "decrease to fit maximum"
        elif current_score < target_min:
            adjustment_direction = "increase to meet minimum"
        
        prompt = f"""
You are an academic grading specialist tasked with refining assessment scores to meet institutional distribution requirements while maintaining evaluation integrity.

CURRENT ASSESSMENT DATA:
Group: {assessment['group_name']}
Current Total Score: {current_score}/100

Video Assessment: {assessment['video_assessment'].get('score', 0)}/35
Comment: {assessment['video_assessment'].get('comment', 'N/A')}

Coding Assessment: {assessment['coding_assessment'].get('score', 0)}/20  
Comment: {assessment['coding_assessment'].get('comment', 'N/A')}

Component Scores:
{chr(10).join([f"- {comp.get('component', 'Unknown')}: {comp.get('score', 0)} points - {comp.get('comment', 'N/A')}" for comp in assessment['component_assessments']])}

DISTRIBUTION CONTEXT:
- Current class mean: {current_mean:.1f}/100, Target: {target_mean}/100
- Current range: {current_min}-{current_max}, Target range: {target_min}-{target_max}
- Processing: {current_index}/{total_count} assessments
- Suggested adjustment: {adjustment_direction}

TASK:
Refine this assessment to help achieve the target distribution while:
1. Maintaining the relative quality evaluation and educational feedback
2. Preserving the core assessment rationale in comments
3. Ensuring all component scores are reasonable and justified
4. Keeping total score within {target_min}-{target_max} range

Scoring Scale Reference:
- Video Presentation: /35 (Excellent: 31-35, Good: 26-30, Satisfactory: 21-25, Needs Improvement: 10-20, Poor: 0-9)
- Coding Quality: /20 (Excellent: 18-20, Good: 15-17, Satisfactory: 12-14, Needs Improvement: 8-11, Poor: 0-7)
- Project Description: /20 (Excellent: 18-20, Good: 15-17, Satisfactory: 12-14, Needs Improvement: 8-11, Poor: 0-7)
- Individual Contribution: /10 (Excellent: 9-10, Good: 7-8, Satisfactory: 6, Needs Improvement: 4-5, Poor: 0-3)
- Testing & Validation: /10 (Excellent: 9-10, Good: 7-8, Satisfactory: 6, Needs Improvement: 4-5, Poor: 0-3)
- Asset Management: /5 (Excellent: 5, Good: 4, Satisfactory: 3, Needs Improvement: 2, Poor: 0-1)

Return a JSON object with the refined assessment:
{{
    "total_score": <calculated_total>,
    "video_assessment": {{"score": <score>, "comment": "<refined_comment>"}},
    "coding_assessment": {{"score": <score>, "comment": "<refined_comment>"}},
    "component_assessments": [
        {{"component": "Project Description, Design & Development Process", "score": <score>, "comment": "<refined_comment>"}},
        {{"component": "Individual Contribution", "score": <score>, "comment": "<refined_comment>"}},
        {{"component": "Testing & Validation", "score": <score>, "comment": "<refined_comment>"}},
        {{"component": "Supporting Asset Management", "score": <score>, "comment": "<refined_comment>"}}
    ]
}}
"""

        response = call_gemini_api(client, prompt)
        
        if response and isinstance(response, dict):
            # Validate the response structure
            required_keys = ['total_score', 'video_assessment', 'coding_assessment', 'component_assessments']
            if all(key in response for key in required_keys):
                # Ensure total score is within acceptable range
                total_score = response.get('total_score', 0)
                if target_min <= total_score <= target_max:
                    return response
                else:
                    print(f"   ⚠️ AI suggested score {total_score} outside target range {target_min}-{target_max}")
                    return None
            else:
                print(f"   ⚠️ AI response missing required keys")
                return None
        else:
            print(f"   ⚠️ Invalid AI response format")
            return None
            
    except Exception as e:
        print(f"   ❌ Error in AI refinement: {e}")
        return None

# Execute the main function when script is run directly
if __name__ == "__main__":
    main()