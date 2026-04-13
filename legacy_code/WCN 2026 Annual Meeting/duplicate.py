import json

def consolidate_urls(json_data):
    """
    Extract all URLs from the given JSON and combine them into a single list.
    Removes duplicate URLs.
    """
    # Parse the JSON string if it's provided as a string
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    # Create an empty list to store all URLs
    all_urls = []
    
    # Iterate through each page in the JSON data
    for page_key, urls in data.items():
        # Add all URLs from this page to our consolidated list
        all_urls.extend(urls)
    
    # Remove duplicates while preserving order
    unique_urls = []
    seen = set()
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls

def main():
    # Read the JSON file
    with open('all_article_urls.json', 'r') as file:
        json_data = json.load(file)
    
    # Get the consolidated list of URLs
    consolidated_urls = consolidate_urls(json_data)
    
    # Print the number of unique URLs found
    print(f"Found {len(consolidated_urls)} unique URLs")
    
    # Save the consolidated URLs to a new JSON file
    with open('article_urls.json', 'w') as file:
        json.dump(consolidated_urls, file, indent=2)
    
    print(f"Consolidated URLs saved to session_urls.json")

if __name__ == "__main__":
    main()