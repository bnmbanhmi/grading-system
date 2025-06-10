#!/usr/bin/env python3
"""
CSV Exporter for Refined Grading Results
Exports refined comments from JSON files to CSV format for easy viewing and sharing.
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path


def export_refined_comments_to_csv(results_dir: str, output_file: str = None):
    """
    Export refined comments from JSON files to CSV format.
    
    Args:
        results_dir: Directory containing grading results (will look for refined_comments subfolder)
        output_file: Optional output CSV file path. If None, auto-generates based on timestamp.
    
    Returns:
        str: Path to the created CSV file
    """
    
    # Look for refined_comments folder first, fallback to main directory
    refined_dir = os.path.join(results_dir, "refined_comments")
    if os.path.exists(refined_dir):
        source_dir = refined_dir
        file_suffix = "_refined_evaluation_report"
    else:
        source_dir = results_dir
        file_suffix = "_evaluation_report"
    
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"Results directory not found: {source_dir}")
    
    # Find all grading result files
    result_files = []
    for file in os.listdir(source_dir):
        if file.endswith('_grading_results.json'):
            file_path = os.path.join(source_dir, file)
            if os.path.isfile(file_path):
                result_files.append((file, file_path))
    
    if not result_files:
        raise FileNotFoundError(f"No grading result files found in: {source_dir}")
    
    # Generate output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        course_name = "3702ICT" if "3702ICT" in results_dir else "7009ICT" if "7009ICT" in results_dir else "AR_Course"
        output_file = os.path.join(results_dir, f"{course_name}{file_suffix}_{timestamp}.csv")
    
    # Prepare CSV data
    csv_rows = []
    
    # CSV headers
    headers = ["Group Name", "Scoring Criteria", "Achieved Score", "Comments/Feedback"]
    
    print(f"📊 Exporting {len(result_files)} grading files to CSV...")
    
    for file_name, file_path in sorted(result_files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            group_name = data.get('group_name', file_name.replace('_grading_results.json', ''))
            
            # Video Assessment
            if 'video_assessment' in data:
                video_data = data['video_assessment']
                csv_rows.append([
                    group_name,
                    "Video Assessment",
                    video_data.get('score', 'N/A'),
                    clean_comment(video_data.get('comment', 'No comment available'))
                ])
            
            # Coding Assessment
            if 'coding_assessment' in data:
                coding_data = data['coding_assessment']
                csv_rows.append([
                    group_name,
                    "Coding Assessment",
                    coding_data.get('score', 'N/A'),
                    clean_comment(coding_data.get('comment', 'No comment available'))
                ])
            
            # Component Assessments
            if 'component_assessments' in data and isinstance(data['component_assessments'], list):
                for component in data['component_assessments']:
                    if isinstance(component, dict):
                        csv_rows.append([
                            group_name,
                            component.get('component', 'Unknown Component'),
                            component.get('score', 'N/A'),
                            clean_comment(component.get('comment', 'No comment available'))
                        ])
            
            # Total Score (add as summary row)
            total_score = data.get('total_score')
            if total_score is not None:
                csv_rows.append([
                    group_name,
                    "TOTAL SCORE",
                    total_score,
                    f"Overall assessment total: {total_score} points"
                ])
            
            # Add separator row between groups for readability
            csv_rows.append(["", "", "", ""])
            
        except Exception as e:
            print(f"   ❌ Error processing {file_name}: {e}")
            continue
    
    # Remove last empty separator row
    if csv_rows and all(cell == "" for cell in csv_rows[-1]):
        csv_rows.pop()
    
    # Write CSV file
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            
            # Write headers
            writer.writerow(headers)
            
            # Write data rows
            writer.writerows(csv_rows)
        
        print(f"✅ CSV export completed successfully!")
        print(f"📁 Output file: {output_file}")
        print(f"📊 Total rows exported: {len(csv_rows)} (excluding headers)")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error writing CSV file: {e}")
        raise


def clean_comment(comment: str) -> str:
    """
    Clean comment text for CSV export by removing problematic characters.
    
    Args:
        comment: Original comment text
    
    Returns:
        str: Cleaned comment text suitable for CSV
    """
    if not comment:
        return "No comment available"
    
    # Replace problematic characters
    cleaned = comment.replace('\n', ' ').replace('\r', ' ')
    
    # Replace multiple spaces with single space
    while '  ' in cleaned:
        cleaned = cleaned.replace('  ', ' ')
    
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


def export_refined_comments_detailed_csv(results_dir: str, output_file: str = None):
    """
    Export refined comments to a detailed CSV with additional metadata.
    
    Args:
        results_dir: Directory containing grading results
        output_file: Optional output CSV file path
    
    Returns:
        str: Path to the created CSV file
    """
    
    # Look for refined_comments folder first
    refined_dir = os.path.join(results_dir, "refined_comments")
    if os.path.exists(refined_dir):
        source_dir = refined_dir
        file_suffix = "_detailed_refined_report"
    else:
        source_dir = results_dir
        file_suffix = "_detailed_report"
    
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"Results directory not found: {source_dir}")
    
    # Find result files
    result_files = []
    for file in os.listdir(source_dir):
        if file.endswith('_grading_results.json'):
            file_path = os.path.join(source_dir, file)
            if os.path.isfile(file_path):
                result_files.append((file, file_path))
    
    if not result_files:
        raise FileNotFoundError(f"No grading result files found in: {source_dir}")
    
    # Generate output filename
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        course_name = "3702ICT" if "3702ICT" in results_dir else "7009ICT" if "7009ICT" in results_dir else "AR_Course"
        output_file = os.path.join(results_dir, f"{course_name}{file_suffix}_{timestamp}.csv")
    
    # Detailed CSV headers
    headers = [
        "Group Name", 
        "Scoring Criteria", 
        "Achieved Score", 
        "Comments/Feedback",
        "Assessment Date",
        "Course Level",
        "Refinement Status",
        "Total Score"
    ]
    
    csv_rows = []
    
    print(f"📊 Exporting detailed evaluation report for {len(result_files)} files...")
    
    for file_name, file_path in sorted(result_files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            group_name = data.get('group_name', file_name.replace('_grading_results.json', ''))
            total_score = data.get('total_score', 'N/A')
            
            # Extract metadata
            assessment_date = "N/A"
            if 'timestamp' in data:
                try:
                    timestamp_data = json.loads(data['timestamp']) if isinstance(data['timestamp'], str) else data['timestamp']
                    if 'graded_at' in timestamp_data:
                        assessment_date = datetime.fromtimestamp(float(timestamp_data['graded_at'])).strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            course_level = "N/A"
            refinement_status = "Original"
            if 'refinement_info' in data:
                course_level = data['refinement_info'].get('course_level', 'N/A').title()
                refinement_status = f"Refined ({data['refinement_info'].get('refinement_version', 'N/A')})"
            
            # Process all assessment components
            components_data = []
            
            # Video Assessment
            if 'video_assessment' in data:
                components_data.append(("Video Assessment", data['video_assessment']))
            
            # Coding Assessment
            if 'coding_assessment' in data:
                components_data.append(("Coding Assessment", data['coding_assessment']))
            
            # Component Assessments
            if 'component_assessments' in data and isinstance(data['component_assessments'], list):
                for component in data['component_assessments']:
                    if isinstance(component, dict):
                        comp_name = component.get('component', 'Unknown Component')
                        components_data.append((comp_name, component))
            
            # Add all components to CSV
            for comp_name, comp_data in components_data:
                csv_rows.append([
                    group_name,
                    comp_name,
                    comp_data.get('score', 'N/A'),
                    clean_comment(comp_data.get('comment', 'No comment available')),
                    assessment_date,
                    course_level,
                    refinement_status,
                    total_score
                ])
            
            # Add separator
            csv_rows.append(["", "", "", "", "", "", "", ""])
            
        except Exception as e:
            print(f"   ❌ Error processing {file_name}: {e}")
            continue
    
    # Remove last separator
    if csv_rows and all(cell == "" for cell in csv_rows[-1]):
        csv_rows.pop()
    
    # Write detailed CSV
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            writer.writerows(csv_rows)
        
        print(f"✅ Detailed CSV export completed!")
        print(f"📁 Output file: {output_file}")
        print(f"📊 Total assessment entries: {len(csv_rows)}")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error writing detailed CSV: {e}")
        raise


def main():
    """
    Main function for command-line usage.
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python csv_exporter.py <results_directory> [output_file]")
        print("Example: python csv_exporter.py 7009ICT_grading_results")
        sys.exit(1)
    
    results_dir = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Export basic CSV
        csv_file = export_refined_comments_to_csv(results_dir, output_file)
        
        # Also create detailed version
        detailed_file = output_file.replace('.csv', '_detailed.csv') if output_file else None
        detailed_csv_file = export_refined_comments_detailed_csv(results_dir, detailed_file)
        
        print(f"\n🎉 Export completed successfully!")
        print(f"📄 Basic report: {csv_file}")
        print(f"📄 Detailed report: {detailed_csv_file}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
