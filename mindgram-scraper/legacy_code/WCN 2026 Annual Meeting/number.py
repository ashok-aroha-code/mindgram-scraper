import json
import re

def extract_number_from_title(title):
    """
    Extract number pattern from beginning of title.
    Pattern examples: WCN26-193, WCN26-4892, WCN26-8229, etc.
    """
    if not title:
        return ""
    
    # Pattern to match WCN26- followed by digits at the beginning of the string
    pattern = r'^(WCN26-\d+)'
    match = re.match(pattern, title.strip())
    
    if match:
        return match.group(1)
    return ""

def process_json_file(input_file, output_file):
    """
    Read JSON data, extract numbers from titles, update number fields,
    and save to new JSON file.
    """
    # Read the input JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process each entry
    for entry in data:
        if 'title' in entry and entry['title']:
            number = extract_number_from_title(entry['title'])
            entry['number'] = number
    
    # Save to new JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"Processing complete! Output saved to: {output_file}")
    
    # Print summary
    entries_with_numbers = sum(1 for entry in data if entry.get('number'))
    print(f"Total entries processed: {len(data)}")
    print(f"Entries with numbers extracted: {entries_with_numbers}")

# Usage
if __name__ == "__main__":
    input_filename = "scraped_data.json"  # Replace with your input file name
    output_filename = "1_scraped_data.json"  # Replace with your desired output file name
    
    process_json_file(input_filename, output_filename)