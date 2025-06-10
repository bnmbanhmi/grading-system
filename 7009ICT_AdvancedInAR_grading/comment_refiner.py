
import json
import os
from datetime import datetime
import google.genai as genai
from google.genai import types


def refine_comment_tone(client: genai.Client, original_comment: str, component_name: str, score: float, course_level: str = "graduate"):
    """
    Refines a single comment to sound more natural and human-like while preserving all technical content.
    
    Args:
        client: Gemini API client
        original_comment: The original AI-generated comment
        component_name: Name of the assessment component
        score: The score for this component
        course_level: "undergraduate" or "graduate" to adjust tone appropriately
    
    Returns:
        str: Refined comment that sounds more professorial and natural
    """
    
    # Determine appropriate tone based on course level
    if course_level == "graduate":
        tone_guidance = """
        - Use sophisticated academic language appropriate for graduate students
        - Focus on research methodology, innovation, and advanced technical concepts
        - Emphasize critical analysis and scholarly contribution
        - Sound like a professor reviewing graduate research work
        """
        professor_persona = "an experienced professor reviewing graduate-level research in Augmented Reality"
    else:  # undergraduate
        tone_guidance = """
        - Use encouraging yet professional academic language for undergraduate students
        - Focus on learning outcomes, practical implementation, and skill development
        - Balance constructive feedback with recognition of effort
        - Sound like a supportive professor guiding undergraduate learning
        """
        professor_persona = "a supportive professor teaching undergraduate Augmented Reality courses"
    
    prompt = f"""
You are {professor_persona}. Your task is to rewrite the following assessment comment to sound more natural, human-like, and professorial while preserving ALL technical content and maintaining the same evaluation level.

ORIGINAL COMMENT:
"{original_comment}"

COMPONENT: {component_name}
SCORE: {score} points
COURSE LEVEL: {course_level.title()}

REFINEMENT GUIDELINES:
{tone_guidance}

ESSENTIAL REQUIREMENTS:
1. **Preserve ALL technical content** - Don't remove any specific technical details, examples, or findings
2. **Maintain the same evaluation level** - Don't make it more positive or negative than the original
3. **Keep the same length approximately** - Don't significantly shorten or lengthen
4. **Sound like a human professor** - Use natural academic language, not robotic AI phrasing
5. **Use conversational academic tone** - Replace phrases like "The documentation demonstrates..." with more natural alternatives
6. **Add subtle personality** - Use varied sentence structures and natural transitions
7. **Maintain professionalism** - Keep it academic and appropriate for formal assessment

AVOID:
- Robotic phrases like "The system demonstrates", "The implementation shows", "The documentation indicates"
- Overly formal or repetitive sentence structures
- AI-typical phrasing that sounds mechanical
- Changing the technical assessment or adding/removing factual content

Please respond with ONLY the refined comment text, no additional formatting, explanations, or metadata:"""

    try:
        # Debug: Check if we have a valid original comment
        if not original_comment or original_comment.strip() == "":
            print(f"   ⚠️ Empty original comment for {component_name}")
            return original_comment
        
        # Handle very long comments by truncating if necessary
        max_comment_length = 2000  # Reasonable limit for input
        if len(original_comment) > max_comment_length:
            print(f"   ⚠️ Comment too long ({len(original_comment)} chars), truncating for {component_name}")
            original_comment = original_comment[:max_comment_length] + "..."
            
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Slightly higher for more natural variation
                max_output_tokens=1000,
            )
        )
        
        # Debug: Check response details
        if not response:
            print(f"   ⚠️ No response object from AI for {component_name}")
            return original_comment
            
        if not hasattr(response, 'text') or not response.text:
            print(f"   ⚠️ Response has no text content for {component_name}")
            return original_comment
        
        if response and response.text:
            refined_comment = response.text.strip()
            
            # Extract just the refined comment from the response
            # Look for patterns like quoted text or specific markers
            if '"' in refined_comment:
                # Try to extract text between quotes
                quote_start = refined_comment.find('"')
                quote_end = refined_comment.rfind('"')
                if quote_start != -1 and quote_end != -1 and quote_end > quote_start:
                    refined_comment = refined_comment[quote_start+1:quote_end]
            elif 'REFINED COMMENT' in refined_comment.upper():
                # Look for the refined comment section
                lines = refined_comment.split('\n')
                refined_lines = []
                in_refined_section = False
                for line in lines:
                    if 'REFINED COMMENT' in line.upper() or in_refined_section:
                        in_refined_section = True
                        if line.strip() and not line.strip().startswith('**') and 'REFINED COMMENT' not in line.upper():
                            refined_lines.append(line.strip())
                if refined_lines:
                    refined_comment = ' '.join(refined_lines)
            
            # Clean up any remaining formatting
            refined_comment = refined_comment.strip()
            if refined_comment.startswith('"') and refined_comment.endswith('"'):
                refined_comment = refined_comment[1:-1]
                
            print(f"   ✅ Successfully refined {component_name} comment")
            return refined_comment
        else:
            print(f"   ⚠️ Empty response from AI for {component_name}")
            return original_comment
            
    except Exception as e:
        print(f"   ❌ Error refining comment for {component_name}: {e}")
        return original_comment


def refine_all_assessment_comments(client: genai.Client, assessment_data: dict, course_level: str = "graduate"):
    """
    Refines all comments in an assessment to sound more natural and human-like in a single API call.
    
    Args:
        client: Gemini API client
        assessment_data: Complete assessment dictionary
        course_level: "undergraduate" or "graduate"
    
    Returns:
        dict: Assessment data with refined comments
    """
    
    refined_data = assessment_data.copy()
    
    print(f"   🎨 Refining all comments for {assessment_data.get('group_name', 'Unknown')} ({course_level} level)")
    
    # Collect all comments to refine in one batch
    comments_to_refine = []
    
    # Video assessment comment
    if 'video_assessment' in refined_data and 'comment' in refined_data['video_assessment']:
        comments_to_refine.append({
            'type': 'video_assessment',
            'component': 'Video Assessment',
            'comment': refined_data['video_assessment']['comment'],
            'score': refined_data['video_assessment'].get('score', 0)
        })
    
    # Coding assessment comment  
    if 'coding_assessment' in refined_data and 'comment' in refined_data['coding_assessment']:
        comments_to_refine.append({
            'type': 'coding_assessment',
            'component': 'Coding Assessment',
            'comment': refined_data['coding_assessment']['comment'],
            'score': refined_data['coding_assessment'].get('score', 0)
        })
    
    # Component assessment comments
    if 'component_assessments' in refined_data and isinstance(refined_data['component_assessments'], list):
        for i, component in enumerate(refined_data['component_assessments']):
            if isinstance(component, dict) and 'comment' in component:
                component_name = component.get('component', f'Component {i+1}')
                comments_to_refine.append({
                    'type': 'component_assessment',
                    'index': i,
                    'component': component_name,
                    'comment': component['comment'],
                    'score': component.get('score', 0)
                })
    
    if not comments_to_refine:
        print(f"   ⚠️ No comments found to refine")
        return refined_data
    
    # Process all comments in a single API call
    try:
        refined_comments = refine_comments_batch(client, comments_to_refine, course_level)
        
        # Apply the refined comments back to the data structure
        for i, comment_data in enumerate(comments_to_refine):
            if i < len(refined_comments):
                refined_comment = refined_comments[i]
                
                if comment_data['type'] == 'video_assessment':
                    refined_data['video_assessment']['comment'] = refined_comment
                elif comment_data['type'] == 'coding_assessment':
                    refined_data['coding_assessment']['comment'] = refined_comment
                elif comment_data['type'] == 'component_assessment':
                    idx = comment_data['index']
                    refined_data['component_assessments'][idx]['comment'] = refined_comment
        
        print(f"   ✅ Successfully refined {len(refined_comments)} comments in batch")
        
    except Exception as e:
        print(f"   ❌ Error in batch refinement: {e}")
        return assessment_data  # Return original if refinement fails
    
    # Add refinement metadata
    if 'refinement_info' not in refined_data:
        refined_data['refinement_info'] = {}
    
    refined_data['refinement_info'].update({
        "refined_at": datetime.now().isoformat(),
        "course_level": course_level,
        "refinement_version": "2.0_batch"
    })
    
    return refined_data


def refine_comments_batch(client: genai.Client, comments_list: list, course_level: str = "graduate"):
    """
    Refines multiple comments in a single API call for efficiency.
    
    Args:
        client: Gemini API client
        comments_list: List of comment dictionaries with 'component', 'comment', 'score'
        course_level: "undergraduate" or "graduate"
    
    Returns:
        list: List of refined comments in the same order
    """
    
    # Determine appropriate tone based on course level
    if course_level == "graduate":
        tone_guidance = """
        - Use sophisticated academic language appropriate for graduate students
        - Focus on research methodology, innovation, and advanced technical concepts
        - Emphasize critical analysis and scholarly contribution
        - Sound like a professor reviewing graduate research work
        """
        professor_persona = "an experienced professor reviewing graduate-level research in Augmented Reality"
    else:  # undergraduate
        tone_guidance = """
        - Use encouraging yet professional academic language for undergraduate students
        - Focus on learning outcomes, practical implementation, and skill development
        - Balance constructive feedback with recognition of effort
        - Sound like a supportive professor guiding undergraduate learning
        """
        professor_persona = "a supportive professor teaching undergraduate Augmented Reality courses"
    
    # Build the batch prompt
    prompt = f"""You are {professor_persona}. Your task is to refine multiple assessment comments to sound more natural, human-like, and professorial while preserving ALL technical content and maintaining the same evaluation levels.

COURSE LEVEL: {course_level.title()}

REFINEMENT GUIDELINES:
{tone_guidance}

ESSENTIAL REQUIREMENTS FOR ALL COMMENTS:
1. **Preserve ALL technical content** - Don't remove any specific technical details, examples, or findings
2. **Maintain the same evaluation level** - Don't make comments more positive or negative than originals
3. **Keep similar length** - Don't significantly shorten or lengthen comments
4. **Sound like a human professor** - Use natural academic language, not robotic AI phrasing
5. **Use conversational academic tone** - Replace phrases like "The documentation demonstrates..." with more natural alternatives
6. **Add subtle personality** - Use varied sentence structures and natural transitions
7. **Maintain professionalism** - Keep it academic and appropriate for formal assessment

AVOID:
- Robotic phrases like "The system demonstrates", "The implementation shows", "The documentation indicates"
- Overly formal or repetitive sentence structures
- AI-typical phrasing that sounds mechanical
- Changing the technical assessment or adding/removing factual content

COMMENTS TO REFINE:

"""
    
    # Add each comment to the prompt
    for i, comment_data in enumerate(comments_list, 1):
        prompt += f"""
COMMENT {i} - {comment_data['component']} (Score: {comment_data['score']} points):
"{comment_data['comment']}"

"""
    
    prompt += f"""
Please respond with exactly {len(comments_list)} refined comments, numbered and separated clearly. Format your response as:

REFINED COMMENT 1:
[refined version of comment 1]

REFINED COMMENT 2:
[refined version of comment 2]

[continue for all comments...]

Respond with ONLY the refined comments in this format, no additional explanations."""

    try:
        # Handle very long prompts by truncating individual comments if necessary
        max_total_length = 15000  # Conservative limit for total prompt length
        if len(prompt) > max_total_length:
            print(f"   ⚠️ Batch prompt too long ({len(prompt)} chars), truncating comments")
            # Truncate individual comments proportionally
            total_comment_length = sum(len(c['comment']) for c in comments_list)
            max_comment_length = 1500 // len(comments_list)  # Distribute available space
            
            for comment_data in comments_list:
                if len(comment_data['comment']) > max_comment_length:
                    comment_data['comment'] = comment_data['comment'][:max_comment_length] + "..."
            
            # Rebuild prompt with truncated comments
            prompt = f"""You are {professor_persona}. Your task is to refine multiple assessment comments to sound more natural, human-like, and professorial while preserving ALL technical content and maintaining the same evaluation levels.

COURSE LEVEL: {course_level.title()}

REFINEMENT GUIDELINES:
{tone_guidance}

ESSENTIAL REQUIREMENTS FOR ALL COMMENTS:
1. **Preserve ALL technical content** - Don't remove any specific technical details, examples, or findings
2. **Maintain the same evaluation level** - Don't make comments more positive or negative than originals
3. **Keep similar length** - Don't significantly shorten or lengthen comments
4. **Sound like a human professor** - Use natural academic language, not robotic AI phrasing
5. **Use conversational academic tone** - Replace phrases like "The documentation demonstrates..." with more natural alternatives
6. **Add subtle personality** - Use varied sentence structures and natural transitions
7. **Maintain professionalism** - Keep it academic and appropriate for formal assessment

COMMENTS TO REFINE:

"""
            for i, comment_data in enumerate(comments_list, 1):
                prompt += f"""
COMMENT {i} - {comment_data['component']} (Score: {comment_data['score']} points):
"{comment_data['comment']}"

"""
            prompt += f"""
Please respond with exactly {len(comments_list)} refined comments, numbered and separated clearly. Format your response as:

REFINED COMMENT 1:
[refined version of comment 1]

REFINED COMMENT 2:
[refined version of comment 2]

[continue for all comments...]

Respond with ONLY the refined comments in this format, no additional explanations."""
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4000,  # Increased for multiple comments
            )
        )
        
        if not response or not response.text:
            print(f"   ⚠️ Empty response from AI for batch refinement")
            return [comment_data['comment'] for comment_data in comments_list]  # Return originals
        
        # Parse the batch response
        refined_comments = parse_batch_response(response.text, len(comments_list))
        
        if len(refined_comments) != len(comments_list):
            print(f"   ⚠️ Expected {len(comments_list)} refined comments, got {len(refined_comments)}")
            # Pad with originals if needed
            while len(refined_comments) < len(comments_list):
                idx = len(refined_comments)
                refined_comments.append(comments_list[idx]['comment'])
        
        return refined_comments
        
    except Exception as e:
        print(f"   ❌ Error in batch comment refinement: {e}")
        return [comment_data['comment'] for comment_data in comments_list]  # Return originals


def parse_batch_response(response_text: str, expected_count: int) -> list:
    """
    Parse the batch response to extract individual refined comments.
    
    Args:
        response_text: The AI response containing multiple refined comments
        expected_count: Number of comments expected
    
    Returns:
        list: List of refined comment strings
    """
    
    refined_comments = []
    
    # Split by "REFINED COMMENT" markers
    parts = response_text.split("REFINED COMMENT")
    
    for i, part in enumerate(parts[1:], 1):  # Skip first empty part
        # Remove the number and colon at the start
        lines = part.strip().split('\n')
        if lines:
            # Remove the number line (e.g., "1:" or "2:")
            comment_lines = []
            for line in lines[1:]:  # Skip first line with number
                line = line.strip()
                if line and not line.startswith("REFINED COMMENT"):
                    comment_lines.append(line)
            
            if comment_lines:
                refined_comment = ' '.join(comment_lines).strip()
                # Clean up any remaining formatting
                if refined_comment.startswith('"') and refined_comment.endswith('"'):
                    refined_comment = refined_comment[1:-1]
                refined_comments.append(refined_comment)
    
    # If parsing failed, try alternative approach
    if len(refined_comments) < expected_count:
        # Try splitting by numbered patterns
        import re
        pattern = r'(?:REFINED COMMENT\s*)?(\d+)[:.]?\s*([^0-9]+?)(?=(?:REFINED COMMENT\s*)?\d+[:.]|$)'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        if matches:
            refined_comments = []
            for num, comment in matches:
                cleaned_comment = comment.strip()
                if cleaned_comment.startswith('"') and cleaned_comment.endswith('"'):
                    cleaned_comment = cleaned_comment[1:-1]
                refined_comments.append(cleaned_comment)
    
    return refined_comments


def batch_refine_existing_results(client: genai.Client, results_dir: str, course_level: str = "graduate"):
    """
    Batch refines all existing grading results to make comments sound more natural and human-like.
    Uses optimized batch processing to refine all components per file in a single API call.
    Saves refined results in a separate 'refined_comments' folder within the results directory.
    
    Args:
        client: Gemini API client
        results_dir: Directory containing grading results JSON files
        course_level: "undergraduate" or "graduate"
    """
    
    if not os.path.exists(results_dir):
        print(f"❌ Results directory '{results_dir}' not found.")
        return False
    
    # Find all grading result files
    result_files = []
    for file in os.listdir(results_dir):
        if file.endswith('_grading_results.json'):
            file_path = os.path.join(results_dir, file)
            if os.path.isfile(file_path):
                result_files.append((file, file_path))
    
    if not result_files:
        print(f"❌ No grading result files found in '{results_dir}'.")
        return False
    
    print(f"🎨 Found {len(result_files)} grading result files to refine")
    
    # Create refined comments directory
    refined_dir = os.path.join(results_dir, "refined_comments")
    os.makedirs(refined_dir, exist_ok=True)
    print(f"📁 Saving refined comments to: {refined_dir}")
    
    success_count = 0
    
    for file_name, file_path in result_files:
        try:
            # Load current data
            with open(file_path, 'r', encoding='utf-8') as f:
                assessment_data = json.load(f)
            
            # Refine comments
            print(f"   🔄 Refining comments for {file_name}...")
            refined_data = refine_all_assessment_comments(client, assessment_data, course_level)
            
            # Add refinement metadata
            refined_data['refinement_info'] = {
                "refined_at": datetime.now().isoformat(),
                "course_level": course_level,
                "original_file": file_path,
                "refinement_method": "ai_comment_refinement"
            }
            
            # Save refined version in refined_comments folder
            refined_file_path = os.path.join(refined_dir, file_name)
            with open(refined_file_path, 'w', encoding='utf-8') as f:
                json.dump(refined_data, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Successfully refined {file_name}")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error processing {file_name}: {e}")
    
    print(f"\n🎉 Comment refinement completed!")
    print(f"   ✅ Successfully refined: {success_count}/{len(result_files)} files")
    print(f"   📁 Refined results saved to: {refined_dir}")
    print(f"   📋 Original files preserved in: {results_dir}")
    if success_count > 0:
        print(f"   💡 Compare original vs refined files to see improvements!")
    
    return success_count == len(result_files)
