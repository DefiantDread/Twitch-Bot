import os
import re

def find_sql_and_utcnow_occurrences(base_path):
    """
    Recursively search for raw SQL queries and utcnow occurrences in Python files in the specified directory.
    """
    sql_patterns = [
        re.compile(r'execute\((["\'])(.*?)\1'),  # Captures queries passed to execute()
        re.compile(r'query\((["\'])(.*?)\1'),    # Captures queries passed to query()
    ]
    utcnow_pattern = re.compile(r'\bdatetime\.utcnow\(\)')  # Captures datetime.utcnow()

    occurrences = {
        'sql': [],
        'utcnow': []
    }

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # Search for SQL queries
                    """for pattern in sql_patterns:
                        for match in pattern.finditer(content):
                            query = match.group(2)
                            line_number = content[:match.start()].count('\n') + 1
                            occurrences['sql'].append({
                                'file': file_path,
                                'line': line_number,
                                'query': query.strip()
                            })"""

                    # Search for datetime.utcnow()
                    for match in utcnow_pattern.finditer(content):
                        line_number = content[:match.start()].count('\n') + 1
                        occurrences['utcnow'].append({
                            'file': file_path,
                            'line': line_number,
                            'expression': match.group(0)
                        })

    return occurrences


if __name__ == "__main__":
    base_dir = input("Enter the path to your project directory: ")
    results = find_sql_and_utcnow_occurrences(base_dir)

    if results['sql']:
        print(f"Found {len(results['sql'])} raw SQL query occurrences:")
        for result in results['sql']:
            print(f"File: {result['file']}, Line: {result['line']}, Query: {result['query']}")
    else:
        print("No raw SQL queries found.")

    if results['utcnow']:
        print(f"\nFound {len(results['utcnow'])} occurrences of datetime.utcnow():")
        for result in results['utcnow']:
            print(f"File: {result['file']}, Line: {result['line']}, Expression: {result['expression']}")
    else:
        print("No occurrences of datetime.utcnow() found.")
