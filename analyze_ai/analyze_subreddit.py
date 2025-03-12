#!/usr/bin/env python3
"""
Subreddit Analysis Script using AI

This script analyzes Reddit data from .zst compressed files to identify
pain points, problems, and themes within subreddits using AI.
"""

import os
import sys
import json
import logging
import argparse
import time
from datetime import datetime
from collections import defaultdict
import zstandard
import requests
from dotenv import load_dotenv, find_dotenv

# Add the parent directory to the path so we can import from parent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from personal.utils import read_obj_zst_meta, chunk_list

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("analyze_subreddit.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Improved .env file loading
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")

# Try multiple locations for .env file
possible_env_paths = [
    os.path.join(os.getcwd(), '.env'),
    os.path.join(os.getcwd(), 'PushshiftDumps', '.env'),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
]

env_file_path = None
for path in possible_env_paths:
    if os.path.exists(path):
        logger.info(f"Found .env file at: {path}")
        env_file_path = path
        load_dotenv(path)
        break
else:
    logger.warning("Could not find .env file in any of the expected locations")
    for path in possible_env_paths:
        logger.warning(f"  - {path} {'(exists)' if os.path.exists(path) else '(not found)'}")

# Get API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# If we found an env file but the API key is not set or is the old one, try to read it directly
if env_file_path and (not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-proj-1234")):
    logger.info("API key not found in environment or using old key, trying to read directly from file")
    try:
        with open(env_file_path, 'r') as f:
            for line in f:
                if line.strip().startswith("OPENAI_API_KEY="):
                    OPENAI_API_KEY = line.strip().split("=", 1)[1]
                    logger.info("Successfully read API key directly from file")
                    break
    except Exception as e:
        logger.error(f"Error reading API key from file: {e}")

if not OPENAI_API_KEY:
    logger.warning("No OpenAI API key found in .env file. Please add your API key as OPENAI_API_KEY=your_key")
else:
    # Only show the first few and last few characters for security
    masked_key = OPENAI_API_KEY[:4] + "..." + OPENAI_API_KEY[-4:] if len(OPENAI_API_KEY) > 8 else "Too short"
    logger.info(f"API Key found (masked): {masked_key}")

# Check for organization ID
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
if OPENAI_ORG_ID:
    logger.info(f"Organization ID found: {OPENAI_ORG_ID}")


def extract_metadata(subreddit_data):
    """
    Extract metadata from a list of subreddit posts/comments
    """
    metadata = {
        "post_count": len(subreddit_data),
        "date_range": {"earliest": None, "latest": None},
        "authors": set(),
        "avg_score": 0,
        "total_score": 0
    }
    
    for item in subreddit_data:
        # Extract creation date
        try:
            created_time = datetime.utcfromtimestamp(int(item.get('created_utc', 0)))
            if metadata["date_range"]["earliest"] is None or created_time < metadata["date_range"]["earliest"]:
                metadata["date_range"]["earliest"] = created_time
            if metadata["date_range"]["latest"] is None or created_time > metadata["date_range"]["latest"]:
                metadata["date_range"]["latest"] = created_time
        except (ValueError, TypeError):
            pass
        
        # Extract author
        if 'author' in item and item['author'] not in ['[deleted]', 'AutoModerator']:
            metadata["authors"].add(item['author'])
        
        # Extract score
        if 'score' in item:
            metadata["total_score"] += int(item.get('score', 0))
    
    # Calculate average score
    if metadata["post_count"] > 0:
        metadata["avg_score"] = metadata["total_score"] / metadata["post_count"]
    
    # Convert date objects to strings for JSON serialization
    if metadata["date_range"]["earliest"]:
        metadata["date_range"]["earliest"] = metadata["date_range"]["earliest"].strftime('%Y-%m-%d')
    if metadata["date_range"]["latest"]:
        metadata["date_range"]["latest"] = metadata["date_range"]["latest"].strftime('%Y-%m-%d')
    
    # Convert set to list for JSON serialization
    metadata["authors"] = list(metadata["authors"])
    metadata["unique_authors"] = len(metadata["authors"])
    
    return metadata


def format_content_for_ai(items, is_submission=True):
    """
    Format content for AI analysis based on whether it's a submission or comment
    """
    formatted_items = []
    
    for item in items:
        if is_submission:
            # Format submission
            title = item.get('title', 'No Title')
            selftext = item.get('selftext', '')
            score = item.get('score', 0)
            num_comments = item.get('num_comments', 0)
            created = datetime.utcfromtimestamp(int(item.get('created_utc', 0))).strftime('%Y-%m-%d')
            
            formatted_text = f"POST [Score: {score}, Comments: {num_comments}, Date: {created}]\n"
            formatted_text += f"TITLE: {title}\n"
            if selftext and selftext != "[deleted]" and selftext != "[removed]":
                formatted_text += f"CONTENT: {selftext}\n"
        else:
            # Format comment
            body = item.get('body', '')
            score = item.get('score', 0)
            created = datetime.utcfromtimestamp(int(item.get('created_utc', 0))).strftime('%Y-%m-%d')
            
            if body and body != "[deleted]" and body != "[removed]":
                formatted_text = f"COMMENT [Score: {score}, Date: {created}]\n"
                formatted_text += f"CONTENT: {body}\n"
            else:
                continue  # Skip deleted/removed comments
        
        formatted_items.append(formatted_text)
    
    return "\n\n".join(formatted_items)


def prepare_ai_prompt(subreddit_name, content, metadata):
    """
    Prepare the AI prompt using the template from prompts.md
    """
    prompt = f"""
# Subreddit Community Analysis: r/{subreddit_name}

## Context
- Subreddit: r/{subreddit_name}
- Time period: {metadata['date_range']['earliest']} to {metadata['date_range']['latest']}
- Sample size: {metadata['post_count']} posts/comments
- Unique authors: {metadata['unique_authors']}

## Your Task
You are a cultural anthropologist and user researcher analyzing this community to identify pain points, challenges, and recurring themes. Based on the content provided, conduct a thorough analysis of the community conversations.

## Analysis Framework
Please analyze the following content from r/{subreddit_name} and provide insights in these categories:

0. **General Information**
   - What is the community about?
   - What are the main topics discussed?
   - What is popular to chat about, what isn't?

1. **Primary Pain Points and Problems**
   - Identify the most significant challenges, frustrations, or problems faced by community members
   - Rank these issues by apparent frequency and emotional intensity
   - Include specific examples or quotes that illustrate each pain point

2. **Recurring Questions and Information Gaps**
   - Note patterns of questions that appear repeatedly
   - Identify topics where users seem to lack information or clarity
   - Highlight areas where the community struggles to find consensus or clear answers

3. **Most Popular Solutions, Products, or Services**
   - Identify the most frequently discussed solutions, products, or services
   - Analyze the frequency and intensity of discussion around these topics
   - Consider the emotional tone and sentiment associated with each topic

4. **Least Popular Solutions, Products, or Services**
   - Identify the least frequently discussed solutions, products, or services
   - Analyze the frequency and intensity of discussion around these topics
   - Consider the emotional tone and sentiment associated with each topic

## Content For Analysis:

{content}
"""
    return prompt


def analyze_with_openai(prompt, model="gpt-4o", max_tokens=4000):
    """
    Send the prompt to OpenAI API for analysis
    """
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key is required but not provided")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    # Add organization ID to headers if available
    if OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = OPENAI_ORG_ID
        logger.info(f"Using organization ID: {OPENAI_ORG_ID}")
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    try:
        logger.info(f"Sending request to OpenAI API using model: {model}")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling OpenAI API: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
            
            # Provide more helpful error messages
            if e.response.status_code == 401:
                logger.error("Authentication error: Your API key may be invalid or expired")
            elif e.response.status_code == 429:
                logger.error("Rate limit exceeded: You've hit your API usage limits")
            elif e.response.status_code == 404:
                logger.error(f"Model not found: The model '{model}' may not exist or you don't have access to it")
        return None


def process_subreddit_file(file_path, output_dir, chunk_size=100, max_chunks=5, is_submission=True):
    """
    Process a subreddit file and analyze it with AI
    """
    logger.info(f"Processing file: {file_path}")
    
    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Extract subreddit name from file path
    subreddit_name = os.path.basename(file_path).split('_')[0]
    logger.info(f"Analyzing subreddit: r/{subreddit_name}")
    
    # Read all items from the file
    file_size = os.stat(file_path).st_size
    all_items = []
    items_processed = 0
    total_items_estimate = 0
    
    # First pass to estimate total items (if file is small enough)
    # This is just a quick count of lines to get an estimate
    if file_size < 500 * 1024 * 1024:  # Less than 500MB
        logger.info("File is relatively small, counting total items for accurate coverage stats...")
        try:
            # Count items without loading them all
            for _, _, _ in read_obj_zst_meta(file_path):
                total_items_estimate += 1
                if total_items_estimate % 50000 == 0:
                    logger.info(f"Counted {total_items_estimate:,} items so far...")
            logger.info(f"Total items in file: {total_items_estimate:,}")
        except Exception as e:
            logger.error(f"Error counting items: {e}")
            # Use a rough estimate based on file size
            # This is very approximate but better than nothing
            bytes_per_item = 500  # Very rough estimate
            total_items_estimate = file_size // bytes_per_item
            logger.info(f"Estimated total items based on file size: ~{total_items_estimate:,}")
    else:
        # For larger files, use a sample-based estimate
        logger.info("File is large, using sample-based estimate for total items...")
        sample_size = 1000
        sample_items = 0
        sample_bytes = 0
        
        for _, _, file_bytes_processed in read_obj_zst_meta(file_path):
            sample_items += 1
            if sample_items >= sample_size:
                sample_bytes = file_bytes_processed
                break
        
        if sample_items > 0 and sample_bytes > 0:
            # Estimate total items based on the sample
            items_per_byte = sample_items / sample_bytes
            total_items_estimate = int(items_per_byte * file_size)
            logger.info(f"Estimated total items based on sampling: ~{total_items_estimate:,}")
        else:
            # Fallback estimate
            bytes_per_item = 500  # Very rough estimate
            total_items_estimate = file_size // bytes_per_item
            logger.info(f"Estimated total items based on file size: ~{total_items_estimate:,}")
    
    # Second pass to read items for analysis
    logger.info("Reading items for analysis...")
    for obj, _, file_bytes_processed in read_obj_zst_meta(file_path):
        all_items.append(obj)
        items_processed += 1
        
        # Log progress
        if items_processed % 10000 == 0:
            progress = (file_bytes_processed / file_size) * 100
            logger.info(f"Processed {items_processed:,} items - {progress:.2f}% of file")
            
        # If we have enough items for analysis, stop reading
        if items_processed >= chunk_size * max_chunks:
            logger.info(f"Reached maximum items ({chunk_size * max_chunks}), stopping file read")
            break
    
    # Calculate percentage of data analyzed
    coverage_pct = 0
    if total_items_estimate > 0:
        coverage_pct = (items_processed / total_items_estimate) * 100
        logger.info(f"Analyzing {items_processed:,} out of estimated {total_items_estimate:,} items ({coverage_pct:.2f}%)")
    else:
        logger.info(f"Collected {len(all_items)} items from file. Total items unknown.")
    
    # File coverage metadata
    file_coverage = {
        "items_processed": items_processed,
        "total_items_estimate": total_items_estimate,
        "coverage_percentage": round(coverage_pct, 2),
        "file_size_bytes": file_size
    }
    
    # Process in chunks
    chunk_results = []
    chunks = list(chunk_list(all_items, chunk_size))
    logger.info(f"Split data into {len(chunks)} chunks of size {chunk_size}")
    
    # Process only the first max_chunks chunks
    chunks_to_process = chunks[:max_chunks]
    logger.info(f"Processing {len(chunks_to_process)} chunks")
    
    for i, chunk in enumerate(chunks_to_process):
        logger.info(f"Processing chunk {i+1}/{len(chunks_to_process)}")
        
        # Extract metadata for this chunk
        metadata = extract_metadata(chunk)
        logger.info(f"Chunk metadata: {metadata['post_count']} posts, {metadata['unique_authors']} authors")
        
        # Format content for AI
        formatted_content = format_content_for_ai(chunk, is_submission)
        
        # Prepare prompt
        prompt = prepare_ai_prompt(subreddit_name, formatted_content, metadata)
        
        # Save prompt to file
        prompt_file = os.path.join(output_dir, f"{subreddit_name}_chunk_{i+1}_prompt.txt")
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        logger.info(f"Saved prompt to {prompt_file}")
        
        # Send to OpenAI for analysis
        logger.info("Sending to OpenAI for analysis...")
        start_time = time.time()
        analysis = analyze_with_openai(prompt)
        elapsed_time = time.time() - start_time
        logger.info(f"OpenAI analysis completed in {elapsed_time:.2f} seconds")
        
        if analysis:
            # Save analysis to file
            analysis_file = os.path.join(output_dir, f"{subreddit_name}_chunk_{i+1}_analysis.md")
            with open(analysis_file, 'w') as f:
                f.write(analysis)
            logger.info(f"Saved analysis to {analysis_file}")
            
            # Add to results
            chunk_results.append({
                "chunk_id": i+1,
                "metadata": metadata,
                "analysis": analysis
            })
        else:
            logger.error(f"Failed to get analysis for chunk {i+1}")
        
        # Rate limiting
        if i < len(chunks_to_process) - 1:
            logger.info("Waiting 5 seconds before processing next chunk...")
            time.sleep(5)
    
    # Combine all chunk analyses into a single summary
    if chunk_results:
        # Create combined analysis file
        combined_file = os.path.join(output_dir, f"{subreddit_name}_all_analyses.json")
        with open(combined_file, 'w') as f:
            json.dump(chunk_results, f, indent=2)
        logger.info(f"Saved all analyses to {combined_file}")
        
        # Now create a meta-analysis of all chunks
        if len(chunk_results) > 1:
            logger.info("Creating meta-analysis of all chunks...")
            
            # Format all analyses for the meta-analysis
            all_analyses = "\n\n".join([f"## Chunk {result['chunk_id']} Analysis\n\n{result['analysis']}" 
                                       for result in chunk_results])
            
            meta_prompt = f"""
# Meta-Analysis of r/{subreddit_name}

You have been provided with {len(chunk_results)} separate analyses of different chunks of content from the subreddit r/{subreddit_name}.
Your task is to synthesize these analyses into a coherent summary that identifies:

1. The most consistent pain points and problems across all analyses
2. The most common questions and information gaps
3. The most frequently discussed solutions, products, or services
4. Overall themes and patterns in the community

Please provide a comprehensive summary that brings together the insights from all chunks, highlighting both consistencies and any notable differences between chunks.

## Analysis Coverage
This analysis covers approximately {coverage_pct:.2f}% of the total content in the subreddit file.

## Individual Chunk Analyses

{all_analyses}
"""
            
            # Save meta-prompt
            meta_prompt_file = os.path.join(output_dir, f"{subreddit_name}_meta_prompt.txt")
            with open(meta_prompt_file, 'w') as f:
                f.write(meta_prompt)
            
            # Send to OpenAI for meta-analysis
            logger.info("Sending to OpenAI for meta-analysis...")
            meta_analysis = analyze_with_openai(meta_prompt, max_tokens=4000)
            
            if meta_analysis:
                # Save meta-analysis
                meta_file = os.path.join(output_dir, f"{subreddit_name}_meta_analysis.md")
                with open(meta_file, 'w') as f:
                    f.write(meta_analysis)
                logger.info(f"Saved meta-analysis to {meta_file}")
                
                # Also save as the summary file
                summary_file = os.path.join(output_dir, f"{subreddit_name}_analysis_summary.json")
                with open(summary_file, 'w') as f:
                    json.dump({
                        "subreddit": subreddit_name,
                        "chunks_analyzed": len(chunk_results),
                        "total_posts_analyzed": sum(result["metadata"]["post_count"] for result in chunk_results),
                        "coverage_data": file_coverage,
                        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                        "meta_analysis": meta_analysis
                    }, f, indent=2)
                logger.info(f"Saved summary to {summary_file}")
            else:
                logger.error("Failed to get meta-analysis")
        else:
            # If only one chunk, use that as the summary
            summary_file = os.path.join(output_dir, f"{subreddit_name}_analysis_summary.json")
            with open(summary_file, 'w') as f:
                json.dump({
                    "subreddit": subreddit_name,
                    "chunks_analyzed": 1,
                    "total_posts_analyzed": chunk_results[0]["metadata"]["post_count"],
                    "coverage_data": file_coverage,
                    "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                    "analysis": chunk_results[0]["analysis"]
                }, f, indent=2)
            logger.info(f"Saved summary to {summary_file}")
    
    return chunk_results, file_coverage


def main():
    """
    Main function to parse arguments and run the analysis
    """
    parser = argparse.ArgumentParser(description="Analyze subreddit data with AI")
    parser.add_argument("--submissions", type=str, help="Path to submissions .zst file")
    parser.add_argument("--comments", type=str, help="Path to comments .zst file")
    parser.add_argument("--subreddit", type=str, help="Subreddit name (used to construct file paths if not provided)")
    parser.add_argument("--data-dir", type=str, default=".", help="Directory containing the .zst files")
    parser.add_argument("--output-dir", type=str, default="./output", help="Directory to save output files")
    parser.add_argument("--chunk-size", type=int, default=100, help="Number of posts/comments per chunk")
    parser.add_argument("--max-chunks", type=int, default=5, help="Maximum number of chunks to process")
    parser.add_argument("--model", type=str, default="gpt-4o", help="OpenAI model to use")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.submissions and not args.comments and not args.subreddit:
        parser.error("Either --submissions, --comments, or --subreddit must be provided")
    
    # If subreddit is provided but not files, construct file paths
    if args.subreddit and not args.submissions and not args.comments:
        args.submissions = os.path.join(args.data_dir, f"{args.subreddit}_submissions.zst")
        args.comments = os.path.join(args.data_dir, f"{args.subreddit}_comments.zst")
    
    # Create subreddit-specific output directory
    subreddit_name = args.subreddit
    if not subreddit_name and args.submissions:
        subreddit_name = os.path.basename(args.submissions).split('_')[0]
    elif not subreddit_name and args.comments:
        subreddit_name = os.path.basename(args.comments).split('_')[0]
    
    output_dir = os.path.join(args.output_dir, subreddit_name)
    
    logger.info(f"Starting analysis for r/{subreddit_name}")
    logger.info(f"Output directory: {output_dir}")
    
    # Track overall coverage
    overall_coverage = {
        "total_items_estimate": 0,
        "items_processed": 0
    }
    
    # Process submissions file if provided
    submission_results = None
    submission_coverage = None
    if args.submissions and os.path.exists(args.submissions):
        logger.info(f"Processing submissions file: {args.submissions}")
        submission_results, submission_coverage = process_subreddit_file(
            args.submissions,
            os.path.join(output_dir, "submissions"),
            args.chunk_size,
            args.max_chunks,
            is_submission=True
        )
        if submission_coverage:
            overall_coverage["total_items_estimate"] += submission_coverage["total_items_estimate"]
            overall_coverage["items_processed"] += submission_coverage["items_processed"]
    
    # Process comments file if provided
    comment_results = None
    comment_coverage = None
    if args.comments and os.path.exists(args.comments):
        logger.info(f"Processing comments file: {args.comments}")
        comment_results, comment_coverage = process_subreddit_file(
            args.comments,
            os.path.join(output_dir, "comments"),
            args.chunk_size,
            args.max_chunks,
            is_submission=False
        )
        if comment_coverage:
            overall_coverage["total_items_estimate"] += comment_coverage["total_items_estimate"]
            overall_coverage["items_processed"] += comment_coverage["items_processed"]
    
    # Calculate overall coverage percentage
    if overall_coverage["total_items_estimate"] > 0:
        overall_coverage["coverage_percentage"] = round(
            (overall_coverage["items_processed"] / overall_coverage["total_items_estimate"]) * 100, 2
        )
    else:
        overall_coverage["coverage_percentage"] = 0
    
    # If both submissions and comments were processed, create a combined analysis
    if submission_results and comment_results:
        logger.info("Creating combined analysis of submissions and comments...")
        
        # Create combined output directory
        combined_dir = os.path.join(output_dir, "combined")
        if not os.path.exists(combined_dir):
            os.makedirs(combined_dir)
        
        # Get paths to all analysis files
        submission_analyses = [os.path.join(output_dir, "submissions", f"{subreddit_name}_chunk_{i+1}_analysis.md") 
                              for i in range(len(submission_results))]
        comment_analyses = [os.path.join(output_dir, "comments", f"{subreddit_name}_chunk_{i+1}_analysis.md") 
                           for i in range(len(comment_results))]
        
        # Read all analyses
        all_analyses = []
        for path in submission_analyses + comment_analyses:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    all_analyses.append(f.read())
        
        if all_analyses:
            # Create combined prompt
            combined_prompt = f"""
# Combined Analysis of r/{subreddit_name}

You have been provided with separate analyses of submissions and comments from the subreddit r/{subreddit_name}.
Your task is to synthesize these analyses into a coherent summary that provides a complete picture of the community.

Please provide a comprehensive summary that brings together the insights from all analyses, highlighting:

1. The primary characteristics and purpose of this subreddit community
2. The most significant pain points and problems faced by community members
3. The most common questions and information gaps
4. The most popular solutions, products, or services discussed
5. The least popular solutions, products, or services discussed
6. Overall themes, patterns, and dynamics in the community

## Individual Analyses

{all_analyses}
"""
            
            # Save combined prompt
            combined_prompt_file = os.path.join(combined_dir, f"{subreddit_name}_combined_prompt.txt")
            with open(combined_prompt_file, 'w') as f:
                f.write(combined_prompt)
            
            # Send to OpenAI for combined analysis
            logger.info("Sending to OpenAI for combined analysis...")
            combined_analysis = analyze_with_openai(combined_prompt, max_tokens=4000)
            
            if combined_analysis:
                # Save combined analysis
                combined_file = os.path.join(combined_dir, f"{subreddit_name}_combined_analysis.md")
                with open(combined_file, 'w') as f:
                    f.write(combined_analysis)
                logger.info(f"Saved combined analysis to {combined_file}")
                
                # Save final summary
                final_summary_file = os.path.join(output_dir, f"{subreddit_name}_analysis_summary.json")
                with open(final_summary_file, 'w') as f:
                    json.dump({
                        "subreddit": subreddit_name,
                        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                        "submissions_analyzed": sum(result["metadata"]["post_count"] for result in submission_results),
                        "comments_analyzed": sum(result["metadata"]["post_count"] for result in comment_results),
                        "coverage_data": {
                            "overall": overall_coverage,
                            "submissions": submission_coverage,
                            "comments": comment_coverage
                        },
                        "combined_analysis": combined_analysis
                    }, f, indent=2)
                logger.info(f"Saved final summary to {final_summary_file}")
            else:
                logger.error("Failed to get combined analysis")
    
    logger.info("Analysis complete!")


if __name__ == "__main__":
    main() 