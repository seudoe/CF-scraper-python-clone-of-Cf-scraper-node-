"""
HTML parser for Codeforces problem pages
Ported from CF-scraper/lib/parse.js
"""

import re
from typing import List, Optional
from bs4 import BeautifulSoup, Tag
from lib.types import (
    Block, ParagraphBlock, CodeBlock, ImageBlock, TableBlock, ListBlock,
    Example, ProblemStatement
)


def strip_tags(html: str) -> str:
    """Remove HTML tags and decode entities"""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()
    return re.sub(r'\s+', ' ', text).strip()


def parse_blocks(html: str) -> List[Block]:
    """Parse HTML into structured blocks"""
    blocks = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Process direct children of the section
    for elem in soup.children:
        if isinstance(elem, str):
            text = elem.strip()
            if text:
                blocks.append(ParagraphBlock(html=text))
            continue
        
        if not isinstance(elem, Tag):
            continue
        
        tag_name = elem.name.lower()
        
        # Image
        if tag_name == 'img':
            src = elem.get('src', '')
            alt = elem.get('alt')
            if src:
                print(f'[parse] Image found: {src}')
                blocks.append(ImageBlock(src=src, alt=alt))
        
        # Table
        elif tag_name == 'table':
            blocks.append(TableBlock(html=str(elem)))
        
        # Lists
        elif tag_name in ['ul', 'ol']:
            ordered = tag_name == 'ol'
            items = [strip_tags(str(li)) for li in elem.find_all('li', recursive=False)]
            blocks.append(ListBlock(ordered=ordered, items=items))
        
        # Code blocks
        elif tag_name == 'pre':
            code_text = strip_tags(str(elem))
            blocks.append(CodeBlock(code=code_text))
        
        # Paragraphs and divs
        elif tag_name in ['p', 'div']:
            # Check if it only contains an image
            img = elem.find('img', recursive=False)
            if img and len(list(elem.children)) == 1:
                src = img.get('src', '')
                alt = img.get('alt')
                if src:
                    print(f'[parse] Image found (in block): {src}')
                    blocks.append(ImageBlock(src=src, alt=alt))
            else:
                inner_html = ''.join(str(c) for c in elem.children)
                trimmed = inner_html.strip()
                if trimmed:
                    blocks.append(ParagraphBlock(html=trimmed))
        
        # Other tags - keep as paragraph
        else:
            text = str(elem).strip()
            if text:
                blocks.append(ParagraphBlock(html=text))
    
    return blocks


def extract_sample_tests(soup: BeautifulSoup) -> List[Example]:
    """Extract input/output examples from .sample-test divs"""
    examples = []
    
    sample_tests = soup.find_all('div', class_='sample-test')
    
    for sample in sample_tests:
        input_div = sample.find('div', class_='input')
        output_div = sample.find('div', class_='output')
        note_div = sample.find('div', class_='note')
        
        input_text = ''
        output_text = ''
        explanation = None
        
        if input_div:
            input_pre = input_div.find('pre')
            if input_pre:
                input_text = strip_tags(str(input_pre)).replace('\r\n', '\n')
        
        if output_div:
            output_pre = output_div.find('pre')
            if output_pre:
                output_text = strip_tags(str(output_pre)).replace('\r\n', '\n')
        
        if note_div:
            note_text = strip_tags(str(note_div)).strip()
            if note_text:
                explanation = note_text
        
        examples.append(Example(
            input=input_text,
            output=output_text,
            explanation=explanation
        ))
    
    return examples


def parse_problem_page(html: str, problem_key: str = '?') -> Optional[ProblemStatement]:
    """Parse a Codeforces problem page into structured ProblemStatement"""
    print(f'[parse] Parsing problem statement for {problem_key} ...')
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the .problem-statement div
    ps_div = soup.find('div', class_='problem-statement')
    if not ps_div:
        print(f'[parse] ✗ Could not find .problem-statement in HTML for {problem_key}')
        return None
    
    # Extract title, time limit, memory limit
    title_div = ps_div.find('div', class_='title')
    title = strip_tags(str(title_div)) if title_div else ''
    
    time_div = ps_div.find('div', class_='time-limit')
    time_limit = strip_tags(str(time_div)).replace('time limit per test', '').strip() if time_div else ''
    
    memory_div = ps_div.find('div', class_='memory-limit')
    memory_limit = strip_tags(str(memory_div)).replace('memory limit per test', '').strip() if memory_div else ''
    
    print(f'[parse] Title: "{title}" | Time: {time_limit} | Memory: {memory_limit}')
    
    # Extract sections
    legend_div = ps_div.find('div', class_='legend')
    description = parse_blocks(str(legend_div)) if legend_div else []
    
    input_spec_div = ps_div.find('div', class_='input-specification')
    if input_spec_div:
        # Remove section title
        section_title = input_spec_div.find('div', class_='section-title')
        if section_title:
            section_title.decompose()
        input_blocks = parse_blocks(str(input_spec_div))
    else:
        input_blocks = []
    
    output_spec_div = ps_div.find('div', class_='output-specification')
    if output_spec_div:
        section_title = output_spec_div.find('div', class_='section-title')
        if section_title:
            section_title.decompose()
        output_blocks = parse_blocks(str(output_spec_div))
    else:
        output_blocks = []
    
    examples = extract_sample_tests(ps_div)
    
    note_div = ps_div.find('div', class_='note')
    note_blocks = None
    if note_div:
        section_title = note_div.find('div', class_='section-title')
        if section_title:
            section_title.decompose()
        note_blocks = parse_blocks(str(note_div))
    
    # Count images
    all_blocks = description + input_blocks + output_blocks + (note_blocks or [])
    image_count = sum(1 for b in all_blocks if isinstance(b, ImageBlock))
    
    print(f'[parse] ✓ Parsed {problem_key}: {len(examples)} examples, {image_count} images')
    
    statement = ProblemStatement(
        title=title,
        timeLimit=time_limit,
        memoryLimit=memory_limit,
        description=description,
        input=input_blocks,
        output=output_blocks,
        examples=examples,
        note=note_blocks
    )
    
    return statement
