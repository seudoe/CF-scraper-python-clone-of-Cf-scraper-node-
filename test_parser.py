"""Test the parser with actual HTML files"""
import sys
from pathlib import Path

script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

from lib.parse import parse_problem_page

# Test with all HTML files
html_dir = script_dir / 'example-htmls'
html_files = list(html_dir.glob('*.html'))

print(f'[test] Found {len(html_files)} HTML files to test\n')

passed = 0
failed = 0

for html_file in html_files:
    problem_id = html_file.stem
    print(f'[test] ═══ Testing {problem_id} ═══')
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()
    
    result = parse_problem_page(html, problem_id)
    
    if result:
        print(f'[test] ✓ {problem_id} parsed successfully')
        print(f'[test]   Title: {result["title"]}')
        print(f'[test]   Description blocks: {len(result["description"])}')
        print(f'[test]   Input blocks: {len(result["input"])}')
        print(f'[test]   Output blocks: {len(result["output"])}')
        print(f'[test]   Examples: {len(result["examples"])}')
        passed += 1
    else:
        print(f'[test] ✗ {problem_id} FAILED')
        failed += 1
    
    print()

print(f'[test] ═══════════════════════════')
print(f'[test] Results: {passed} passed, {failed} failed')
print(f'[test] Success rate: {passed}/{len(html_files)} ({100*passed//len(html_files)}%)')
