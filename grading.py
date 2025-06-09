import base64
import os
import cv2
import google.genai as genai
from google.genai import types
import json
import shutil # For cleaning up dummy data
from dotenv import load_dotenv
import time  # For rate limiting
import zipfile

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
    + Excellent (27.1 to 35 pts): Video is clear, engaging, and within 3 minutes. Effectively showcases the prototype’s key features and functionality with smooth execution. High production quality (audio, visuals).
    + Good (20.1 to 27 pts): Video is clear and within the time limit. Shows most key features but may have minor polish issues or clarity issues. Good production quality.
    + Satisfactory (13.1 to 20 pts): Video is somewhat clear but exceeds the time limit or misses some features. Functionality is partially demonstrated. Average production quality.
    + Needs Improvement (0.1 to 13 pts): Video is unclear, significantly over/under time, or fails to demonstrate prototype functionality. Poor production quality.
    + No Evidence (0 pts): No submission

    The output should be a JSON object with 'score' (integer or float) and 'comment' (string).
    """
    response_json = call_gemini_api(client, prompt, files=image_files)
    return response_json # call_gemini_api now returns parsed JSON

def grade_all_components(client: genai.Client, project_files: list, video_score_comment: dict, coding_score_comment: dict):
    """
    Performs grading of the remaining project components (excluding video and coding which are graded separately).
    """
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

    # Assessment Criteria for REMAINING Components (Total: 45 points)
    Provide a score (integer or float) and detailed feedback (string) for each of the following criteria:

    ## 1. Project Description, Design & Development Process (/20 pts)
    - Excellent (15.1-20 pts): Comprehensive project description with clear objectives, well-documented design process, detailed development methodology, and thorough documentation
    - Good (11.1-15 pts): Clear project description with good design documentation and development process explanation
    - Satisfactory (7.1-11 pts): Basic project description with some design and development documentation
    - Needs Improvement (0.1-7 pts): Poor or incomplete project description and documentation
    - No Evidence (0 pts): No project description or documentation

    ## 2. Individual Contribution (/10 pts)
    - Excellent (7.6-10 pts): Clear evidence of individual contributions, well-documented roles and responsibilities, individual reflection on learning
    - Good (5.6-7.5 pts): Good documentation of individual contributions with some evidence of personal involvement
    - Satisfactory (3.6-5.5 pts): Basic documentation of individual contributions
    - Needs Improvement (0.1-3.5 pts): Unclear or minimal individual contribution documentation
    - No Evidence (0 pts): No individual contribution documentation

    ## 3. Testing & Validation (/10 pts)
    - Excellent (7.6-10 pts): Comprehensive testing plan, systematic validation, user testing results, performance analysis
    - Good (5.6-7.5 pts): Good testing approach with validation evidence
    - Satisfactory (3.6-5.5 pts): Basic testing and validation documentation
    - Needs Improvement (0.1-3.5 pts): Minimal or poor testing documentation
    - No Evidence (0 pts): No testing or validation evidence

    ## 4. Supporting Asset Management (/5 pts)
    - Excellent (3.8-5 pts): Well-organized assets, proper file structure, comprehensive asset documentation
    - Good (2.8-3.7 pts): Good asset organization with documentation
    - Satisfactory (1.8-2.7 pts): Basic asset management
    - Needs Improvement (0.1-1.7 pts): Poor asset organization
    - No Evidence (0 pts): No asset management

    The output should be a JSON object containing a list of dictionaries, where each dictionary has 'component' (string), 'score' (integer or float), and 'comment' (string). Ensure you assess these 4 remaining components only.
    """
    response_json = call_gemini_api(client, prompt, files=project_files)
    
    # Ensure the response is a list as expected by the prompt
    if isinstance(response_json, list):
        return response_json
    else:
        print(f"Warning: Expected a list of grades for 'grade_all_components' but got: {response_json}")
        # Return a mock or error structure if the API doesn't return a list
        return [
            {"component": "Project Description, Design & Development Process", "score": 0, "comment": response_json.get('comment', 'API response format error.')},
            {"component": "Individual Contribution", "score": 0, "comment": "No specific feedback due to API response format."},
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
        final_grades = grade_all_components(client, other_files, video_assessment, coding_assessment)
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
            component_name = item.get('component', 'Unknown Component')
            score = item.get('score', 0)
            comment = item.get('comment', '')
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
    results_dir = "grading_results"
    os.makedirs(results_dir, exist_ok=True)
    
    results_file = os.path.join(results_dir, f"{group_name}_grading_results.json")
    
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
        if item.endswith('_organized') and os.path.isdir(item_path):
            group_name = item.replace('_organized', '')
            groups.append((group_name, item_path))  # Return full path instead of just item name
    
    return sorted(groups)


def check_existing_results(group_name: str):
    """
    Checks if grading results already exist for a group.
    """
    results_dir = "grading_results"
    results_file = os.path.join(results_dir, f"{group_name}_grading_results.json")
    return os.path.exists(results_file)


def choose_grading_mode():
    """
    Allows user to choose between batch grading mode and interactive mode.
    
    Returns:
        str: 'batch' for batch mode, 'interactive' for interactive mode
    """
    print("\n=== GRADING MODE SELECTION ===")
    print("1. Interactive Mode: Confirm after each group (recommended for careful review)")
    print("2. Batch Mode: Process all groups without interruption")
    print("3. Quit")
    
    while True:
        choice = input("\nSelect grading mode (1/2/3): ").strip()
        
        if choice == '1':
            print("✓ Interactive mode selected - you'll be prompted after each group")
            return 'interactive'
        elif choice == '2':
            print("✓ Batch mode selected - all groups will be processed automatically")
            return 'batch'
        elif choice == '3':
            print("Exiting grading system.")
            return 'quit'
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


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
    print(f"Results saved in: grading_results/")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()