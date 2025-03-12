Given a subreddit data in .zst compressed files, let's analyze them with AI to identify pain points and problems in each subreddit (both posts and comments). We also want to identify the most popular topics and themes in each subreddit, and what usually gets the most upvotes.

We will use the OpenAI API to analyze the data (Context window is 128k tokens. Note about 4 characters = 1 token).

Example input files:
[subreddit_name]_submissions.zst
[subreddit_name]_comments.zst

Example output files:
[subreddit_name]_analysis_summary.json

As we process, we can have a file that contains all the analysis summaries for all chunks so far, then we can summarize that file into a new file that contains the overall analysis for the subreddit.

We will use the following prompt to analyze the data:

# Subreddit Community Analysis: r/{subreddit_name}

## Context
- Subreddit: r/{subreddit_name}
- Time period: {start_date} to {end_date}
- Sample size: {post_count} posts/comments
- Community size: Approximately {subscriber_count} members

## Your Task
You are a cultural anthropologist and user researcher analyzing this community to identify pain points, challenges, and recurring themes. Based on the content provided, conduct a thorough analysis of what the community is about, what they are struggling with, and how their current solutions are faring for them.

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
   - Consider how these pain points are currently solved, or if there are no solutions

2. **Recurring Questions and Information Gaps**
   - Note patterns of questions that appear repeatedly
   - Identify topics where users seem to lack information or clarity
   - Highlight areas where the community struggles to find consensus or clear answers

3. **Most Popular Solutions, Products, or Services**
   - Identify the most frequently discussed solutions, products, or services
   - Analyze the frequency and intensity of discussion around these topics
   - Consider the emotional tone and sentiment associated with each topic, and why

4. **Least Popular Solutions, Products, or Services**
   - Identify the least frequently discussed solutions, products, or services
   - Analyze the frequency and intensity of discussion around these topics
   - Consider the emotional tone and sentiment associated with each topic, and why

<think>
The user has a collection of subreddit data in .zst compressed files and wants to analyze them with AI to identify pain points and problems in each subreddit. I'll need to formulate a plan to help them process these files and prepare the data for AI analysis.

From the code provided, I can see they're working with the Pushshift Reddit data dumps, which contain Reddit comments and submissions in compressed zstandard format. Their files appear to be organized by subreddit.

Here's a plan I can suggest:

1. **Data Processing Pipeline**:
   - Extract data from the .zst files
   - Preprocess the content to make it suitable for AI analysis
   - Split data into manageable chunks
   - Send chunks to AI for analysis
   - Aggregate and summarize results

2. **Tools Available**:
   - From the provided code, there are several utilities for reading and processing .zst files
   - `utils.read_obj_zst_meta` seems to be a commonly used function for reading objects from zst files
   - Various scripts are available for filtering content

3. **Implementation Approach**:
   - Use existing utilities to read the .zst files
   - For each subreddit, process a representative sample (or all, if feasible)
   - Format data into chunks that fit within AI context window
   - Define clear prompts for the AI to identify problems and pain points
   - Collect and organize AI responses
</think>

# Processing Subreddit Data for AI Analysis

Based on your collection of subreddit data in .zst format, here's a comprehensive plan to analyze these files with AI to identify pain points and problems in each subreddit.

## 1. Data Extraction and Preparation

### Step 1: Set up a data extraction pipeline
```python
import utils
import discord_logging
import os
import json
from datetime import datetime
from collections import defaultdict

log = discord_logging.init_logging()

def extract_subreddit_data(input_file_path, output_folder, chunk_size=1000):
    """
    Extract data from a zst file and save in chunks for AI processing
    """
    file_size = os.stat(input_file_path).st_size
    subreddit_name = os.path.basename(input_file_path).split('_')[0]
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    # Initialize counters and containers
    file_lines = 0
    chunks = []
    current_chunk = []
    
    # Process the file
    for obj, line, file_bytes_processed in utils.read_obj_zst_meta(input_file_path):
        # Add this comment/submission to the current chunk
        current_chunk.append(obj)
        
        # If we've reached the chunk size, save it and start a new one
        if len(current_chunk) >= chunk_size:
            chunks.append(current_chunk)
            current_chunk = []
        
        file_lines += 1
        if file_lines % 100000 == 0:
            log.info(f"Processed {file_lines:,} lines : {(file_bytes_processed / file_size) * 100:.0f}%")
    
    # Add any remaining data as the final chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    # Save chunks to disk
    for i, chunk in enumerate(chunks):
        output_file = os.path.join(output_folder, f"{subreddit_name}_chunk_{i}.json")
        with open(output_file, 'w') as f:
            json.dump(chunk, f)
    
    log.info(f"Completed processing {file_lines:,} lines, created {len(chunks)} chunks")
    return chunks
```

### Step 2: Add metadata aggregation for context

```python
def analyze_subreddit_metadata(input_file_path):
    """
    Extract metadata about the subreddit to provide context for AI analysis
    """
    file_size = os.stat(input_file_path).st_size
    
    # Metadata to collect
    metadata = {
        "subreddit": os.path.basename(input_file_path).split('_')[0],
        "total_posts": 0,
        "date_range": {"earliest": None, "latest": None},
        "top_authors": defaultdict(int),
        "post_length_avg": 0,
        "common_topics": defaultdict(int)
    }
    
    total_length = 0
    
    for obj, _, _ in utils.read_obj_zst_meta(input_file_path):
        metadata["total_posts"] += 1
        
        # Track date range
        created = datetime.utcfromtimestamp(int(obj['created_utc']))
        if metadata["date_range"]["earliest"] is None or created < metadata["date_range"]["earliest"]:
            metadata["date_range"]["earliest"] = created
        if metadata["date_range"]["latest"] is None or created > metadata["date_range"]["latest"]:
            metadata["date_range"]["latest"] = created
        
        # Track authors
        metadata["top_authors"][obj['author']] += 1
        
        # Track content length
        content = obj.get('selftext', '') if 'selftext' in obj else obj.get('body', '')
        total_length += len(content)
        
        # Simple topic extraction (this is basic - could be improved)
        if 'title' in obj:
            words = obj['title'].lower().split()
            for word in words:
                if len(word) > 4:  # Only count longer words
                    metadata["common_topics"][word] += 1
    
    # Calculate averages
    if metadata["total_posts"] > 0:
        metadata["post_length_avg"] = total_length / metadata["total_posts"]
    
    # Keep only top authors and topics
    metadata["top_authors"] = dict(sorted(metadata["top_authors"].items(), 
                                         key=lambda x: x[1], reverse=True)[:20])
    metadata["common_topics"] = dict(sorted(metadata["common_topics"].items(), 
                                          key=lambda x: x[1], reverse=True)[:50])
    
    # Format dates for JSON serialization
    metadata["date_range"]["earliest"] = metadata["date_range"]["earliest"].strftime('%Y-%m-%d') if metadata["date_range"]["earliest"] else None
    metadata["date_range"]["latest"] = metadata["date_range"]["latest"].strftime('%Y-%m-%d') if metadata["date_range"]["latest"] else None
    
    return metadata
```

## 2. AI Analysis Pipeline

### Step 1: Create a function to prepare data for AI

```python
def prepare_for_ai_analysis(chunks, metadata, max_tokens=12000):
    """
    Prepare chunks for AI analysis by formatting them appropriately
    """
    ai_ready_chunks = []
    
    # Create a context introduction that will be included with each chunk
    context_intro = f"""
    Subreddit Analysis: r/{metadata['subreddit']}
    Time period: {metadata['date_range']['earliest']} to {metadata['date_range']['latest']}
    Total posts analyzed: {metadata['total_posts']}
    
    Your task is to analyze the following sample of content from r/{metadata['subreddit']} 
    to identify pain points, problems, and common themes discussed by the community.
    Focus on:
    1. Recurring issues or complaints
    2. Questions that appear frequently
    3. Problems that users are trying to solve
    4. Emotional themes (frustration, confusion, excitement)
    5. Product or service issues mentioned
    
    Provide a structured analysis with examples.
    """
    
    # Process each chunk to fit within token limits
    for i, chunk in enumerate(chunks):
        formatted_content = []
        estimated_tokens = len(context_intro.split())
        
        for post in chunk:
            # Format post content
            if 'title' in post:  # Submission
                post_text = f"TITLE: {post.get('title', '')}\nCONTENT: {post.get('selftext', '')}"
            else:  # Comment
                post_text = f"COMMENT: {post.get('body', '')}"
                
            # Estimate tokens (rough calculation: 4 chars ≈ 1 token)
            post_tokens = len(post_text) // 4
            
            # Add post if it fits in the token budget
            if estimated_tokens + post_tokens < max_tokens:
                formatted_content.append(post_text)
                estimated_tokens += post_tokens
            else:
                break
                
        # Create the complete prompt for this chunk
        if formatted_content:
            ai_ready_chunks.append({
                "chunk_id": i,
                "context": context_intro,
                "content": "\n\n".join(formatted_content),
                "estimated_tokens": estimated_tokens
            })
    
    return ai_ready_chunks
```

### Step 2: Function to send data to AI and process results

```python
import requests
import time

def analyze_with_ai(ai_ready_chunks, api_key, output_folder):
    """
    Send chunks to an AI API for analysis and save results
    This is a placeholder - you'll need to adapt it to your specific AI service
    """
    results = []
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    for chunk in ai_ready_chunks:
        log.info(f"Sending chunk {chunk['chunk_id']} to AI for analysis...")
        
        # Prepare the prompt
        prompt = f"{chunk['context']}\n\n{chunk['content']}"
        
        # This is a placeholder for your actual API call
        # You would replace this with the appropriate API for your AI service
        response = {
            "chunk_id": chunk["chunk_id"],
            "analysis": "Placeholder for AI analysis result"
        }
        
        # Save individual result
        output_file = os.path.join(output_folder, f"analysis_chunk_{chunk['chunk_id']}.json")
        with open(output_file, 'w') as f:
            json.dump(response, f, indent=2)
        
        results.append(response)
        time.sleep(1)  # Rate limiting
    
    return results
```

### Step 3: Aggregate and summarize findings

```python
def aggregate_findings(analysis_results, metadata, output_folder):
    """
    Combine and summarize findings from all chunks
    """
    # Placeholder for aggregation logic
    # In a real implementation, you might use another AI call to summarize all the findings
    
    summary = {
        "subreddit": metadata["subreddit"],
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "data_analyzed": {
            "post_count": metadata["total_posts"],
            "date_range": metadata["date_range"]
        },
        "key_findings": [],
        "pain_points": [],
        "common_themes": [],
        "recommendations": []
    }
    
    # In a real implementation, you would process all the chunk analyses
    # to extract and consolidate findings here
    
    # Save the summary
    summary_file = os.path.join(output_folder, f"{metadata['subreddit']}_analysis_summary.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary
```

## 3. Main Execution Flow

```python
def main():
    # Configuration
    input_folder = r"path\to\your\zst\files"
    output_base = r"path\to\output"
    api_key = "your_ai_api_key"
    
    # Process each subreddit file
    for file_name in os.listdir(input_folder):
        if file_name.endswith("_submissions.zst") or file_name.endswith("_comments.zst"):
            input_file_path = os.path.join(input_folder, file_name)
            subreddit_name = file_name.split('_')[0]
            
            log.info(f"Processing r/{subreddit_name}...")
            
            # Create output folders
            chunks_folder = os.path.join(output_base, subreddit_name, "chunks")
            analysis_folder = os.path.join(output_base, subreddit_name, "analysis")
            
            # Step 1: Extract metadata for context
            metadata = analyze_subreddit_metadata(input_file_path)
            
            # Step 2: Extract content in chunks
            chunks = extract_subreddit_data(input_file_path, chunks_folder)
            
            # Step 3: Prepare data for AI analysis
            ai_ready_chunks = prepare_for_ai_analysis(chunks, metadata)
            
            # Step 4: Send to AI for analysis
            analysis_results = analyze_with_ai(ai_ready_chunks, api_key, analysis_folder)
            
            # Step 5: Aggregate and summarize findings
            summary = aggregate_findings(analysis_results, metadata, output_base)
            
            log.info(f"Completed analysis for r/{subreddit_name}")

if __name__ == "__main__":
    main()
```

## 4. Considerations and Optimizations

1. **Sampling Strategy**: For large subreddits, consider analyzing a representative sample rather than all content.

2. **Time Period Selection**: Focus on recent content (last 6-12 months) for more relevant insights.

3. **Content Selection**:
   - Prioritize posts with high engagement (comments, upvotes)
   - Include a mix of questions, discussions, and problem reports

4. **Parallel Processing**:
   ```python
   import multiprocessing
   
   # Use multiple processes to handle different files
   def process_subreddit(file_path):
       # Call the processing pipeline for a single file
       # ...
   
   # In main()
   with multiprocessing.Pool(processes=4) as pool:
       pool.map(process_subreddit, file_paths)
   ```

5. **Incremental Processing**: Add checkpoint functionality to resume interrupted processing.

6. **Cost Management**: If using a commercial API like OpenAI, monitor token usage and implement batching strategies.

This approach gives you a systematic way to process your subreddit data and analyze it with AI to identify pain points and community problems. You can adjust the components based on your specific needs and the AI service you're using.
