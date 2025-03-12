# Subreddit Analysis with AI

This tool analyzes Reddit data from .zst compressed files to identify pain points, problems, and themes within subreddits using AI.

## Requirements

- Python 3.7+
- OpenAI API key (set in `.env` file)

## Installation

1. Ensure you have all dependencies:
   ```bash
   pip install requests zstandard python-dotenv
   ```

2. Create a `.env` file in the root directory with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

The script can analyze both subreddit submissions and comments. You can provide either one or both file types.

### Basic Usage

```bash
python analyze_subreddit.py --subreddit [SUBREDDIT_NAME] --data-dir [PATH_TO_DATA_DIRECTORY]
```

This will look for files named `[SUBREDDIT_NAME]_submissions.zst` and `[SUBREDDIT_NAME]_comments.zst` in the specified data directory.

### Advanced Usage

```bash
python analyze_subreddit.py --submissions [PATH_TO_SUBMISSIONS_FILE] --comments [PATH_TO_COMMENTS_FILE] --output-dir [OUTPUT_DIRECTORY] --chunk-size [SIZE] --max-chunks [NUM]
```

### Parameters

- `--subreddit`: Name of the subreddit to analyze (used to construct file paths if `--submissions` and `--comments` are not provided)
- `--data-dir`: Directory containing the .zst files (default: current directory)
- `--submissions`: Path to the submissions .zst file
- `--comments`: Path to the comments .zst file
- `--output-dir`: Directory to save output files (default: ./output)
- `--chunk-size`: Number of posts/comments per chunk for AI analysis (default: 100)
- `--max-chunks`: Maximum number of chunks to process (default: 5)
- `--model`: OpenAI model to use (default: gpt-4o)

## Output

The script generates several output files:

1. **Prompts**: The prompts sent to the AI for each chunk
2. **Analysis files**: Individual analysis files for each chunk
3. **Meta-analysis**: A combined analysis across all chunks (if multiple chunks are processed)
4. **Summary JSON**: JSON file containing the complete analysis results

All output is organized in the following directory structure:
```
output/
  [subreddit_name]/
    submissions/
      [subreddit_name]_chunk_1_prompt.txt
      [subreddit_name]_chunk_1_analysis.md
      ...
    comments/
      [subreddit_name]_chunk_1_prompt.txt
      [subreddit_name]_chunk_1_analysis.md
      ...
    combined/
      [subreddit_name]_combined_prompt.txt
      [subreddit_name]_combined_analysis.md
    [subreddit_name]_analysis_summary.json
```

### Data Coverage Statistics

The script now includes coverage statistics in all analysis reports to indicate how representative your analysis is:

- For smaller files (< 500MB), the script will count the total number of items in the file
- For larger files, it estimates the total count based on sampling
- All reports include the percentage of content analyzed (e.g., "This analysis covers 2.5% of the total content")

This coverage information helps you understand how comprehensive your analysis is and whether you should consider processing more chunks for a more representative view.

Example coverage data in the summary JSON:
```json
"coverage_data": {
  "overall": {
    "total_items_estimate": 250000,
    "items_processed": 500,
    "coverage_percentage": 0.2
  },
  "submissions": {
    "items_processed": 200,
    "total_items_estimate": 50000,
    "coverage_percentage": 0.4,
    "file_size_bytes": 25000000
  },
  "comments": {
    "items_processed": 300,
    "total_items_estimate": 200000,
    "coverage_percentage": 0.15,
    "file_size_bytes": 120000000
  }
}
```

## Example

```bash
python analyze_subreddit.py --subreddit AskReddit --data-dir /path/to/reddit/data --chunk-size 50 --max-chunks 3
```

This will analyze up to 3 chunks of 50 posts each from the AskReddit subreddit's submissions and comments.

## Tips

1. For large subreddits, use smaller chunk sizes (50-100) and fewer chunks to avoid hitting API limits.
2. Use a more powerful model (gpt-4o) for better analysis quality, or use a faster model (gpt-3.5-turbo) for quicker results.
3. The script saves intermediate results, so if it's interrupted, you can still access partial analyses.
4. Check the coverage statistics to understand how representative your analysis is. If you're only analyzing a small percentage of a large subreddit, consider focusing on recent data or increasing the number of chunks. 