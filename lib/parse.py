"""HTML parser for Codeforces problem pages - Recursive DOM walker approach"""
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag, NavigableString
from .colors import magenta, green, red, cyan, success, error, warning, info


def strip_tags(html: str) -> str:
    """Remove all HTML tags and decode entities"""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()
    return ' '.join(text.split())


def walk_node(node) -> List[Dict[str, Any]]:
    """
    Recursively walk a DOM node and emit blocks.
    This is the core of the parser - handles arbitrary nesting.
    """
    blocks: List[Dict[str, Any]] = []
    
    # Base case: text node
    if isinstance(node, (str, NavigableString)):
        text = str(node).strip()
        if text:
            blocks.append({'type': 'paragraph', 'html': text})
        return blocks
    
    # Must be a Tag
    if not isinstance(node, Tag):
        return blocks
    
    # Handle different element types
    tag_name = node.name
    
    # Image - emit immediately
    if tag_name == 'img':
        src = node.get('src', '')
        if isinstance(src, list):
            src = src[0] if src else ''
        src = str(src)
        
        if src:
            print(magenta(f'[parse] Image found: {src}'))
            block: Dict[str, Any] = {'type': 'image', 'src': src}
            alt = node.get('alt')
            if alt:
                block['alt'] = str(alt)
            blocks.append(block)
        return blocks
    
    # Pre/code - emit immediately
    if tag_name == 'pre':
        code = strip_tags(str(node))
        blocks.append({'type': 'code', 'code': code})
        return blocks
    
    # Table - emit immediately
    if tag_name == 'table':
        blocks.append({'type': 'table', 'html': str(node)})
        return blocks
    
    # Lists - emit immediately
    if tag_name in ['ul', 'ol']:
        ordered = tag_name == 'ol'
        items = []
        for li in node.find_all('li', recursive=False):
            items.append(strip_tags(str(li)))
        blocks.append({'type': 'list', 'ordered': ordered, 'items': items})
        return blocks
    
    # Paragraph - emit the HTML content
    if tag_name == 'p':
        # Check if it's just an image
        img = node.find('img')
        if img and len(list(node.children)) == 1:
            # Just an image wrapped in <p>
            return walk_node(img)
        
        # Regular paragraph with content
        html_content = ''.join(str(c) for c in node.children)
        trimmed = html_content.strip()
        if trimmed:
            blocks.append({'type': 'paragraph', 'html': trimmed})
        return blocks
    
    # Div - container only, recurse into children
    if tag_name == 'div':
        for child in node.children:
            blocks.extend(walk_node(child))
        return blocks
    
    # Br - ignore
    if tag_name == 'br':
        return blocks
    
    # Other inline tags (span, a, strong, em, etc) - treat as text
    if tag_name in ['span', 'a', 'strong', 'em', 'b', 'i', 'u', 'code', 'sub', 'sup']:
        # Return the whole element as HTML for inline formatting
        html = str(node).strip()
        if html:
            blocks.append({'type': 'paragraph', 'html': html})
        return blocks
    
    # Unknown tag - recurse
    for child in node.children:
        blocks.extend(walk_node(child))
    
    return blocks


def extract_examples(sample_tests_div: Tag) -> List[Dict[str, Any]]:
    """Extract test cases from sample-tests div"""
    examples: List[Dict[str, Any]] = []
    
    # Find all sample-test divs
    for sample in sample_tests_div.find_all('div', class_=lambda c: c and 'sample-test' in str(c).split()):
        if not isinstance(sample, Tag):
            continue
        
        # Find input
        input_div = sample.find('div', class_=lambda c: c and 'input' in str(c).split())
        input_text = ''
        if input_div:
            pre = input_div.find('pre')
            if pre:
                input_text = strip_tags(str(pre)).replace('\r\n', '\n')
        
        # Find output
        output_div = sample.find('div', class_=lambda c: c and 'output' in str(c).split())
        output_text = ''
        if output_div:
            pre = output_div.find('pre')
            if pre:
                output_text = strip_tags(str(pre)).replace('\r\n', '\n')
        
        example: Dict[str, Any] = {
            'input': input_text,
            'output': output_text
        }
        
        # Optional explanation/note
        note_div = sample.find('div', class_=lambda c: c and 'note' in str(c).split())
        if note_div:
            note_text = strip_tags(str(note_div)).strip()
            if note_text:
                example['explanation'] = note_text
        
        examples.append(example)
    
    return examples


def parse_problem_page(html: str, problem_key: str = '?') -> Optional[Dict[str, Any]]:
    """
    Parse a Codeforces problem page using a sequential walker approach.
    This handles arbitrary HTML nesting and doesn't rely on specific structure.
    """
    print(magenta(f'[parse] Parsing problem statement for {problem_key} ...'))
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find problem-statement div
    ps_div = soup.find('div', class_=lambda c: c and 'problem-statement' in str(c).split())
    if not ps_div or not isinstance(ps_div, Tag):
        print(red(f'[parse] ✗ Could not find .problem-statement in HTML for {problem_key}'))
        return None
    
    # Extract metadata from header
    title = ''
    time_limit = ''
    memory_limit = ''
    
    header_div = ps_div.find('div', class_=lambda c: c and 'header' in str(c).split())
    if header_div and isinstance(header_div, Tag):
        title_div = header_div.find('div', class_=lambda c: c and 'title' in str(c).split())
        if title_div:
            title = strip_tags(str(title_div))
        
        time_div = header_div.find('div', class_=lambda c: c and 'time-limit' in str(c).split())
        if time_div:
            time_limit = strip_tags(str(time_div)).replace('time limit per test', '').strip()
        
        memory_div = header_div.find('div', class_=lambda c: c and 'memory-limit' in str(c).split())
        if memory_div:
            memory_limit = strip_tags(str(memory_div)).replace('memory limit per test', '').strip()
    
    print(cyan(f'[parse] Title: "{title}" | Time: {time_limit} | Memory: {memory_limit}'))
    
    # Sequential parsing approach: walk through children and switch sections
    current_section = 'description'
    sections = {
        'description': [],
        'input': [],
        'output': [],
        'note': []
    }
    examples = []
    
    # Walk through all direct children of problem-statement
    for child in ps_div.children:
        if not isinstance(child, Tag):
            continue
        
        classes = child.get('class', [])
        if not isinstance(classes, list):
            classes = str(classes).split()
        
        # Check if this is a section marker
        if 'header' in classes:
            # Skip header, already processed
            continue
        
        elif 'input-specification' in classes:
            current_section = 'input'
            # Remove section title and walk the rest
            for section_child in child.children:
                if isinstance(section_child, Tag):
                    child_classes = section_child.get('class', [])
                    if not isinstance(child_classes, list):
                        child_classes = str(child_classes).split()
                    if 'section-title' not in child_classes:
                        sections['input'].extend(walk_node(section_child))
            continue
        
        elif 'output-specification' in classes:
            current_section = 'output'
            # Remove section title and walk the rest
            for section_child in child.children:
                if isinstance(section_child, Tag):
                    child_classes = section_child.get('class', [])
                    if not isinstance(child_classes, list):
                        child_classes = str(child_classes).split()
                    if 'section-title' not in child_classes:
                        sections['output'].extend(walk_node(section_child))
            continue
        
        elif 'sample-tests' in classes or 'sample-test' in classes:
            # Extract examples
            examples = extract_examples(child)
            continue
        
        elif 'note' in classes and 'sample-test' not in ' '.join(classes):
            current_section = 'note'
            # Remove section title and walk the rest
            for section_child in child.children:
                if isinstance(section_child, Tag):
                    child_classes = section_child.get('class', [])
                    if not isinstance(child_classes, list):
                        child_classes = str(child_classes).split()
                    if 'section-title' not in child_classes:
                        sections['note'].extend(walk_node(section_child))
            continue
        
        # No specific section marker - add to current section
        sections[current_section].extend(walk_node(child))
    
    # Build result
    image_count = sum(
        1 for section in sections.values()
        for block in section
        if block.get('type') == 'image'
    )
    
    print(success(f'[parse] Parsed {problem_key}: {len(examples)} examples, {image_count} images'))
    
    result: Dict[str, Any] = {
        'title': title,
        'timeLimit': time_limit,
        'memoryLimit': memory_limit,
        'description': sections['description'],
        'input': sections['input'],
        'output': sections['output'],
        'examples': examples
    }
    
    if sections['note']:
        result['note'] = sections['note']
    
    return result
