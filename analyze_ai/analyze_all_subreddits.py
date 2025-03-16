#!/usr/bin/env python3
"""
Script to process all subreddits that don't already have output directories.
Place in root directory (outside of PushshiftDumps)
"""

import os
import subprocess
import re
import sys

# Configuration
DATA_DIR = "reddit_feb_25/subreddits/"
OUTPUT_DIR = "output"
SCRIPT_PATH = "PushshiftDumps/analyze_ai/analyze_subreddit.py"
MAX_CHUNKS = 15

def get_subreddit_from_filename(filename):
    """Extract subreddit name from a filename like 'SubredditName_submissions.zst'"""
    match = re.match(r'([^_]+)_(submissions|comments)\.zst', filename)
    return match.group(1) if match else None

def find_subreddits():
    """Find all unique subreddits in the data directory"""
    subreddits = set()
    try:
        for filename in os.listdir(DATA_DIR):
            subreddit = get_subreddit_from_filename(filename)
            if subreddit:
                subreddits.add(subreddit)
    except FileNotFoundError:
        print(f"Error: Data directory '{DATA_DIR}' not found")
        sys.exit(1)
    return subreddits

def get_analyzed_subreddits():
    """Get list of subreddits that already have output directories"""
    try:
        return set(os.listdir(OUTPUT_DIR))
    except FileNotFoundError:
        print(f"Output directory '{OUTPUT_DIR}' not found, creating it")
        os.makedirs(OUTPUT_DIR)
        return set()

def process_subreddits():
    """Process all subreddits that haven't been analyzed yet"""
    all_subreddits = find_subreddits()
    analyzed_subreddits = get_analyzed_subreddits()
    
    remaining = all_subreddits - analyzed_subreddits
    total = len(remaining)
    
    if total == 0:
        print("All subreddits have already been analyzed!")
        return
    
    print(f"Found {total} subreddits to analyze")
    
    for i, subreddit in enumerate(sorted(remaining), 1):
        print(f"[{i}/{total}] Analyzing r/{subreddit}")
        try:
            subprocess.run([
                "python3", SCRIPT_PATH,
                "--subreddit", subreddit,
                "--data-dir", DATA_DIR,
                "--max-chunks", str(MAX_CHUNKS)
            ], check=True)
            print(f"✓ Successfully analyzed r/{subreddit}")
        except subprocess.CalledProcessError as e:
            print(f"× Error analyzing r/{subreddit}: {e}")

if __name__ == "__main__":
    process_subreddits()